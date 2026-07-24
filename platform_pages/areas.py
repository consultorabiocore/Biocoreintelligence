import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión ambiental",
    title="Áreas de estudio",
    subtitle=(
        "Organiza polígonos, ubicaciones y antecedentes geoespaciales bajo el "
        "proyecto y la organización correspondientes."
    ),
)
st.info(
    "Las áreas aparecerán cuando el repositorio geoespacial se conecte. "
    "Esta vista no presenta datos demostrativos como si fueran del cliente."
)
