import streamlit as st

from biocore.components.module_access import (
    render_module_placeholder,
    require_module_page,
)
from biocore.components.module_integration import render_module_integration
from biocore.config.brand import BRAND, available_logo
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.INTELLIGENCE,
    kicker="Ecosistema BioCore",
    title="BioCore Intelligence",
    subtitle=(
        "Analítica científica y capacidades geoespaciales especializadas, "
        "conectadas al historial de la organización."
    ),
)
logo = available_logo(BRAND.intelligence_logo)
if logo:
    st.image(str(logo), width=180)
render_module_placeholder(ModuleCode.INTELLIGENCE)
st.subheader("Herramientas científicas conectadas")
render_module_integration("geot_radar")
