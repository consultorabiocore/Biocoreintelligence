from datetime import date
from html import escape

import streamlit as st

from biocore.components.page_header import render_page_header
from biocore.domain.dashboard import DashboardSnapshot
from biocore.domain.subscriptions import (
    PLAN_LABELS,
    STATUS_LABELS,
    SubscriptionSnapshot,
)
from biocore.security.authorization import UserContext
from biocore.security.roles import Permission


def _metric_value(value: int | None) -> tuple[str, str]:
    if value is None:
        return "—", "Fuente aún no conectada"
    return str(value), "Datos de la organización"


def _stat_card(label: str, value: int | None) -> str:
    display_value, detail = _metric_value(value)
    return f"""
    <article class="bc-stat">
        <span>{escape(label)}</span>
        <strong>{escape(display_value)}</strong>
        <small>{escape(detail)}</small>
    </article>
    """


def render_private_dashboard(
    context: UserContext,
    subscription: SubscriptionSnapshot,
    dashboard: DashboardSnapshot,
) -> None:
    render_page_header(
        "Panel de la organización",
        f"Bienvenida a {subscription.organization_name}",
        (
            "Consulta el estado de la operación ambiental, los accesos de la "
            "organización y las actividades que requieren atención."
        ),
    )

    st.markdown(
        f"""
        <div class="bc-stat-grid">
            {_stat_card("Proyectos activos", dashboard.active_projects)}
            {_stat_card("Campañas realizadas", dashboard.completed_campaigns)}
            {_stat_card("Informes nuevos", dashboard.new_reports)}
            {_stat_card("Alertas", dashboard.alerts)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.2, 0.8], gap="large")
    with left:
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

    with right:
        st.subheader("Suscripción")
        if not subscription.subscription:
            st.info("La suscripción principal aún no está configurada.")
        else:
            item = subscription.subscription
            st.markdown(
                f"""
                <section class="bc-private-card">
                    <h3>{escape(PLAN_LABELS[item.plan])}</h3>
                    <p>Estado: <strong>{escape(STATUS_LABELS[item.status])}</strong></p>
                    <p>
                        Renovación:
                        <strong>{item.renews_on.strftime("%d/%m/%Y") if item.renews_on else "A convenir"}</strong>
                    </p>
                </section>
                """,
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
            """
            <div class="bc-activity-empty">
                La actividad aparecerá aquí cuando proyectos, campañas e informes
                estén conectados. No se muestran datos demostrativos dentro del
                espacio privado.
            </div>
            """,
            unsafe_allow_html=True,
        )
