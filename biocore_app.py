"""Public website and authenticated BioCore platform entrypoint."""

from pathlib import Path
from typing import Any

import streamlit as st
from supabase import create_client

from biocore.components.private_shell import render_private_shell
from biocore.components.public_ecological_diagnostic import (
    render_public_ecological_diagnostic,
)
from biocore.components.public_landing_gateway import (
    render_public_landing_with_diagnostic_cta,
)
from biocore.config.navigation import pages_for
from biocore.config.settings import Settings
from biocore.repositories.memberships import (
    IdentityNotProvisionedError,
    OrganizationSelectionRequired,
    SupabaseMembershipResolver,
)
from biocore.repositories.ecological_diagnostics import (
    SupabaseEcologicalDiagnosticRepository,
)
from biocore.repositories.projects import SupabaseProjectRepository
from biocore.repositories.subscriptions import SupabaseSubscriptionRepository
from biocore.repositories.central_auth import SupabaseCentralAuthRepository
from biocore.repositories.darwincheck import SupabaseDarwinCheckRunRepository
from biocore.repositories.mycofield import SupabaseMycoFieldRepository
from biocore.repositories.intelligence import SupabaseIntelligenceRunRepository
from biocore.repositories.ecological_evidence import (
    SupabaseEcologicalEvidenceRepository,
)
from biocore.auth.session_service import SessionService
from biocore.modules.darwincheck.analyzer import (
    DarwinCheckAnalyzer,
    TaxonomyReference,
)
from biocore.platform_session import clear_platform_session, store_platform_session
from biocore.security.identity import AuthenticatedIdentity
from biocore.services.subscriptions import SubscriptionService
from biocore.services.ecological_diagnostics import EcologicalDiagnosticService
from biocore.services.projects import ProjectService
from biocore.services.darwincheck import DarwinCheckService
from biocore.services.mycofield import MycoFieldService
from biocore.services.intelligence import IntelligenceService
from biocore.services.ecological_evidence import EcologicalEvidenceService
from biocore.integrations.inaturalist import PublicINaturalistClient
from biocore.modules.intelligence.earth_engine import EarthEngineProvider
from biocore.services.public_diagnostic_leads import save_public_lead


st.set_page_config(
    page_title="BioCore | Inteligencia ecológica",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="auto",
)


def _start_login() -> None:
    requested_page = st.query_params.get("next")
    post_login_pages = {
        "mycofield": "BioCore MycoField",
        "darwincheck": "DarwinCheck",
        "intelligence": "BioCore Intelligence",
    }
    if requested_page in post_login_pages:
        st.session_state["biocore_post_login_page"] = post_login_pages[
            requested_page
        ]
    st.query_params.clear()
    st.login()


@st.cache_resource
def supabase_server_client() -> Any:
    """Create one trusted server-side client; never expose its key to a page."""
    settings = Settings.from_environment()
    connection = st.secrets.get("connections", {}).get("supabase", {})
    supabase_url = settings.supabase_url or connection.get("url")
    service_role_key = settings.supabase_service_role_key or st.secrets.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    if not supabase_url or not service_role_key:
        raise RuntimeError("Supabase server credentials are not configured")
    return create_client(supabase_url, service_role_key)


def record_public_diagnostic_lead(payload: dict[str, object]) -> str:
    """Persist a consented prospect without creating a client subscription."""
    return save_public_lead(supabase_server_client(), payload)


# The public diagnostic must remain available even when the browser already
# has an authenticated BioCore session. This also lets administrators test the
# prospect experience without logging out.
if st.query_params.get("diagnostico") == "publico":
    render_public_ecological_diagnostic(record_public_diagnostic_lead)
    st.stop()

is_logged_in = bool(getattr(st.user, "is_logged_in", False))

if not is_logged_in:
    if st.query_params.get("auth") == "login":
        _start_login()
        st.stop()
    render_public_landing_with_diagnostic_cta()
    st.stop()


@st.cache_resource
def membership_resolver() -> SupabaseMembershipResolver:
    return SupabaseMembershipResolver(supabase_server_client())


@st.cache_resource
def subscription_service() -> SubscriptionService:
    repository = SupabaseSubscriptionRepository(supabase_server_client())
    return SubscriptionService(repository)


@st.cache_resource
def ecological_diagnostic_service() -> EcologicalDiagnosticService:
    repository = SupabaseEcologicalDiagnosticRepository(supabase_server_client())
    return EcologicalDiagnosticService(repository)


@st.cache_resource
def project_service() -> ProjectService:
    repository = SupabaseProjectRepository(supabase_server_client())
    return ProjectService(repository)


@st.cache_resource
def darwincheck_service() -> DarwinCheckService:
    client = supabase_server_client()
    reference_path = (
        Path(__file__).parent
        / "biocore"
        / "modules"
        / "darwincheck"
        / "data"
        / "SIMBIO_Especies_2026-02-19.xlsx"
    )
    analyzer = DarwinCheckAnalyzer(TaxonomyReference(reference_path))
    return DarwinCheckService(
        SupabaseDarwinCheckRunRepository(client),
        SupabaseProjectRepository(client),
        analyzer,
    )


