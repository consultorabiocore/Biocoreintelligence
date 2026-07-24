import streamlit as st

from biocore.components.module_access import (
    render_module_placeholder,
    require_module_page,
)
from biocore.config.brand import BRAND, available_logo
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.DARWINCHECK,
    kicker="Ecosistema BioCore",
    title="DarwinCheck",
    subtitle=(
        "Valida consistencia, calidad y trazabilidad antes de usar los datos "
        "en análisis e informes."
    ),
)
logo = available_logo(BRAND.darwincheck_logo)
if logo:
    st.image(str(logo), width=180)
render_module_placeholder(ModuleCode.DARWINCHECK)
