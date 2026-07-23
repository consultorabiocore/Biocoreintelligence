import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.config.brand import BRAND
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.REPORTS,
    kicker="Resultados",
    title="BioCore Reports",
    subtitle=(
        "Consulta informes y productos versionados junto con la evidencia que "
        "les dio origen."
    ),
)
if BRAND.reports_logo.is_file():
    st.image(str(BRAND.reports_logo), width=180)
st.info(
    "Los informes aparecerán cuando el repositorio de documentos se conecte "
    "con el espacio privado de la organización."
)