@st.cache_resource
def mycofield_service() -> MycoFieldService:
    client = supabase_server_client()
    return MycoFieldService(
        SupabaseMycoFieldRepository(client),
        SupabaseProjectRepository(client),
    )


@st.cache_resource
def intelligence_service() -> IntelligenceService:
    client = supabase_server_client()
    gee = st.secrets.get("gee", {})
    provider = EarthEngineProvider(gee.get("json") if gee else None)
    return IntelligenceService(
        SupabaseIntelligenceRunRepository(client),
        SupabaseProjectRepository(client),
        provider,
    )


@st.cache_resource
def ecological_evidence_service() -> EcologicalEvidenceService:
    client = supabase_server_client()
    return EcologicalEvidenceService(
        SupabaseEcologicalEvidenceRepository(client),
        SupabaseProjectRepository(client),
        PublicINaturalistClient(),
    )


@st.cache_resource
def central_auth_repository() -> SupabaseCentralAuthRepository:
    return SupabaseCentralAuthRepository(supabase_server_client())


@st.cache_resource
def central_session_service() -> SessionService:
    repository = central_auth_repository()
    return SessionService(repository, repository)


def _logout() -> None:
    token = st.session_state.get("biocore_central_session_token")
    if token:
        try:
            central_session_service().revoke(str(token))
        except Exception:
            # OIDC logout remains available during a migration outage.
            pass
    clear_platform_session(st.session_state)
    st.session_state.clear()
    st.logout()


identity = AuthenticatedIdentity.from_oidc_claims(st.user.to_dict())
selected_organization = st.session_state.get(
    "biocore_selected_organization_id"
) or st.session_state.get("organization_id")

try:
    context = membership_resolver().resolve_context(identity, selected_organization)
except OrganizationSelectionRequired as selection:
    organization_id = st.selectbox(
        "Selecciona una organización",
        selection.organization_ids,
    )
    if st.button("Continuar", type="primary"):
        st.session_state["organization_id"] = organization_id
        st.session_state["biocore_selected_organization_id"] = organization_id
        st.rerun()
    st.stop()
except IdentityNotProvisionedError:
    st.error("Tu cuenta no tiene una membresía activa en BioCore.")
    st.caption(
        "Identificador de alta (cópialo para que un administrador autorice tu cuenta):"
    )
    st.code(identity.subject, language=None)
    st.button("Cerrar sesión", on_click=st.logout)
    st.stop()
except RuntimeError:
    st.error("La autenticación de BioCore aún no está configurada en el servidor.")
    st.stop()

subscription = subscription_service().resolve_for(context)
settings = Settings.from_environment()
if settings.auth_mode in {"shadow", "optional", "required"}:
    try:
        if identity.email_verified and identity.email:
            central_auth_repository().mark_verified_oidc_identity(
                context.user_id,
                provider="google",
                subject=identity.subject,
                email=identity.email,
            )
        existing_token = st.session_state.get("biocore_central_session_token")
        if existing_token:
            central_context = central_session_service().validate(
                str(existing_token)
            )
            if central_context.organization_id != context.organization_id:
                central_session_service().revoke(
                    str(existing_token), reason="organization_switched"
                )
                issued_session = central_session_service().issue(
                    context.user_id,
                    context.organization_id,
                    auth_method="streamlit_oidc",
                )
                existing_token = issued_session.token
                central_context = issued_session.context
        else:
            issued_session = central_session_service().issue(
                context.user_id,
                context.organization_id,
                auth_method="streamlit_oidc",
            )
            existing_token = issued_session.token
            central_context = issued_session.context
        st.session_state["biocore_central_session_token"] = existing_token
        st.session_state["biocore_central_session_context"] = central_context
    except Exception:
        st.session_state.pop("biocore_central_session_token", None)
        st.session_state.pop("biocore_central_session_context", None)
        if settings.auth_mode == "required":
            st.error(
                "La sesión central de BioCore no está disponible. "
                "Intenta nuevamente en unos minutos."
            )
            st.stop()
store_platform_session(st.session_state, identity, context, subscription)
st.session_state["biocore_ecological_diagnostic_service"] = (
    ecological_diagnostic_service()
)
st.session_state["biocore_project_service"] = project_service()
st.session_state["biocore_darwincheck_service"] = darwincheck_service()
st.session_state["biocore_mycofield_service"] = mycofield_service()
st.session_state["biocore_intelligence_service"] = intelligence_service()
st.session_state["biocore_ecological_evidence_service"] = (
    ecological_evidence_service()
)
st.session_state["biocore_public_diagnostic_lead_recorder"] = (
    record_public_diagnostic_lead
)

render_private_shell(
    identity,
    context,
    subscription,
    logout_callback=_logout,
)

page_groups = pages_for(context, subscription)
requested_default_page = st.session_state.pop(
    "biocore_post_login_page", None
)
available_page_titles = {
    item.title for items in page_groups.values() for item in items
}
default_page_title = (
    requested_default_page
    if requested_default_page in available_page_titles
    else "Inicio"
)

navigation = {
    section: [
        st.Page(
            item.path,
            title=item.title,
            default=item.title == default_page_title,
        )
        for item in items
    ]
    for section, items in page_groups.items()
}
st.navigation(navigation).run()
