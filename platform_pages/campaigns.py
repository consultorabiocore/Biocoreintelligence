import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión ambiental",
    title="Campañas",
    subtitle=(
        "Planifica, consulta y compara campañas sin perder la relación con el "
        "proyecto, los datos de terreno y los informes."
    ),
)
st.info(
    "La gestión de campañas está preparada para conectarse con sus servicios "
    "de dominio. Todavía no hay registros operativos en esta vista."
)
