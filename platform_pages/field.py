import streamlit as st

from biocore.components.module_access import (
    require_module_page,
)
from biocore.components.module_integration import render_module_integration
from biocore.config.brand import BRAND
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.FIELD,
    kicker="Ecosistema BioCore",
    title="BioCore MycoField",
    subtitle="Captura y organiza registros de hongos con continuidad desde la campaña.",
)
if BRAND.field_logo.is_file():
    st.image(str(BRAND.field_logo), width=180)
render_module_integration("field")
