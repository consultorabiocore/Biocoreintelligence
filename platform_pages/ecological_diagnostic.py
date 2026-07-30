import streamlit as st

from biocore.components.ecological_diagnostic_ui import (
    render_ecological_diagnostic_page,
)
from biocore.components.module_access import enforce_module_access
from biocore.components.public_ecological_diagnostic import (
    render_public_ecological_diagnostic,
)
from biocore.config.brand import BRAND
from biocore.domain.subscriptions import ModuleCode, SubscriptionSnapshot
from biocore.security.authorization import UserContext


def _service_card(
    *,
    label: str,
    title: str,
    description: str,
    included: tuple[str, ...],
    excluded: tuple[str, ...],
    button_label: str,
    subject: str,
) -> None:
    st.markdown(f"### {title}")
    st.caption(label)
    st.write(description)

    left, right = st.columns(2)
    with left:
        st.markdown("#### Incluye")
        for item in included:
            st.markdown(f"✓ {item}")
    with right:
        st.markdown("#### No incluye")
        for item in excluded:
            st.markdown(f"— {item}")

    st.info(
        "BioCore revisará la solicitud antes de confirmar alcance, plazo y valor. "
        "No se realiza ningún cobro desde esta página."
    )
    st.link_button(
        button_label,
        BRAND.demo_request_url(subject),
        use_container_width=True,
    )


initial_tab, professional_tab, integral_tab, client_tab = st.tabs(
    [
        "Diagnóstico inicial",
        "Diagnóstico profesional",
        "Diagnóstico integral",
        "Área de clientes",
    ]
)

with initial_tab:
    recorder = st.session_state.get("biocore_public_diagnostic_lead_recorder")
    render_public_ecological_diagnostic(
        recorder if callable(recorder) else None
    )

with professional_tab:
    _service_card(
        label="Servicio pagado · revisión humana",
        title="Diagnóstico Profesional BioCore",
        description=(
            "Una profesional revisa los archivos y antecedentes del proyecto para "
            "determinar qué información sirve, qué brechas existen y cuál debería "
            "ser el siguiente paso."
        ),
        included=(
            "Revisión de informes, planillas, mapas y fotografías entregadas.",
            "Evaluación de vigencia, cobertura, orden y trazabilidad.",
            "Identificación y priorización de brechas.",
            "Informe profesional breve.",
            "Reunión de explicación de resultados.",
            "Recomendación del servicio siguiente.",
        ),
        excluded=(
            "Campaña de terreno.",
            "Identificación taxonómica nueva.",
            "Confirmación de presencia o ausencia de especies.",
            "Evaluación de impactos o pronunciamiento normativo.",
        ),
        button_label="Solicitar cotización del diagnóstico profesional",
        subject="Cotización Diagnóstico Profesional BioCore",
    )

with integral_tab:
    _service_card(
        label="Servicio avanzado · cotización personalizada",
        title="Diagnóstico Integral BioCore",
        description=(
            "Revisión profunda para proyectos que necesitan transformar antecedentes "
            "dispersos en una planificación técnica, cartográfica y operativa."
        ),
        included=(
            "Todo lo contemplado en el Diagnóstico Profesional.",
            "Revisión cartográfica y territorial ampliada.",
            "Análisis de antecedentes espaciales disponibles.",
            "Definición preliminar de componentes y prioridades.",
            "Diseño preliminar de campaña o monitoreo.",
            "Cronograma y propuesta de etapas posteriores.",
        ),
        excluded=(
            "Ejecución automática de campañas de terreno.",
            "Permisos o certificaciones emitidos por autoridades.",
            "Resultados taxonómicos sin evidencias suficientes.",
            "Servicios adicionales no incluidos en la cotización aprobada.",
        ),
        button_label="Solicitar propuesta de diagnóstico integral",
        subject="Propuesta Diagnóstico Integral BioCore",
    )

with client_tab:
    context = st.session_state.get("biocore_user_context")
    subscription = st.session_state.get("biocore_subscription")

    if not isinstance(context, UserContext) or not isinstance(
        subscription, SubscriptionSnapshot
    ):
        st.info(
            "Esta sección es para organizaciones con sesión y acceso habilitado. "
            "El diagnóstico inicial y la información de servicios están disponibles "
            "en las pestañas anteriores."
        )
    else:
        enforce_module_access(ModuleCode.ECOLOGICAL_DIAGNOSTIC)
        render_ecological_diagnostic_page()
