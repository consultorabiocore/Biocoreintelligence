from html import escape
from textwrap import dedent

import streamlit as st

from biocore.components.module_access import MODULE_DESCRIPTIONS, MODULE_LABELS
from biocore.components.page_header import render_page_header
from biocore.config.brand import BRAND, asset_data_uri
from biocore.domain.dashboard import DashboardSnapshot, ProjectSummary
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

PROJECT_VIEW_KEY = "biocore_projects_view"
SELECTED_PROJECT_KEY = "biocore_selected_project_id"


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


def _project_card(project: ProjectSummary) -> str:
    progress = max(0, min(project.progress_percent, 100))
    return _html(
        dedent(
            f"""
        <article class="bc-project-overview">
            <div class="bc-project-overview-head">
                <div>
                    <small>{escape(project.code)} · {escape(project.status)}</small>
                    <h3>{escape(project.name)}</h3>
                    <p>{escape(project.client)}</p>
                </div>
                <strong>{progress}%</strong>
            </div>
            <div class="bc-project-progress" aria-label="Avance {progress}%">
                <span style="width: {progress}%"></span>
            </div>
            <dl>
                <div><dt>Etapa actual</dt><dd>{escape(project.current_stage)}</dd></div>
                <div><dt>Responsable</dt><dd>{escape(project.responsible_name)}</dd></div>
                <div><dt>Siguiente actividad</dt><dd>{escape(project.next_activity)}</dd></div>
                <div><dt>Actualizado</dt><dd>{project.updated_at.strftime('%d/%m/%Y')}</dd></div>
            </dl>
        </article>
            """
        )
    )


def _recommended_next_step(dashboard: DashboardSnapshot) -> tuple[str, str]:
    if not dashboard.projects_loaded:
        return (
            "Revisa la conexión de tus proyectos",
            "No pudimos confirmar el listado ahora. Tu información no se modificó; actualiza la página para intentarlo nuevamente.",
        )
    if not dashboard.recent_projects:
        return (
            "Crea tu primer proyecto ecológico",
            "Después podrás definir el área de estudio, organizar la campaña de terreno y reunir la evidencia en orden.",
        )
    project = dashboard.recent_projects[0]
    return (
        f"Continúa con {project.name}",
        f"Etapa actual: {project.current_stage}. Siguiente actividad: {project.next_activity}.",
    )


def _open_project(project_id: str) -> None:
    st.session_state[PROJECT_VIEW_KEY] = "detail"
    st.session_state[SELECTED_PROJECT_KEY] = project_id
    st.switch_page("platform_pages/projects.py")


def _create_project() -> None:
    st.session_state[PROJECT_VIEW_KEY] = "create"
    st.session_state.pop(SELECTED_PROJECT_KEY, None)
    st.switch_page("platform_pages/projects.py")


def render_private_dashboard(
    context: UserContext,
    subscription: SubscriptionSnapshot,
    dashboard: DashboardSnapshot,
) -> None:
    render_page_header(
        "Inicio",
        "Tus proyectos ecológicos",
        (
            f"{subscription.organization_name} · Gestiona proyectos de flora, "
            "vegetación, hongos y líquenes desde un solo lugar."
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
        <div class="bc-metadata-strip bc-metadata-strip-compact">
            <div><small>Organización</small><strong>{escape(subscription.organization_name)}</strong></div>
            <div><small>Plan</small><strong>{escape(plan_label)}</strong></div>
            <div><small>Estado del acceso</small><strong>{escape(plan_state)}</strong></div>
            <div><small>Renovación</small><strong>{escape(renewal)}</strong></div>
        </div>
                """
            )
        ),
        unsafe_allow_html=True,
    )

    next_title, next_copy = _recommended_next_step(dashboard)
    st.markdown(
        _html(
            dedent(
                f"""
        <section class="bc-guidance-card" aria-label="Siguiente acción recomendada">
            <small>Siguiente acción recomendada</small>
            <h2>{escape(next_title)}</h2>
            <p>{escape(next_copy)}</p>
        </section>
                """
            )
        ),
        unsafe_allow_html=True,
    )

    primary_actions = st.columns(3, gap="medium")
    with primary_actions[0]:
        if context.has_permission(Permission.PROJECTS_WRITE):
            st.button(
                "Crear proyecto",
                type="primary",
                use_container_width=True,
                on_click=_create_project,
            )
        else:
            st.page_link(
                "platform_pages/projects.py",
                label="Ver proyectos",
                icon=":material/folder_open:",
                use_container_width=True,
            )
    with primary_actions[1]:
        st.page_link(
            "platform_pages/projects.py",
            label="Mis proyectos",
            icon=":material/folder_open:",
            use_container_width=True,
        )
    with primary_actions[2]:
        st.page_link(
            "platform_pages/ecological_diagnostic.py",
            label="Diagnóstico ecológico",
            icon=":material/checklist:",
            use_container_width=True,
        )

    st.subheader("Mis proyectos")
    if not dashboard.projects_loaded:
        st.warning("No pudimos cargar tus proyectos en este momento.")
        st.info(
            "Tu información permanece guardada. Actualiza la página; si continúa, "
            "cierra sesión e ingresa nuevamente."
        )
    elif dashboard.recent_projects:
        for project in dashboard.recent_projects:
            st.markdown(_project_card(project), unsafe_allow_html=True)
            st.button(
                f"Abrir {project.code}",
                key=f"open_project_{project.id}",
                use_container_width=True,
                on_click=_open_project,
                args=(project.id,),
            )
    else:
        st.markdown(
            _empty_state(
                "Aún no hay proyectos. Crea el primero para organizar su objetivo, "
                "área de estudio, campañas y próximos pasos."
            ),
            unsafe_allow_html=True,
        )

    st.subheader("Estado del trabajo")
    st.markdown(
        _html(
            dedent(
                f"""
        <div class="bc-stat-grid bc-stat-grid-compact">
            {_stat_card("Proyectos activos", dashboard.active_projects)}
            {_stat_card("Próximas campañas", dashboard.upcoming_campaigns)}
            {_stat_card("Informes disponibles", dashboard.new_reports)}
        </div>
                """
            )
        ),
        unsafe_allow_html=True,
    )

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

    st.subheader("Herramientas especializadas")
    st.caption(
        "Ábrelas cuando una tarea del proyecto las necesite. Su estado depende "
        "de los permisos y del plan de tu organización."
    )
    st.markdown(
        _html(
            f'<div class="bc-dashboard-modules">{_module_cards(context, subscription)}</div>'
        ),
        unsafe_allow_html=True,
    )
