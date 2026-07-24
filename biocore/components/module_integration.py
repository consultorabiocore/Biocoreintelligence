from collections.abc import Mapping
from html import escape

import streamlit as st

from biocore.config.integrations import ExternalApplication, external_applications
from biocore.config.settings import Settings


def configured_external_applications() -> dict[str, ExternalApplication]:
    """Resolve deploy-time URLs while keeping secrets out of rendered HTML."""
    configured: Mapping[str, object] = st.secrets.get("integrations", {})
    return external_applications(Settings.from_environment(), configured)


def render_external_application(
    application: ExternalApplication,
    *,
    pending_message: str | None = None,
) -> None:
    status_class = (
        "bc-integration-ready"
        if application.is_configured
        else "bc-integration-pending"
    )
    status_label = (
        "Aplicación conectada"
        if application.is_configured
        else "Conexión pendiente"
    )
    st.markdown(
        f"""
        <section class="bc-integration-card">
            <span class="bc-integration-status {status_class}">
                {escape(status_label)}
            </span>
            <h3>{escape(application.label)}</h3>
            <p>{escape(application.description)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    if application.url:
        st.link_button(
            f"Abrir {application.label}",
            application.url,
            type="primary",
            use_container_width=False,
        )
        st.caption(
            "Se abre como aplicación externa. En esta primera integración no "
            "se comparte automáticamente la sesión ni se transfieren datos."
        )
    else:
        st.info(
            pending_message
            or (
                "El módulo está autorizado, pero BioCore aún debe configurar "
                "la URL de producción para habilitar su apertura."
            )
        )


def render_module_integration(application_code: str) -> None:
    applications = configured_external_applications()
    render_external_application(applications[application_code])
