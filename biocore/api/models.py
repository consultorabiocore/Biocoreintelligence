from datetime import datetime

from pydantic import BaseModel, Field

from biocore.auth.models import IssuedSession, SessionContext


class AuthExchangeRequest(BaseModel):
    organization_id: str | None = None


class ModuleLaunchRequest(BaseModel):
    module_code: str = Field(min_length=1, max_length=80)
    return_to: str = Field(min_length=1, max_length=2048)
    project_id: str | None = None


class ModuleLaunchResponse(BaseModel):
    code: str
    module_code: str
    return_to: str
    expires_at: datetime


class ModuleExchangeRequest(BaseModel):
    code: str = Field(min_length=20, max_length=512)
    module_code: str = Field(min_length=1, max_length=80)


class SessionResponse(BaseModel):
    token: str | None = None
    session_id: str
    user_id: str
    organization_id: str
    roles: list[str]
    permissions: list[str]
    modules: list[str]
    project_ids: list[str]
    project_modules: dict[str, list[str]]
    audience: str
    started_at: datetime
    expires_at: datetime

    @classmethod
    def from_context(
        cls,
        context: SessionContext,
        *,
        token: str | None = None,
    ) -> "SessionResponse":
        return cls(
            token=token,
            session_id=context.session_id,
            user_id=context.user_id,
            organization_id=context.organization_id,
            roles=sorted(context.roles),
            permissions=sorted(context.permissions),
            modules=sorted(context.modules),
            project_ids=sorted(context.project_ids),
            project_modules={
                project_id: sorted(modules)
                for project_id, modules in sorted(
                    context.project_modules.items()
                )
            },
            audience=context.audience,
            started_at=context.started_at,
            expires_at=context.expires_at,
        )

    @classmethod
    def from_issued(cls, issued: IssuedSession) -> "SessionResponse":
        return cls.from_context(issued.context, token=issued.token)


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(min_length=1, max_length=80)
    project_ids: list[str] = Field(default_factory=list, max_length=500)


class InvitationCreateResponse(BaseModel):
    token: str
    invitation_id: str
    organization_id: str
    email: str
    role: str
    project_ids: list[str]
    expires_at: datetime


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
