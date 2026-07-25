import streamlit as st

from biocore.components.ecological_diagnostic_ui import (
    render_ecological_diagnostic_page,
)
from biocore.components.module_access import enforce_module_access
from biocore.components.public_ecological_diagnostic import (
    render_public_ecological_diagnostic,
)
from biocore.domain.subscriptions import ModuleCode


enforce_module_access(ModuleCode.ECOLOGICAL_DIAGNOSTIC)

public_tab, client_tab = st.tabs(
    ["Diagnóstico gratuito", "Área de clientes"]
)

with public_tab:
    recorder = st.session_state.get("biocore_public_diagnostic_lead_recorder")
    render_public_ecological_diagnostic(
        recorder if callable(recorder) else None
    )

with client_tab:
    render_ecological_diagnostic_page()
