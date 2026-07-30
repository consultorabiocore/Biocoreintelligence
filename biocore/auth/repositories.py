from datetime import datetime
from typing import Protocol

from .models import (
    AccessGrant,
    AuthenticatedUser,
    InvitationRecord,
    LaunchCodeRecord,
    SessionRecord,
)


class IdentityDirectory(Protocol):
    def get_user(self, user_id: str) -> AuthenticatedUser | None:
        """Return one central user without exposing credential material."""

    def find_user(self, provider: str, subject: str) -> AuthenticatedUser | None:
        """Resolve a verified identity-provider subject to one BioCore user."""

    def organization_ids(self, user_id: str) -> tuple[str, ...]:
        """Return active organization memberships for a user."""

    def resolve_access(self, user_id: str, organization_id: str) -> AccessGrant:
        """Resolve current roles, permissions, modules and projects."""

    def record_login(self, user_id: str, at: datetime) -> None:
        """Record a successful central authentication."""


class SessionRepository(Protocol):
    def create_session(self, record: SessionRecord, token_hash: str) -> None:
        """Persist a new opaque session."""

    def get_session_by_hash(self, token_hash: str) -> SessionRecord | None:
        """Find one session by opaque-token digest."""

    def get_session_by_id(self, session_id: str) -> SessionRecord | None:
        """Find one session for a single-use launch exchange."""

    def touch_session(self, session_id: str, at: datetime) -> None:
        """Update last-seen time without extending expiration."""

    def revoke_session(self, session_id: str, at: datetime, reason: str) -> None:
        """Revoke one session."""

    def revoke_all_sessions(self, user_id: str, at: datetime, reason: str) -> int:
        """Revoke every active session for a user."""

    def create_launch_code(
        self, record: LaunchCodeRecord, code_hash: str
    ) -> None:
        """Persist one short-lived module launch code."""

    def consume_launch_code(
        self, code_hash: str, module_code: str
    ) -> LaunchCodeRecord | None:
        """Atomically consume one unexpired launch code."""


class InvitationRepository(Protocol):
    def create_invitation(
        self, record: InvitationRecord, token_hash: str
    ) -> None:
        """Persist an invitation while keeping only the token digest."""

    def consume_invitation(
        self, token_hash: str, user_id: str, verified_email: str
    ) -> InvitationRecord | None:
        """Atomically accept one valid invitation."""

    def activate_membership(
        self,
        user_id: str,
        invitation: InvitationRecord,
    ) -> None:
        """Create membership and project access after acceptance."""
