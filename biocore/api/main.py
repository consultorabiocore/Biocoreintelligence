from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from supabase import create_client

from biocore.api.dependencies import (
    ApiServices,
    bearer_value,
    central_session_token,
    get_services,
)
from biocore.api.models import (
    AuthExchangeRequest,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationCreateResponse,
    ModuleExchangeRequest,
    ModuleLaunchRequest,
    ModuleLaunchResponse,
    SessionResponse,
)
from biocore.auth.auth_service import AuthenticationError, AuthService
from biocore.auth.invitation_service import InvitationError, InvitationService
from biocore.auth.module_launch_service import (
    InvalidReturnUrl,
    ModuleAccessDenied,
    ModuleLaunchService,
    ProjectAccessDenied,
    RedirectPolicy,
)
from biocore.auth.oidc import JwtIdentityVerifier
from biocore.auth.session_service import SessionError, SessionService
from biocore.config.settings import Settings
from biocore.repositories.central_auth import (
    SupabaseAuditWriter,
    SupabaseCentralAuthRepository,
)
from biocore.security.audit import AuditEvent, AuditService


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (AuthenticationError, SessionError)):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, (ModuleAccessDenied, ProjectAccessDenied, InvitationError)):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, (InvalidReturnUrl, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="BioCore authentication failed")


def _append_launch_code(return_to: str, code: str, module_code: str) -> str:
    parts = urlsplit(return_to)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["biocore_code"] = code
    query["biocore_module"] = module_code
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def build_services(settings: Settings | None = None) -> ApiServices:
    current = settings or Settings.from_environment()
    required = (
        current.supabase_url,
        current.supabase_service_role_key,
        current.oidc_issuer,
        current.oidc_audience,
        current.oidc_jwks_url,
    )
    if not all(required):
        raise RuntimeError("Central authentication environment is incomplete")
    client = create_client(
        str(current.supabase_url),
        str(current.supabase_service_role_key),
    )
    repository = SupabaseCentralAuthRepository(client)
    sessions = SessionService(
        repository,
        repository,
        session_ttl=timedelta(hours=current.auth_session_hours),
        module_session_ttl=timedelta(
            hours=current.auth_module_session_hours
        ),
    )
    verifier = JwtIdentityVerifier(
        provider=current.oidc_provider,
        issuer=str(current.oidc_issuer),
        audience=str(current.oidc_audience),
        jwks_url=str(current.oidc_jwks_url),
    )
    launches = ModuleLaunchService(
        sessions,
        repository,
        RedirectPolicy(current.auth_allowed_redirect_hosts),
        launch_ttl=timedelta(minutes=current.auth_launch_minutes),
    )
    return ApiServices(
        settings=current,
        directory=repository,
        auth=AuthService(verifier, repository, sessions),
        sessions=sessions,
        launches=launches,
        invitations=InvitationService(repository),
        audit=AuditService(SupabaseAuditWriter(client)),
    )


