import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión geoespacial",
    title="Mapas",
    subtitle=(
        "Consulta áreas de estudio, capas y resultados vinculados a proyectos "
        "y campañas."
    ),
)
st.info(
    "El visor se conectará cuando exista un repositorio geoespacial autorizado "
    "para esta organización."
)
