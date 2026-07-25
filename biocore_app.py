"""Public website and authenticated BioCore platform entrypoint."""

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
from biocore.repositories.subscriptions import SupabaseSubscriptionRepository
from biocore.security.identity import AuthenticatedIdentity
from biocore.services.subscriptions import SubscriptionService
from biocore.services.ecological_diagnostics import EcologicalDiagnosticService
from biocore.services.public_diagnostic_leads import save_public_lead


st.set_page_config(
    page_title="BioCore | Inteligencia ecológica",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="auto",
)


def _start_login() -> None:
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


is_logged_in = bool(getattr(st.user, "is_logged_in", False))

if not is_logged_in:
    if st.query_params.get("diagnostico") == "publico":
        render_public_ecological_diagnostic(record_public_diagnostic_lead)
        st.stop()
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


identity = AuthenticatedIdentity.from_oidc_claims(st.user.to_dict())
selected_organization = st.session_state.get("organization_id")

try:
    context = membership_resolver().resolve_context(identity, selected_organization)
except OrganizationSelectionRequired as selection:
    organization_id = st.selectbox(
        "Selecciona una organización",
        selection.organization_ids,
    )
    if st.button("Continuar", type="primary"):
        st.session_state["organization_id"] = organization_id
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
st.session_state["biocore_identity"] = identity
st.session_state["biocore_user_context"] = context
st.session_state["biocore_subscription"] = subscription
st.session_state["biocore_ecological_diagnostic_service"] = (
    ecological_diagnostic_service()
)

render_private_shell(identity, context, subscription)

navigation = {
    section: [
        st.Page(item.path, title=item.title, default=item.title == "Inicio")
        for item in items
    ]
    for section, items in pages_for(context, subscription).items()
}
st.navigation(navigation).run()