def create_app(
    services: ApiServices | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app = FastAPI(
        title="BioCore Central Auth API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
    )
    current_settings = settings or Settings.from_environment()
    if services is not None:
        app.state.services = services
    else:
        try:
            app.state.services = build_services(current_settings)
        except Exception:
            # Health remains available without exposing configuration details.
            app.state.services = None
    app.state.settings = current_settings

    @app.get("/health")
    def health(request: Request) -> dict[str, object]:
        return {
            "status": "ok",
            "central_auth_configured": isinstance(
                getattr(request.app.state, "services", None), ApiServices
            ),
        }

    @app.post("/v1/auth/exchange", response_model=SessionResponse)
    def exchange_identity(
        payload: AuthExchangeRequest,
        response: Response,
        authorization: str | None = Header(default=None),
        service_set: ApiServices = Depends(get_services),
    ) -> SessionResponse:
        identity_token = bearer_value(authorization)
        if not identity_token:
            raise HTTPException(401, "OIDC identity token is required")
        try:
            issued = service_set.auth.exchange(
                identity_token, payload.organization_id
            )
            response.set_cookie(
                service_set.settings.auth_cookie_name,
                issued.token,
                httponly=True,
                secure=service_set.settings.auth_cookie_secure,
                samesite="lax",
                max_age=service_set.settings.auth_session_hours * 3600,
                path="/",
            )
            return SessionResponse.from_issued(issued)
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/v1/session", response_model=SessionResponse)
    def current_session(
        token: str = Depends(central_session_token),
        service_set: ApiServices = Depends(get_services),
    ) -> SessionResponse:
        try:
            return SessionResponse.from_context(
                service_set.sessions.validate(token)
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/v1/session/revoke", status_code=204)
    def revoke_session(
        response: Response,
        token: str = Depends(central_session_token),
        service_set: ApiServices = Depends(get_services),
    ) -> None:
        try:
            service_set.sessions.revoke(token)
            response.delete_cookie(
                service_set.settings.auth_cookie_name,
                path="/",
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/v1/module-launch", response_model=ModuleLaunchResponse)
    def create_module_launch(
        payload: ModuleLaunchRequest,
        token: str = Depends(central_session_token),
        service_set: ApiServices = Depends(get_services),
    ) -> ModuleLaunchResponse:
        try:
            issued = service_set.launches.issue(
                token,
                payload.module_code,
                payload.return_to,
                payload.project_id,
            )
            return ModuleLaunchResponse(
                code=issued.code,
                module_code=issued.module_code,
                return_to=issued.return_to,
                expires_at=issued.expires_at,
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/v1/module-exchange", response_model=SessionResponse)
    def exchange_module_launch(
        payload: ModuleExchangeRequest,
        service_set: ApiServices = Depends(get_services),
    ) -> SessionResponse:
        try:
            return SessionResponse.from_issued(
                service_set.launches.exchange(
                    payload.code, payload.module_code
                )
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.get("/v1/authorize")
    def authorize_module(
        request: Request,
        module_code: str = Query(min_length=1, max_length=80),
        return_to: str = Query(min_length=1, max_length=2048),
        project_id: str | None = None,
        service_set: ApiServices = Depends(get_services),
    ) -> RedirectResponse:
        token = request.cookies.get(service_set.settings.auth_cookie_name)
        if not token:
            if not service_set.settings.auth_login_url:
                raise HTTPException(401, "Central login is not configured")
            callback = str(request.url)
            return RedirectResponse(
                f"{service_set.settings.auth_login_url}?"
                + urlencode({"return_to": callback}),
                status_code=303,
            )
        try:
            issued = service_set.launches.issue(
                token, module_code, return_to, project_id
            )
            return RedirectResponse(
                _append_launch_code(
                    issued.return_to, issued.code, issued.module_code
                ),
                status_code=303,
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/v1/invitations", response_model=InvitationCreateResponse)
    def create_invitation(
        payload: InvitationCreateRequest,
        token: str = Depends(central_session_token),
        service_set: ApiServices = Depends(get_services),
    ) -> InvitationCreateResponse:
        try:
            context = service_set.sessions.validate(token)
            issued = service_set.invitations.create(
                context,
                payload.email,
                payload.role,
                tuple(payload.project_ids),
            )
            if service_set.audit:
                service_set.audit.record(
                    AuditEvent(
                        event_code="invitation.created",
                        outcome="success",
                        organization_id=context.organization_id,
                        user_id=context.user_id,
                        session_id=context.session_id,
                        resource_type="invitation",
                        resource_id=issued.invitation.id,
                    )
                )
            return InvitationCreateResponse(
                token=issued.token,
                invitation_id=issued.invitation.id,
                organization_id=issued.invitation.organization_id,
                email=issued.invitation.email,
                role=issued.invitation.role,
                project_ids=list(issued.invitation.project_ids),
                expires_at=issued.invitation.expires_at,
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    @app.post("/v1/invitations/accept", status_code=204)
    def accept_invitation(
        payload: InvitationAcceptRequest,
        token: str = Depends(central_session_token),
        service_set: ApiServices = Depends(get_services),
    ) -> None:
        try:
            context = service_set.sessions.validate(token)
            user = service_set.directory.get_user(context.user_id)
            if user is None or not user.email_verified:
                raise InvitationError("Verified account email is required")
            service_set.invitations.accept(
                payload.token,
                user.id,
                user.email,
            )
        except Exception as exc:
            raise _http_error(exc) from exc

    return app


app = create_app()
