from dataclasses import dataclass
from typing import Mapping, Protocol

from .authorization import UserContext


class InvalidIdentityError(ValueError):
    """Raised when an identity provider response lacks required claims."""


@dataclass(frozen=True)
class AuthenticatedIdentity:
    subject: str
    email: str | None

    @classmethod
    def from_oidc_claims(cls, claims: Mapping[str, object]) -> "AuthenticatedIdentity":
        subject = str(claims.get("sub") or "").strip()
        if not subject:
            raise InvalidIdentityError("OIDC claim 'sub' is required")
        email_value = claims.get("email")
        email = str(email_value).strip().lower() if email_value else None
        return cls(subject=subject, email=email)


class MembershipResolver(Protocol):
    def resolve_context(
        self, identity: AuthenticatedIdentity, organization_id: str | None = None
    ) -> UserContext:
        """Resolve organization and roles from the database, never from UI input."""
