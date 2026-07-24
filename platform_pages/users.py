import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Cuenta",
    title="Usuarios",
    subtitle="Consulta los accesos asociados a tu organización y sus roles.",
)
st.info(
    "La administración autoservicio de usuarios se habilitará en una siguiente "
    "etapa. Los accesos actuales continúan gestionándose con el modelo de "
    "membresías existente."
)
