from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .models import IssuedSession, SessionContext, SessionRecord
from .repositories import IdentityDirectory, SessionRepository
from .tokens import OpaqueTokenFactory


class SessionError(PermissionError):
    """Base error for invalid or unavailable central sessions."""


class SessionExpired(SessionError):
    pass


class SessionRevoked(SessionError):
    pass


class SessionAudienceMismatch(SessionError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    def __init__(
        self,
        repository: SessionRepository,
        directory: IdentityDirectory,
        *,
        token_factory: OpaqueTokenFactory | None = None,
        session_ttl: timedelta = timedelta(hours=8),
        module_session_ttl: timedelta = timedelta(hours=2),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._directory = directory
        self._tokens = token_factory or OpaqueTokenFactory()
        self._session_ttl = session_ttl
        self._module_session_ttl = module_session_ttl
        self._clock = clock

    def issue(
        self,
        user_id: str,
        organization_id: str,
        *,
        auth_method: str,
        audience: str = "platform",
        parent_session_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> IssuedSession:
        now = self._clock()
        self._directory.resolve_access(user_id, organization_id)
        raw_token, token_hash = self._tokens.issue()
        ttl = (
            self._module_session_ttl
            if parent_session_id is not None
            else self._session_ttl
        )
        record = SessionRecord(
            id=str(uuid4()),
            user_id=user_id,
            organization_id=organization_id,
            audience=audience,
            auth_method=auth_method,
            started_at=now,
            expires_at=min(expires_at, now + ttl) if expires_at else now + ttl,
            parent_session_id=parent_session_id,
        )
        self._repository.create_session(record, token_hash)
        return IssuedSession(raw_token, self._context(record))

    def validate(
        self,
        raw_token: str,
        *,
        expected_audience: str | None = None,
    ) -> SessionContext:
        if not raw_token:
            raise SessionError("Central session token is required")
        record = self._repository.get_session_by_hash(
            self._tokens.digest(raw_token)
        )
        if record is None:
            raise SessionError("Central session was not found")
        now = self._clock()
        if record.revoked_at is not None:
            raise SessionRevoked("Central session was revoked")
        if record.expires_at <= now:
            raise SessionExpired("Central session expired")
        if expected_audience and record.audience not in {
            expected_audience,
            "platform",
        }:
            raise SessionAudienceMismatch("Session audience is not allowed")
        self._repository.touch_session(record.id, now)
        return self._context(record)

    def issue_child(
        self,
        parent_session_id: str,
        audience: str,
    ) -> IssuedSession:
        parent = self._repository.get_session_by_id(parent_session_id)
        if parent is None:
            raise SessionError("Parent session was not found")
        now = self._clock()
        if not parent.is_active(now):
            raise SessionExpired("Parent session is no longer active")
        return self.issue(
            parent.user_id,
            parent.organization_id,
            auth_method="module_launch_code",
            audience=audience,
            parent_session_id=parent.id,
            expires_at=parent.expires_at,
        )

    def revoke(self, raw_token: str, reason: str = "user_logout") -> None:
        context = self.validate(raw_token)
        self._repository.revoke_session(context.session_id, self._clock(), reason)

    def revoke_all(self, user_id: str, reason: str = "user_request") -> int:
        return self._repository.revoke_all_sessions(
            user_id, self._clock(), reason
        )

    def _context(self, record: SessionRecord) -> SessionContext:
        access = self._directory.resolve_access(
            record.user_id, record.organization_id
        )
        return SessionContext(
            session_id=record.id,
            user_id=record.user_id,
            organization_id=record.organization_id,
            roles=access.roles,
            permissions=access.permissions,
            modules=access.modules,
            project_ids=access.project_ids,
            audience=record.audience,
            started_at=record.started_at,
            expires_at=record.expires_at,
            project_modules=access.project_modules,
        )
