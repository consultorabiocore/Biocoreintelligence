from datetime import datetime, timezone
from typing import Any

from biocore.auth.models import (
    AccessGrant,
    AuthenticatedUser,
    InvitationRecord,
    LaunchCodeRecord,
    SessionRecord,
)
from biocore.domain.subscriptions import ModuleCode
from biocore.repositories.subscriptions import SupabaseSubscriptionRepository
from biocore.security.audit import AuditEvent
from biocore.security.roles import ROLE_PERMISSIONS, Role


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _user_from_row(row: dict[str, object]) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=str(row["id"]),
        email=str(row.get("email") or "").strip().lower(),
        display_name=(
            str(row["display_name"]).strip()
            if row.get("display_name")
            else None
        ),
        status=str(row.get("status") or "active"),
        email_verified=bool(row.get("email_verified", False)),
    )


def _session_from_row(row: dict[str, object]) -> SessionRecord:
    return SessionRecord(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        organization_id=str(row["organization_id"]),
        audience=str(row.get("audience") or "platform"),
        auth_method=str(row.get("auth_method") or "unknown"),
        started_at=_as_datetime(row["started_at"]),
        expires_at=_as_datetime(row["expires_at"]),
        parent_session_id=(
            str(row["parent_session_id"])
            if row.get("parent_session_id")
            else None
        ),
        revoked_at=(
            _as_datetime(row["revoked_at"]) if row.get("revoked_at") else None
        ),
    )


def _launch_from_row(row: dict[str, object]) -> LaunchCodeRecord:
    return LaunchCodeRecord(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        user_id=str(row["user_id"]),
        organization_id=str(row["organization_id"]),
        module_code=str(row["module_code"]),
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        return_to=str(row["return_to"]),
        expires_at=_as_datetime(row["expires_at"]),
        used_at=_as_datetime(row["used_at"]) if row.get("used_at") else None,
    )


def _invitation_from_row(row: dict[str, object]) -> InvitationRecord:
    return InvitationRecord(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        email=str(row["email"]).strip().lower(),
        role=str(row["role"]),
        project_ids=tuple(str(item) for item in (row.get("project_ids") or [])),
        invited_by_user_id=str(row["invited_by_user_id"]),
        expires_at=_as_datetime(row["expires_at"]),
        accepted_at=(
            _as_datetime(row["accepted_at"]) if row.get("accepted_at") else None
        ),
        revoked_at=(
            _as_datetime(row["revoked_at"]) if row.get("revoked_at") else None
        ),
    )


