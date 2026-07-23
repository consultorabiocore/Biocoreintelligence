from dataclasses import dataclass
from typing import Mapping, Protocol

from .authorization import UserContext


class InvalidIdentityError(ValueError):
    """Raised when an identity provider response lacks required claims."""


@dataclass(frozen=True)
class AuthenticatedIdentity:
    subject: str
    email: str | None
    display_name: str | None = None

    @classmethod
    def from_oidc_claims(cls, claims: Mapping[str, object]) -> "AuthenticatedIdentity":
        subject = str(claims.get("sub") or "").strip()
        if not subject:
            raise InvalidIdentityError("OIDC claim 'sub' is required")
        email_value = claims.get("email")
        email = str(email_value).strip().lower() if email_value else None
        name_value = claims.get("name")
        display_name = str(name_value).strip() if name_value else None
        return cls(subject=subject, email=email, display_name=display_name)


class MembershipResolver(Protocol):
    def resolve_context(
        self, identity: AuthenticatedIdentity, organization_id: str | None = None
    ) -> UserContext:
        """Resolve organization and roles from the database, never from UI input."""
