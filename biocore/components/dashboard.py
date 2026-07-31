from datetime import date
from html import escape
from textwrap import dedent

import streamlit as st

from biocore.components.module_access import MODULE_DESCRIPTIONS, MODULE_LABELS
from biocore.components.page_header import render_page_header
from biocore.config.brand import BRAND, asset_data_uri
from biocore.domain.dashboard import DashboardSnapshot
from biocore.domain.subscriptions import (
    PLAN_LABELS,
    PLAN_MODULES,
    STATUS_LABELS,
    ModuleCode,
    SubscriptionSnapshot,
)
from biocore.security.authorization import UserContext
from biocore.security.roles import Permission
from biocore.services.subscriptions import can_access_module


DASHBOARD_MODULES = (
    ModuleCode.FIELD,
    ModuleCode.DARWINCHECK,
    ModuleCode.INTELLIGENCE,
    ModuleCode.REPORTS,
    ModuleCode.ACADEMY,
)

DASHBOARD_MODULE_LOGOS = {
    ModuleCode.FIELD: BRAND.field_logo,
    ModuleCode.DARWINCHECK: BRAND.darwincheck_logo,
    ModuleCode.INTELLIGENCE: BRAND.intelligence_logo,
    ModuleCode.REPORTS: BRAND.reports_logo,
    ModuleCode.ACADEMY: BRAND.academy_logo,
}

DASHBOARD_MODULE_PATHS = {
    ModuleCode.FIELD: "/field",
    ModuleCode.DARWINCHECK: "/darwincheck",
    ModuleCode.INTELLIGENCE: "/intelligence",
    ModuleCode.REPORTS: "/biocore_reports",
    ModuleCode.ACADEMY: "/academy",
}


def _html(value: str) -> str:
    """Keep Markdown from interpreting indented HTML fragments as code."""
    return "\n".join(line.lstrip() for line in value.splitlines())


def _metric_value(value: int | None) -> tuple[str, str]:
    if value is None:
        return "—", "Fuente aún no conectada"
    return str(value), "Datos de la organización"


def _stat_card(label: str, value: int | None) -> str:
    display_value, detail = _metric_value(value)
    return _html(
        dedent(
            f"""
        <article class="bc-stat">
        <span>{escape(label)}</span>
        <strong>{escape(display_value)}</strong>
        <small>{escape(detail)}</small>
        </article>
            """
        )
    )


def _empty_state(message: str) -> str:
    return f'<div class="bc-activity-empty">{escape(message)}</div>'


def module_display_state(
    context: UserContext,
    subscription: SubscriptionSnapshot,
    module_code: ModuleCode,
) -> tuple[str, str]:
    """Return an explainable UI state using the same service-level authorization."""
    enabled = can_access_module(
        context.user_id,
        context.organization_id,
        module_code,
        context=context,
        subscription=subscription,
    )
    if enabled:
        included = bool(
            subscription.subscription
            and module_code in PLAN_MODULES[subscription.subscription.plan]
        )
        return ("Incluido en tu plan" if included else "Activo"), "bc-status-active"
    if module_code is ModuleCode.ACADEMY:
        return "Próximamente", "bc-status-soon"
    return "No contratado", "bc-status-locked"


def _module_cards(
    context: UserContext,
    subscription: SubscriptionSnapshot,
) -> str:
    cards: list[str] = []
    for module_code in DASHBOARD_MODULES:
        label, class_name = module_display_state(context, subscription, module_code)
        module_name = MODULE_LABELS[module_code]
        logo_uri = asset_data_uri(DASHBOARD_MODULE_LOGOS[module_code])
        logo = (
            f'<img class="bc-dashboard-module-logo" src="{escape(logo_uri)}" '
            f'alt="Logo {escape(module_name)}">'
            if logo_uri
            else ""
        )
        action = ""
        if class_name == "bc-status-locked":
            action_url = BRAND.demo_request_url(
                f"Activación de {module_name}"
            )
            action = (
                '<strong class="bc-module-message">'
                "Módulo no incluido en tu plan"
                "</strong>"
                f'<a href="{escape(action_url)}">Consultar activación</a>'
            )
        elif class_name == "bc-status-soon":
            action = '<span class="bc-module-message">Lanzamiento gradual</span>'
        else:
            action = (
                f'<a href="{escape(DASHBOARD_MODULE_PATHS[module_code])}" '
                'target="_self">Abrir módulo →</a>'
            )
        cards.append(
            f"""
            <article class="bc-dashboard-module">
                <div class="bc-dashboard-module-brand">
                    {logo}
                    <span class="bc-module-status {class_name}">{escape(label)}</span>
                </div>
                <h3>{escape(module_name)}</h3>
                <p>{escape(MODULE_DESCRIPTIONS[module_code])}</p>
                {action}
            </article>
            """
        )
    return "".join(cards)


