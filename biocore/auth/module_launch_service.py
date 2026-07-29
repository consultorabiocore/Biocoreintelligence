from collections.abc import Callable
from datetime import timedelta
from urllib.parse import urlparse
from uuid import uuid4

from .models import IssuedLaunchCode, IssuedSession, LaunchCodeRecord
from .repositories import SessionRepository
from .session_service import SessionError, SessionService, utc_now
from .tokens import OpaqueTokenFactory


class ModuleAccessDenied(PermissionError):
    pass


class ProjectAccessDenied(PermissionError):
    pass


class InvalidReturnUrl(ValueError):
    pass


class RedirectPolicy:
    def __init__(self, allowed_hosts: frozenset[str]) -> None:
        self._allowed_hosts = frozenset(host.lower() for host in allowed_hosts)

    def validate(self, return_to: str) -> str:
        parsed = urlparse(return_to)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or host not in self._allowed_hosts:
            raise InvalidReturnUrl("Module return URL is not allowlisted")
        if parsed.username or parsed.password:
            raise InvalidReturnUrl("Credentials are not allowed in return URL")
        return return_to


class ModuleLaunchService:
    def __init__(
        self,
        sessions: SessionService,
        repository: SessionRepository,
        redirect_policy: RedirectPolicy,
        *,
        token_factory: OpaqueTokenFactory | None = None,
        launch_ttl: timedelta = timedelta(minutes=2),
        clock: Callable = utc_now,
    ) -> None:
        self._sessions = sessions
        self._repository = repository
        self._redirects = redirect_policy
        self._tokens = token_factory or OpaqueTokenFactory()
        self._launch_ttl = launch_ttl
        self._clock = clock

    def issue(
        self,
        session_token: str,
        module_code: str,
        return_to: str,
        project_id: str | None = None,
    ) -> IssuedLaunchCode:
        context = self._sessions.validate(session_token)
        has_global_module = context.has_module(module_code)
        has_project_module = bool(
            project_id and context.has_project_module(project_id, module_code)
        )
        if not has_global_module and not has_project_module:
            raise ModuleAccessDenied(f"Module not enabled: {module_code}")
        if project_id and not context.has_project(project_id):
            raise ProjectAccessDenied("Project is not authorized")
        validated_url = self._redirects.validate(return_to)
        now = self._clock()
        raw_code, code_hash = self._tokens.issue()
        record = LaunchCodeRecord(
            id=str(uuid4()),
            session_id=context.session_id,
            user_id=context.user_id,
            organization_id=context.organization_id,
            module_code=module_code,
            project_id=project_id,
            return_to=validated_url,
            expires_at=now + self._launch_ttl,
        )
        self._repository.create_launch_code(record, code_hash)
        return IssuedLaunchCode(
            code=raw_code,
            module_code=module_code,
            return_to=validated_url,
            expires_at=record.expires_at,
        )

    def exchange(self, raw_code: str, module_code: str) -> IssuedSession:
        if not raw_code:
            raise SessionError("Module launch code is required")
        record = self._repository.consume_launch_code(
            self._tokens.digest(raw_code), module_code
        )
        if record is None:
            raise SessionError("Module launch code is invalid, expired or used")
        child = self._sessions.issue_child(record.session_id, module_code)
        has_global_module = child.context.has_module(module_code)
        has_project_module = bool(
            record.project_id
            and child.context.has_project_module(record.project_id, module_code)
        )
        if not has_global_module and not has_project_module:
            raise ModuleAccessDenied("Module entitlement is no longer active")
        if record.project_id and not child.context.has_project(record.project_id):
            raise ProjectAccessDenied("Project access is no longer active")
        return child
