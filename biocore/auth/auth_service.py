from collections.abc import Callable
from typing import Protocol

from .models import IdentityClaims, IssuedSession
from .repositories import IdentityDirectory
from .session_service import SessionService, utc_now


class AuthenticationError(PermissionError):
    """Raised when an external identity cannot start a BioCore session."""


class EmailVerificationRequired(AuthenticationError):
    pass


class IdentityVerifier(Protocol):
    def verify(self, raw_identity_token: str) -> IdentityClaims:
        """Validate signature, issuer, audience, expiration and identity claims."""


class AuthService:
    def __init__(
        self,
        verifier: IdentityVerifier,
        directory: IdentityDirectory,
        sessions: SessionService,
        *,
        clock: Callable = utc_now,
    ) -> None:
        self._verifier = verifier
        self._directory = directory
        self._sessions = sessions
        self._clock = clock

    def exchange(
        self,
        raw_identity_token: str,
        organization_id: str | None = None,
    ) -> IssuedSession:
        claims = self._verifier.verify(raw_identity_token)
        if not claims.email_verified:
            raise EmailVerificationRequired("Verified email is required")
        user = self._directory.find_user(claims.provider, claims.subject)
        if user is None or not user.is_active:
            raise AuthenticationError("BioCore account is not active")
        if user.email and user.email != claims.email:
            raise AuthenticationError("Identity email does not match BioCore account")
        if not user.email_verified:
            raise EmailVerificationRequired("BioCore email is not verified")
        organizations = self._directory.organization_ids(user.id)
        if not organizations:
            raise AuthenticationError("No active organization membership")
        selected = organization_id or (organizations[0] if len(organizations) == 1 else None)
        if selected is None:
            raise AuthenticationError("Active organization must be selected")
        if selected not in organizations:
            raise AuthenticationError("Organization membership was not found")
        self._directory.record_login(user.id, self._clock())
        return self._sessions.issue(
            user.id,
            selected,
            auth_method=claims.provider,
        )
