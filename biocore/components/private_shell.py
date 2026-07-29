from html import escape

import streamlit as st

from biocore.components.styles import PRIVATE_STYLES
from biocore.config.brand import BRAND, available_logo
from biocore.domain.subscriptions import PLAN_LABELS, STATUS_LABELS, SubscriptionSnapshot
from biocore.security.identity import AuthenticatedIdentity
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


ROLE_LABELS: dict[Role, str] = {
    Role.SUPERADMIN: "Superadministración",
    Role.BIOCORE_ADMIN: "Administración BioCore",
    Role.BIOCORE_SPECIALIST: "Especialista BioCore",
    Role.CLIENT_ADMIN: "Administración cliente",
    Role.CLIENT_EDITOR: "Edición cliente",
    Role.CLIENT_READER: "Consulta cliente",
}


def _primary_role(context: UserContext) -> str:
    ordered_roles = (
        Role.SUPERADMIN,
        Role.BIOCORE_ADMIN,
        Role.BIOCORE_SPECIALIST,
        Role.CLIENT_ADMIN,
        Role.CLIENT_EDITOR,
        Role.CLIENT_READER,
    )
    for role in ordered_roles:
        if role in context.roles:
            return ROLE_LABELS[role]
    return "Usuario BioCore"


def render_private_shell(
    identity: AuthenticatedIdentity,
    context: UserContext,
    subscription: SubscriptionSnapshot,
    *,
    logout_callback=st.logout,
) -> None:
    st.markdown(PRIVATE_STYLES, unsafe_allow_html=True)
    logo = available_logo(BRAND.compact_logo, BRAND.master_logo)
    if logo:
        st.logo(str(logo), size="large")

    plan_label = "Plan por configurar"
    plan_state = "Acceso administrativo" if Role.SUPERADMIN in context.roles else "Sin suscripción activa"
    if subscription.subscription:
        plan_label = PLAN_LABELS[subscription.subscription.plan]
        plan_state = STATUS_LABELS[subscription.subscription.status]

    with st.sidebar:
        st.markdown(
            f"""
            <div class="bc-workspace-card">
                <strong>{escape(subscription.organization_name)}</strong>
                <span>{escape(plan_state)}</span>
                <span class="bc-plan-pill">{escape(plan_label)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown(
            f"""
            <div class="bc-account-card">
                <strong>{escape(identity.display_name or "Cuenta BioCore")}</strong>
                <span>{escape(identity.email or "Correo no disponible")}</span>
                <span>{escape(_primary_role(context))}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Cerrar sesión",
            on_click=logout_callback,
            use_container_width=True,
            type="secondary",
        )
