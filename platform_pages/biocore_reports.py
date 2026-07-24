import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.config.brand import BRAND, available_logo
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.REPORTS,
    kicker="Módulos",
    title="BioCore Reports",
    subtitle=(
        "Genera productos especializados y conserva versiones conectadas con "
        "la evidencia que les dio origen."
    ),
)
logo = available_logo(BRAND.reports_logo)
if logo:
    st.image(str(logo), width=180)
st.info(
    "BioCore Reports está preparado para conectarse al repositorio documental "
    "sin duplicar los informes generales de la plataforma."
)
