import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión ambiental",
    title="Proyectos",
    subtitle=(
        "Organiza áreas de estudio, equipos, campañas y productos bajo un "
        "mismo historial ambiental."
    ),
)
st.info(
    "El repositorio de proyectos se conectará a PostgreSQL/PostGIS en una "
    "siguiente integración. Esta vista no presenta datos de demostración."
)
