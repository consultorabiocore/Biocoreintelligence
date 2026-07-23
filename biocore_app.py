"""Gradual BioCore entrypoint; the legacy application remains in app.py."""
import streamlit as st
from supabase import create_client

from biocore.config.navigation import pages_for
from biocore.config.settings import Settings
from biocore.repositories.memberships import (
    IdentityNotProvisionedError,
    OrganizationSelectionRequired,
    SupabaseMembershipResolver,
)
from biocore.security.identity import AuthenticatedIdentity


st.set_page_config(page_title="BioCore", layout="wide")


if not st.user.is_logged_in:
    st.title("BioCore")
    st.button("Iniciar sesión", on_click=st.login, use_container_width=True)
    st.stop()


@st.cache_resource
def membership_resolver() -> SupabaseMembershipResolver:
    settings = Settings.from_environment()
    connection = st.secrets.get("connections", {}).get("supabase", {})
    supabase_url = settings.supabase_url or connection.get("url")
    service_role_key = settings.supabase_service_role_key or st.secrets.get(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    if not supabase_url or not service_role_key:
        raise RuntimeError("Supabase server credentials are not configured")
    client = create_client(supabase_url, service_role_key)
    return SupabaseMembershipResolver(client)


identity = AuthenticatedIdentity.from_oidc_claims(st.user.to_dict())
selected_organization = st.session_state.get("organization_id")

try:
    context = membership_resolver().resolve_context(identity, selected_organization)
except OrganizationSelectionRequired as selection:
    organization_id = st.selectbox("Selecciona una organización", selection.organization_ids)
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


with st.sidebar:
    st.caption(identity.email or identity.subject)
    st.button("Cerrar sesión", on_click=st.logout, use_container_width=True)

navigation = {
    section: [st.Page(item.path, title=item.title) for item in items]
    for section, items in pages_for(context).items()
}
st.navigation(navigation).run()