def render_private_dashboard(
    context: UserContext,
    subscription: SubscriptionSnapshot,
    dashboard: DashboardSnapshot,
) -> None:
    render_page_header(
        "Panel de la organización",
        "Bienvenida a BioCore",
        (
            f"{subscription.organization_name} · Consulta el estado de la operación "
            "ambiental y las actividades que requieren atención."
        ),
    )

    plan_label = "Por configurar"
    plan_state = "Sin suscripción activa"
    renewal = "A convenir"
    if subscription.subscription:
        item = subscription.subscription
        plan_label = PLAN_LABELS[item.plan]
        plan_state = STATUS_LABELS[item.status]
        renewal = (
            item.renews_on.strftime("%d/%m/%Y") if item.renews_on else "A convenir"
        )

    st.markdown(
        _html(
            dedent(
                f"""
        <div class="bc-metadata-strip">
            <div><small>Organización</small><strong>{escape(subscription.organization_name)}</strong></div>
            <div><small>Plan</small><strong>{escape(plan_label)}</strong></div>
            <div><small>Estado</small><strong>{escape(plan_state)}</strong></div>
            <div><small>Renovación</small><strong>{escape(renewal)}</strong></div>
            <div><small>Módulos habilitados</small><strong>{len(subscription.enabled_modules)}</strong></div>
        </div>
        <div class="bc-stat-grid">
            {_stat_card("Proyectos activos", dashboard.active_projects)}
            {_stat_card("Campañas realizadas", dashboard.completed_campaigns)}
            {_stat_card("Campañas pendientes", dashboard.upcoming_campaigns)}
            {_stat_card("Informes disponibles", dashboard.new_reports)}
            {_stat_card("Registros validados", dashboard.validated_records)}
            {_stat_card("Alertas activas", dashboard.alerts)}
        </div>
                """
            )
        ),
        unsafe_allow_html=True,
    )

    quick, plan = st.columns([1.2, 0.8], gap="large")
    with quick:
        st.subheader("Accesos rápidos")
        action_columns = st.columns(2)
        with action_columns[0]:
            st.page_link(
                "platform_pages/projects.py",
                label="Ver proyectos",
                icon=":material/folder_open:",
                use_container_width=True,
            )
            campaign_label = (
                "Crear campaña"
                if context.has_permission(Permission.CAMPAIGNS_WRITE)
                else "Ver campañas"
            )
            st.page_link(
                "platform_pages/campaigns.py",
                label=campaign_label,
                icon=":material/calendar_month:",
                use_container_width=True,
            )
            st.page_link(
                "platform_pages/reports.py",
                label="Abrir informes",
                icon=":material/description:",
                use_container_width=True,
            )
        with action_columns[1]:
            st.page_link(
                "platform_pages/maps.py",
                label="Ver mapa",
                icon=":material/map:",
                use_container_width=True,
            )
            st.page_link(
                "platform_pages/campaigns.py",
                label="Comparar campañas",
                icon=":material/compare_arrows:",
                use_container_width=True,
            )
            st.page_link(
                "platform_pages/intelligence.py",
                label="Abrir BioCore Intelligence",
                icon=":material/monitoring:",
                use_container_width=True,
            )

    with plan:
        st.subheader("Suscripción")
        if not subscription.subscription:
            st.info("La suscripción principal aún no está configurada.")
            st.link_button(
                "Solicitar activación de BioCore",
                BRAND.demo_request_url("Activación de suscripción BioCore"),
                type="primary",
                use_container_width=True,
            )
        else:
            item = subscription.subscription
            st.markdown(
                _html(
                    dedent(
                        f"""
                <section class="bc-private-card">
                    <h3>{escape(PLAN_LABELS[item.plan])}</h3>
                    <p>Estado: <strong>{escape(STATUS_LABELS[item.status])}</strong></p>
                    <p>Renovación: <strong>{escape(renewal)}</strong></p>
                </section>
                        """
                    )
                ),
                unsafe_allow_html=True,
            )
            if item.storage_limit_gb > 0:
                usage_ratio = min(
                    subscription.usage.storage_used_gb / item.storage_limit_gb,
                    1.0,
                )
                st.progress(
                    usage_ratio,
                    text=(
                        f"Almacenamiento: {subscription.usage.storage_used_gb:.1f} "
                        f"de {item.storage_limit_gb:.0f} GB"
                    ),
                )
            if item.renews_on and item.renews_on < date.today():
                st.warning("La fecha de renovación requiere revisión.")

    st.subheader("Actividad reciente")
    if dashboard.activities:
        for activity in dashboard.activities:
            st.markdown(
                f"**{activity.title}**  \n{activity.detail} · "
                f"{activity.occurred_at.strftime('%d/%m/%Y %H:%M')}"
            )
    else:
        st.markdown(
            _empty_state(
                "La actividad aparecerá aquí cuando proyectos, campañas e informes "
                "estén conectados. No se muestran datos demostrativos en el espacio privado."
            ),
            unsafe_allow_html=True,
        )

    project_column, campaign_column, report_column = st.columns(3, gap="medium")
    with project_column:
        st.subheader("Proyectos recientes")
        if dashboard.recent_projects:
            for project in dashboard.recent_projects:
                st.markdown(
                    f"**{project.name}**  \n{project.client} · "
                    f"Última campaña: {project.last_campaign} · {project.status}"
                )
        else:
            st.markdown(
                _empty_state("Aún no hay proyectos conectados para esta organización."),
                unsafe_allow_html=True,
            )
    with campaign_column:
        st.subheader("Próximas campañas")
        if dashboard.upcoming_campaign_items:
            for campaign in dashboard.upcoming_campaign_items:
                st.markdown(
                    f"**{campaign.station}**  \n{campaign.project_name} · "
                    f"{campaign.scheduled_for.strftime('%d/%m/%Y')} · "
                    f"{campaign.responsible} · {campaign.status}"
                )
        else:
            st.markdown(
                _empty_state("No hay campañas programadas en la fuente conectada."),
                unsafe_allow_html=True,
            )
    with report_column:
        st.subheader("Informes recientes")
        if dashboard.recent_reports:
            for report in dashboard.recent_reports:
                st.markdown(
                    f"**{report.name}**  \nVersión {report.version} · "
                    f"{report.published_at.strftime('%d/%m/%Y')} · {report.status}"
                )
        else:
            st.markdown(
                _empty_state("Los informes publicados aparecerán en esta sección."),
                unsafe_allow_html=True,
            )

    st.subheader("Módulos BioCore")
    st.markdown(
        _html(
            f'<div class="bc-dashboard-modules">{_module_cards(context, subscription)}</div>'
        ),
        unsafe_allow_html=True,
    )
