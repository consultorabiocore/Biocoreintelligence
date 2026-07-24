import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión ambiental",
    title="Informes",
    subtitle=(
        "Consulta informes y productos versionados junto con la evidencia que "
        "les dio origen."
    ),
)
st.info(
    "Los informes generales aparecerán cuando el repositorio de documentos se "
    "conecte con el espacio privado de la organización."
)
