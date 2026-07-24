import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Cuenta",
    title="Configuración",
    subtitle="Revisa las preferencias del espacio privado de tu organización.",
)
st.info(
    "Las preferencias editables se incorporarán sin alterar la autenticación ni "
    "la configuración técnica del servidor."
)
