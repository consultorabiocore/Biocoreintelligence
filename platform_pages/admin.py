import streamlit as st

from biocore.components.module_access import enforce_module_access
from biocore.components.page_header import render_page_header
from biocore.domain.subscriptions import ModuleCode
from biocore.security.authorization import require_permission
from biocore.security.roles import Permission


context, _ = enforce_module_access(ModuleCode.PLATFORM_CORE)
require_permission(context, Permission.PLATFORM_ADMIN)
render_page_header(
    "Sistema",
    "Administración",
    "Gestiona organizaciones, membresías, roles, permisos y suscripciones.",
)
st.info(
    "La administración operativa se incorporará sobre los repositorios "
    "seguros. Las credenciales y claves de servicio nunca se mostrarán aquí."
)
