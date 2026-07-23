import streamlit as st

from biocore.components.module_access import (
    render_module_placeholder,
    require_module_page,
)
from biocore.config.brand import BRAND
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.ACADEMY,
    kicker="Ecosistema BioCore",
    title="BioCore Academy",
    subtitle=(
        "Capacitación y recursos profesionales vinculados con las capacidades "
        "de la plataforma."
    ),
)
if BRAND.academy_logo.is_file():
    st.image(str(BRAND.academy_logo), width=180)
render_module_placeholder(ModuleCode.ACADEMY)
