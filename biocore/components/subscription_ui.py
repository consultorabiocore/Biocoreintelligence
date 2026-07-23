from html import escape

import streamlit as st

from biocore.components.module_access import (
    MODULE_DESCRIPTIONS,
    MODULE_LABELS,
    current_platform_state,
)
from biocore.components.page_header import render_page_header
from biocore.config.brand import BRAND
from biocore.domain.subscriptions import (
    PLAN_LABELS,
    STATUS_LABELS,
    ModuleCode,
)
from biocore.services.subscriptions import user_can_access_module


def render_subscription_page() -> None:
    context, snapshot = current_platform_state()
    render_page_header(
        "Cuenta de la organización",
        "Suscripción BioCore",
        (
            "La organización mantiene una suscripción principal y puede ampliar "
            "sus capacidades mediante módulos o accesos incluidos por proyecto."
        ),
    )

    if not snapshot.data_available:
        st.warning(
            "Los datos de suscripción todavía no están disponibles. "
            "El acceso administrativo se mantiene mientras se completa la migración."
        )

    if not snapshot.subscription:
        st.markdown(
            """
            <section class="bc-module-lock">
                <span class="bc-module-lock-badge">Configuración pendiente</span>
                <h3>La organización todavía no tiene un plan registrado</h3>
                <p>
                    Configura una suscripción principal para definir límites,
                    renovación, soporte y módulos habilitados.
                </p>
            </section>
            """,
            unsafe_allow_html=True,
        )
        st.link_button("Hablar con BioCore", BRAND.demo_request_url())
        return

    item = snapshot.subscription
    first, second, third = st.columns(3)
    first.metric("Plan", PLAN_LABELS[item.plan])
    second.metric("Estado", STATUS_LABELS[item.status])
    third.metric(
        "Renovación",
        item.renews_on.strftime("%d/%m/%Y") if item.renews_on else "A convenir",
    )

    limits = st.columns(4)
    limits[0].metric("Usuarios", f"{snapshot.usage.users_used} / {item.user_limit}")
    limits[1].metric("Proyectos", f"{snapshot.usage.projects_used} / {item.project_limit}")
    limits[2].metric(
        "Almacenamiento",
        f"{snapshot.usage.storage_used_gb:.1f} / {item.storage_limit_gb:.0f} GB",
    )
    limits[3].metric("Soporte", item.support_level.title())


def render_modules_page() -> None:
    context, snapshot = current_platform_state()
    render_page_header(
        "Capacidades contratadas",
        "Módulos BioCore",
        (
            "Revisa qué capacidades están habilitadas para la organización y "
            "cuáles pueden contratarse como complemento."
        ),
    )

    modules = (
        ModuleCode.FIELD,
        ModuleCode.DARWINCHECK,
        ModuleCode.INTELLIGENCE,
        ModuleCode.SATELLITE,
        ModuleCode.LIDAR,
        ModuleCode.REPORTS,
        ModuleCode.ACADEMY,
        ModuleCode.API_ACCESS,
    )
    for row_start in range(0, len(modules), 2):
        columns = st.columns(2, gap="medium")
        for column, module_code in zip(columns, modules[row_start : row_start + 2]):
            enabled = user_can_access_module(
                context.user_id,
                context.organization_id,
                module_code,
                context=context,
                subscription=snapshot,
            )
            with column:
                badge = "Habilitado" if enabled else "No incluido"
                st.markdown(
                    f"""
                    <section class="bc-private-card">
                        <div class="bc-module-lock-badge">{escape(badge)}</div>
                        <h3>{escape(MODULE_LABELS[module_code])}</h3>
                        <p>{escape(MODULE_DESCRIPTIONS[module_code])}</p>
                    </section>
                    """,
                    unsafe_allow_html=True,
                )
                if not enabled:
                    st.link_button(
                        "Consultar activación",
                        BRAND.demo_request_url(
                            f"Consulta de activación: {MODULE_LABELS[module_code]}"
                        ),
                        use_container_width=True,
                    )