class SupabaseCentralAuthRepository:
    """Trusted server repository for central identity and opaque sessions."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._subscriptions = SupabaseSubscriptionRepository(client)

    def get_user(self, user_id: str) -> AuthenticatedUser | None:
        response = (
            self._client.table("app_users")
            .select("id,email,display_name,status,email_verified")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return _user_from_row(rows[0]) if rows else None

    def mark_verified_oidc_identity(
        self,
        user_id: str,
        *,
        provider: str,
        subject: str,
        email: str,
    ) -> None:
        """Link a verified provider subject already resolved to this user."""
        normalized_email = email.strip().lower()
        identity_response = (
            self._client.table("auth_identities")
            .select("id,user_id")
            .eq("provider", provider)
            .eq("provider_subject", subject)
            .limit(1)
            .execute()
        )
        identities = identity_response.data or []
        values = {
            "email_at_provider": normalized_email,
            "last_used_at": datetime.now(timezone.utc).isoformat(),
        }
        if identities:
            if str(identities[0]["user_id"]) != user_id:
                raise PermissionError("OIDC identity is linked to another user")
            (
                self._client.table("auth_identities")
                .update(values)
                .eq("id", identities[0]["id"])
                .execute()
            )
        else:
            self._client.table("auth_identities").insert(
                {
                    **values,
                    "user_id": user_id,
                    "provider": provider,
                    "provider_subject": subject,
                }
            ).execute()
        self._client.table("app_users").update(
            {
                "email": normalized_email,
                "email_verified": True,
            }
        ).eq("id", user_id).execute()

    def find_user(self, provider: str, subject: str) -> AuthenticatedUser | None:
        identity_response = (
            self._client.table("auth_identities")
            .select("user_id")
            .eq("provider", provider)
            .eq("provider_subject", subject)
            .limit(1)
            .execute()
        )
        rows = identity_response.data or []
        if not rows and provider in {"legacy_oidc", "google"}:
            legacy_response = (
                self._client.table("app_users")
                .select("id")
                .eq("external_subject", subject)
                .limit(1)
                .execute()
            )
            rows = [
                {"user_id": item["id"]}
                for item in (legacy_response.data or [])
            ]
        return self.get_user(str(rows[0]["user_id"])) if rows else None

    def organization_ids(self, user_id: str) -> tuple[str, ...]:
        response = (
            self._client.table("memberships")
            .select("organization_id")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        return tuple(
            sorted(
                {
                    str(item["organization_id"])
                    for item in (response.data or [])
                }
            )
        )

    def resolve_access(self, user_id: str, organization_id: str) -> AccessGrant:
        user = self.get_user(user_id)
        if user is None or not user.is_active:
            raise PermissionError("BioCore user is not active")
        if not user.email_verified:
            raise PermissionError("Verified BioCore email is required")
        membership_response = (
            self._client.table("memberships")
            .select("organization_id,role")
            .eq("user_id", user_id)
            .eq("active", True)
            .execute()
        )
        roles = frozenset(
            str(item["role"])
            for item in (membership_response.data or [])
            if str(item["organization_id"]) == organization_id
            or str(item["role"]) == Role.SUPERADMIN.value
        )
        if not roles:
            raise PermissionError("Active organization membership is required")

        permission_response = (
            self._client.table("role_permissions")
            .select("permission_code")
            .in_("role_code", sorted(roles))
            .execute()
        )
        permissions = frozenset(
            str(item["permission_code"])
            for item in (permission_response.data or [])
        )
        if not permissions:
            # Compatibility during the additive role-permission rollout.
            parsed_roles = {
                Role(role) for role in roles if role in {item.value for item in Role}
            }
            permissions = frozenset(
                permission.value
                for role in parsed_roles
                for permission in ROLE_PERMISSIONS[role]
            )

        subscription = self._subscriptions.get_snapshot(organization_id)
        modules = frozenset(
            module.value for module in subscription.base_enabled_modules
        )
        if Role.SUPERADMIN.value in roles:
            modules = frozenset(module.value for module in ModuleCode)

        if (
            Role.SUPERADMIN.value in roles
            or Role.BIOCORE_ADMIN.value in roles
            or "projects:grant_access" in permissions
        ):
            project_response = (
                self._client.table("projects")
                .select("id")
                .eq("organization_id", organization_id)
                .eq("status", "active")
                .execute()
            )
        else:
            project_response = (
                self._client.table("project_access")
                .select("project_id")
                .eq("organization_id", organization_id)
                .eq("user_id", user_id)
                .eq("active", True)
                .execute()
            )
        project_ids = frozenset(
            str(item.get("id") or item.get("project_id"))
            for item in (project_response.data or [])
        )
        project_modules = {
            project_id: frozenset(module.value for module in granted_modules)
            for project_id, granted_modules in subscription.project_module_map.items()
            if project_id in project_ids
        }
        return AccessGrant(
            roles,
            permissions,
            modules,
            project_ids,
            project_modules,
        )

    def record_login(self, user_id: str, at: datetime) -> None:
        self._client.table("app_users").update(
            {"last_login_at": at.isoformat()}
        ).eq("id", user_id).execute()

    def create_session(self, record: SessionRecord, token_hash: str) -> None:
        self._client.table("auth_sessions").insert(
            {
                "id": record.id,
                "token_hash": token_hash,
                "user_id": record.user_id,
                "organization_id": record.organization_id,
                "parent_session_id": record.parent_session_id,
                "audience": record.audience,
                "auth_method": record.auth_method,
                "started_at": record.started_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
            }
        ).execute()

    def _get_session(self, column: str, value: str) -> SessionRecord | None:
        response = (
            self._client.table("auth_sessions")
            .select(
                "id,user_id,organization_id,parent_session_id,audience,"
                "auth_method,started_at,expires_at,revoked_at"
            )
            .eq(column, value)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return _session_from_row(rows[0]) if rows else None

    def get_session_by_hash(self, token_hash: str) -> SessionRecord | None:
        return self._get_session("token_hash", token_hash)

    def get_session_by_id(self, session_id: str) -> SessionRecord | None:
        return self._get_session("id", session_id)

    def touch_session(self, session_id: str, at: datetime) -> None:
        self._client.table("auth_sessions").update(
            {"last_seen_at": at.isoformat()}
        ).eq("id", session_id).is_("revoked_at", "null").execute()

    def revoke_session(self, session_id: str, at: datetime, reason: str) -> None:
        self._client.rpc(
            "revoke_session_tree",
            {
                "target_session_id": session_id,
                "target_reason": reason,
            },
        ).execute()

    def revoke_all_sessions(self, user_id: str, at: datetime, reason: str) -> int:
        response = (
            self._client.table("auth_sessions")
            .update({"revoked_at": at.isoformat(), "revoked_reason": reason})
            .eq("user_id", user_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return len(response.data or [])

    def create_launch_code(
        self, record: LaunchCodeRecord, code_hash: str
    ) -> None:
        self._client.table("module_launch_codes").insert(
            {
                "id": record.id,
                "code_hash": code_hash,
                "session_id": record.session_id,
                "user_id": record.user_id,
                "organization_id": record.organization_id,
                "module_code": record.module_code,
                "project_id": record.project_id,
                "return_to": record.return_to,
                "expires_at": record.expires_at.isoformat(),
            }
        ).execute()

    def consume_launch_code(
        self, code_hash: str, module_code: str
    ) -> LaunchCodeRecord | None:
        response = self._client.rpc(
            "consume_module_launch_code",
            {
                "target_code_hash": code_hash,
                "target_module_code": module_code,
            },
        ).execute()
        rows = response.data or []
        return _launch_from_row(rows[0]) if rows else None

    def create_invitation(
        self, record: InvitationRecord, token_hash: str
    ) -> None:
        self._client.table("invitations").insert(
            {
                "id": record.id,
                "token_hash": token_hash,
                "organization_id": record.organization_id,
                "email": record.email,
                "role": record.role,
                "project_ids": list(record.project_ids),
                "invited_by_user_id": record.invited_by_user_id,
                "expires_at": record.expires_at.isoformat(),
            }
        ).execute()

    def consume_invitation(
        self, token_hash: str, user_id: str, verified_email: str
    ) -> InvitationRecord | None:
        response = self._client.rpc(
            "consume_invitation",
            {
                "target_token_hash": token_hash,
                "target_user_id": user_id,
                "target_verified_email": verified_email,
            },
        ).execute()
        rows = response.data or []
        return _invitation_from_row(rows[0]) if rows else None

    def activate_membership(
        self, user_id: str, invitation: InvitationRecord
    ) -> None:
        self._client.table("memberships").upsert(
            {
                "user_id": user_id,
                "organization_id": invitation.organization_id,
                "role": invitation.role,
                "active": True,
            }
        ).execute()
        if invitation.project_ids:
            self._client.table("project_access").upsert(
                [
                    {
                        "user_id": user_id,
                        "organization_id": invitation.organization_id,
                        "project_id": project_id,
                        "access_level": (
                            "edit"
                            if invitation.role == Role.CLIENT_EDITOR.value
                            else "read"
                        ),
                        "active": True,
                    }
                    for project_id in invitation.project_ids
                ]
            ).execute()


class SupabaseAuditWriter:
    def __init__(self, client: Any) -> None:
        self._client = client

    def write(self, event: AuditEvent) -> None:
        self._client.table("audit_log").insert(
            {
                "organization_id": event.organization_id,
                "user_id": event.user_id,
                "session_id": event.session_id,
                "event_code": event.event_code,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "outcome": event.outcome,
                "metadata": dict(event.metadata),
                "occurred_at": event.occurred_at.isoformat(),
            }
        ).execute()
