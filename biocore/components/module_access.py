from html import escape

import streamlit as st

from biocore.components.page_header import render_page_header
from biocore.config.brand import BRAND
from biocore.domain.subscriptions import ModuleCode, SubscriptionSnapshot
from biocore.security.authorization import UserContext
from biocore.services.subscriptions import user_can_access_module


MODULE_LABELS: dict[ModuleCode, str] = {
    ModuleCode.PLATFORM_CORE: "Plataforma BioCore",
    ModuleCode.FIELD: "BioCore Field",
    ModuleCode.DARWINCHECK: "DarwinCheck",
    ModuleCode.INTELLIGENCE: "BioCore Intelligence",
    ModuleCode.SATELLITE: "Monitoreo satelital",
    ModuleCode.LIDAR: "LiDAR",
    ModuleCode.REPORTS: "BioCore Reports",
    ModuleCode.ACADEMY: "BioCore Academy",
    ModuleCode.API_ACCESS: "API BioCore",
    ModuleCode.ECOLOGICAL_DIAGNOSTIC: "Diagnóstico Ecológico Digital",
    ModuleCode.ECOLOGICAL_DIAGNOSTIC_DETAILED: "Diagnóstico ecológico detallado",
}


MODULE_DESCRIPTIONS: dict[ModuleCode, str] = {
    ModuleCode.PLATFORM_CORE: "Gestión central de proyectos, campañas e historial ambiental.",
    ModuleCode.FIELD: "Captura y organización de datos provenientes de terreno.",
    ModuleCode.DARWINCHECK: "Validación, consistencia y gobierno de calidad de datos.",
    ModuleCode.INTELLIGENCE: "Analítica ambiental y capacidades científicas especializadas.",
    ModuleCode.SATELLITE: "Monitoreo y comparación temporal con información satelital.",
    ModuleCode.LIDAR: "Procesamiento y análisis de información LiDAR.",
    ModuleCode.REPORTS: "Informes, mapas y productos conectados con la evidencia.",
    ModuleCode.ACADEMY: "Cursos, capacitación y recursos profesionales.",
    ModuleCode.API_ACCESS: "Integraciones seguras con sistemas externos.",
    ModuleCode.ECOLOGICAL_DIAGNOSTIC: (
        "Orientación preliminar sobre información de flora, vegetación, "
        "hongos y líquenes."
    ),
    ModuleCode.ECOLOGICAL_DIAGNOSTIC_DETAILED: (
        "Evaluación ampliada con antecedentes e informe sujeto a revisión."
    ),
}


def current_platform_state() -> tuple[UserContext, SubscriptionSnapshot]:
    context = st.session_state.get("biocore_user_context")
    subscription = st.session_state.get("biocore_subscription")
    if not isinstance(context, UserContext) or not isinstance(
        subscription, SubscriptionSnapshot
    ):
        st.error("La sesión de plataforma no está disponible.")
        st.stop()
    return context, subscription


def module_is_enabled(module_code: ModuleCode) -> bool:
    context, subscription = current_platform_state()
    return user_can_access_module(
        context.user_id,
        context.organization_id,
        module_code,
        context=context,
        subscription=subscription,
    )


def enforce_module_access(
    module_code: ModuleCode,
) -> tuple[UserContext, SubscriptionSnapshot]:
    """Stop before a protected module operation can execute."""
    context, subscription = current_platform_state()
    if user_can_access_module(
        context.user_id,
        context.organization_id,
        module_code,
        context=context,
        subscription=subscription,
    ):
        return context, subscription

    st.markdown(
        f"""
        <section class="bc-module-lock">
            <span class="bc-module-lock-badge">Complemento disponible</span>
            <h3>Módulo no incluido en el plan actual</h3>
            <p>
                {escape(MODULE_LABELS[module_code])} puede activarse para esta
                organización sin crear una cuenta o suscripción separada.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "Consultar activación",
        BRAND.demo_request_url(
            f"Consulta de activación: {MODULE_LABELS[module_code]}"
        ),
        use_container_width=False,
    )
    st.stop()


def require_module_page(
    module_code: ModuleCode,
    *,
    kicker: str,
    title: str,
    subtitle: str,
) -> tuple[UserContext, SubscriptionSnapshot]:
    render_page_header(kicker, title, subtitle)
    return enforce_module_access(module_code)


def render_module_placeholder(module_code: ModuleCode) -> None:
    st.markdown(
        f"""
        <section class="bc-private-card">
            <h3>{escape(MODULE_LABELS[module_code])}</h3>
            <p>{escape(MODULE_DESCRIPTIONS[module_code])}</p>
            <p>
                El acceso está habilitado. La conexión con los servicios técnicos
                se incorporará sin trasladar reglas científicas a esta página.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
