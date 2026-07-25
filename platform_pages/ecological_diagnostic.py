import streamlit as st

from biocore.components.ecological_diagnostic_ui import (
    render_ecological_diagnostic_page,
)
from biocore.components.module_access import enforce_module_access
from biocore.components.public_ecological_diagnostic import (
    render_public_ecological_diagnostic,
)
from biocore.domain.subscriptions import ModuleCode, SubscriptionSnapshot
from biocore.security.authorization import UserContext


public_tab, client_tab = st.tabs(
    ["Diagnóstico gratuito", "Área de clientes"]
)

with public_tab:
    recorder = st.session_state.get("biocore_public_diagnostic_lead_recorder")
    render_public_ecological_diagnostic(
        recorder if callable(recorder) else None
    )

with client_tab:
    context = st.session_state.get("biocore_user_context")
    subscription = st.session_state.get("biocore_subscription")

    if not isinstance(context, UserContext) or not isinstance(
        subscription, SubscriptionSnapshot
    ):
        st.info(
            "El diagnóstico gratuito está disponible en la primera pestaña. "
            "Para acceder al historial y a las funciones privadas, recarga la "
            "plataforma o inicia sesión nuevamente."
        )
    else:
        enforce_module_access(ModuleCode.ECOLOGICAL_DIAGNOSTIC)
        render_ecological_diagnostic_page()
