from dataclasses import dataclass

from fastapi import Cookie, Header, HTTPException, Request, status

from biocore.auth.auth_service import AuthService
from biocore.auth.invitation_service import InvitationService
from biocore.auth.module_launch_service import ModuleLaunchService
from biocore.auth.repositories import IdentityDirectory
from biocore.auth.session_service import SessionService
from biocore.config.settings import Settings
from biocore.security.audit import AuditService


@dataclass(frozen=True)
class ApiServices:
    settings: Settings
    directory: IdentityDirectory
    auth: AuthService
    sessions: SessionService
    launches: ModuleLaunchService
    invitations: InvitationService
    audit: AuditService | None = None


def get_services(request: Request) -> ApiServices:
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, ApiServices):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Central authentication is not configured",
        )
    return services


def bearer_value(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def central_session_token(
    request: Request,
    authorization: str | None = Header(default=None),
    biocore_session: str | None = Cookie(default=None),
) -> str:
    services = get_services(request)
    cookie_value = request.cookies.get(services.settings.auth_cookie_name)
    token = cookie_value or biocore_session or bearer_value(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Central BioCore session is required",
        )
    return token
