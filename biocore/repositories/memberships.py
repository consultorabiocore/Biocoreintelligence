from dataclasses import dataclass
from typing import Any

from biocore.security.authorization import UserContext
from biocore.security.identity import AuthenticatedIdentity
from biocore.security.roles import Role


class IdentityNotProvisionedError(LookupError):
    """The authenticated identity has no active BioCore membership."""


@dataclass(frozen=True)
class OrganizationSelectionRequired(LookupError):
    organization_ids: tuple[str, ...]


class SupabaseMembershipResolver:
    """Resolve trusted authorization data using a server-only Supabase client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def resolve_context(
        self, identity: AuthenticatedIdentity, organization_id: str | None = None
    ) -> UserContext:
        user_response = (
            self._client.table("app_users")
            .select("id")
            .eq("external_subject", identity.subject)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        users = user_response.data or []
        if not users:
            raise IdentityNotProvisionedError("User is not provisioned")

        user_id = str(users[0]["id"])
        membership_response = (
            self._client.table("memberships")
            .select("organization_id,role")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        rows = membership_response.data or []
        if not rows:
            raise IdentityNotProvisionedError("User has no active membership")

        superadmin_rows = [row for row in rows if row.get("role") == Role.SUPERADMIN]
        if superadmin_rows:
            selected = organization_id or str(superadmin_rows[0]["organization_id"])
            return UserContext(user_id, selected, frozenset({Role.SUPERADMIN}))

        available = tuple(sorted({str(row["organization_id"]) for row in rows}))
        if organization_id is None and len(available) > 1:
            raise OrganizationSelectionRequired(available)

        selected = organization_id or available[0]
        if selected not in available:
            raise IdentityNotProvisionedError("Organization membership not found")

        roles = frozenset(
            Role(str(row["role"]))
            for row in rows
            if str(row["organization_id"]) == selected
        )
        return UserContext(user_id, selected, roles)
