from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class IdentityClaims:
    provider: str
    subject: str
    email: str
    email_verified: bool
    display_name: str | None = None


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    display_name: str | None
    status: str
    email_verified: bool

    @property
    def is_active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class AccessGrant:
    roles: frozenset[str]
    permissions: frozenset[str]
    modules: frozenset[str]
    project_ids: frozenset[str] = field(default_factory=frozenset)
    project_modules: Mapping[str, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionRecord:
    id: str
    user_id: str
    organization_id: str
    audience: str
    auth_method: str
    started_at: datetime
    expires_at: datetime
    parent_session_id: str | None = None
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now


@dataclass(frozen=True)
class SessionContext:
    session_id: str
    user_id: str
    organization_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    modules: frozenset[str]
    project_ids: frozenset[str]
    audience: str
    started_at: datetime
    expires_at: datetime
    project_modules: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def has_permission(self, permission_code: str) -> bool:
        return permission_code in self.permissions

    def has_module(self, module_code: str) -> bool:
        return module_code in self.modules

    def has_project(self, project_id: str) -> bool:
        return project_id in self.project_ids

    def has_project_module(self, project_id: str, module_code: str) -> bool:
        return module_code in self.project_modules.get(project_id, frozenset())


@dataclass(frozen=True)
class IssuedSession:
    token: str
    context: SessionContext


@dataclass(frozen=True)
class LaunchCodeRecord:
    id: str
    session_id: str
    user_id: str
    organization_id: str
    module_code: str
    project_id: str | None
    return_to: str
    expires_at: datetime
    used_at: datetime | None = None


@dataclass(frozen=True)
class IssuedLaunchCode:
    code: str
    module_code: str
    return_to: str
    expires_at: datetime


@dataclass(frozen=True)
class InvitationRecord:
    id: str
    organization_id: str
    email: str
    role: str
    project_ids: tuple[str, ...]
    invited_by_user_id: str
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class IssuedInvitation:
    token: str
    invitation: InvitationRecord
