"""Native DarwinCheck experience inside the private BioCore shell."""

from __future__ import annotations

import logging

import pandas as pd
import plotly.express as px
import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.components.module_integration import configured_external_applications
from biocore.domain.projects import ProjectFilters
from biocore.domain.subscriptions import ModuleCode
from biocore.modules.darwincheck.analyzer import DarwinCheckValidationError
from biocore.modules.darwincheck.domain import DarwinCheckExecution
from biocore.modules.darwincheck.excel import DarwinCheckWorkbookError
from biocore.security.authorization import AuthorizationError
from biocore.security.roles import Permission
from biocore.services.darwincheck import (
    DarwinCheckProjectNotFound,
    DarwinCheckUploadError,
)


LOGGER = logging.getLogger(__name__)
EXECUTION_KEY = "biocore_darwincheck_execution"
EXPORT_KEY = "biocore_darwincheck_export"
FLASH_KEY = "biocore_darwincheck_flash"


context, subscription = require_module_page(
    ModuleCode.DARWINCHECK,
    kicker="Calidad y trazabilidad",
    title="DarwinCheck",
    subtitle=(
        "Revisa planillas de biodiversidad con la estructura Darwin Core/SMA, "
        "explica cada hallazgo y conserva el resultado dentro del proyecto."
    ),
)

service = st.session_state.get("biocore_darwincheck_service")
project_service = st.session_state.get("biocore_project_service")
if service is None or not callable(getattr(service, "analyze_upload", None)):
    st.error("DarwinCheck no está disponible en esta sesión.")
    st.info(
        "Actualiza la página. Si el problema continúa, cierra sesión e ingresa nuevamente."
    )
    st.stop()
if project_service is None or not callable(getattr(project_service, "list", None)):
    st.error("No pudimos conectar DarwinCheck con los proyectos.")
    st.info("Tu información no se modificó. Actualiza la página y vuelve a intentarlo.")
    st.stop()

can_run = context.has_permission(Permission.DARWINCHECK_WRITE)


def _friendly_error(error: Exception, *, operation: str) -> None:
    if isinstance(
        error,
        (
            DarwinCheckValidationError,
            DarwinCheckWorkbookError,
            DarwinCheckUploadError,
        ),
    ):
        st.error(str(error))
        st.caption("Corrige el archivo indicado y vuelve a ejecutar la revisión.")
        return
    if isinstance(error, AuthorizationError):
        st.warning("Tu rol permite consultar DarwinCheck, pero no ejecutar nuevas revisiones.")
        st.caption("Solicita acceso de edición a la administración de tu organización.")
        return
    if isinstance(error, DarwinCheckProjectNotFound):
        st.warning(str(error))
        st.caption("Selecciona nuevamente un proyecto de la organización activa.")
        return
    LOGGER.exception("DarwinCheck operation failed: %s", operation)
    st.error("No pudimos completar la operación de DarwinCheck.")
    st.info(
        "El detalle técnico quedó registrado. Actualiza la página y vuelve a intentarlo; "
        "si continúa, contacta al equipo BioCore."
    )


def _render_scope() -> None:
    st.markdown(
        """
        <section class="bc-private-card">
            <h3>Revisión reproducible dentro de BioCore</h3>
            <p>
                DarwinCheck utiliza reglas deterministas y una referencia taxonómica
                versionada. No emplea IA generativa para corregir nombres ni presenta
                inferencias como identificaciones confirmadas.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    observed, calculated, limitation = st.columns(3)
    observed.markdown("**Datos observados**")
    observed.caption(
        "Estructura de la hoja Ocurrencia, nombres, abundancias, horas y coordenadas."
    )
    calculated.markdown("**Datos calculados**")
    calculated.caption(
        "Coincidencias exactas, completitud, clasificación geográfica e índices ecológicos."
    )
    limitation.markdown("**Limitación visible**")
    limitation.caption(
        "Es una auditoría preliminar. No identifica especies, no certifica cumplimiento "
        "y no reemplaza una revisión profesional."
    )


def _load_projects():
    try:
        with st.spinner("Cargando proyectos de la organización…"):
            return project_service.list(context, ProjectFilters())
    except Exception as error:
        _friendly_error(error, operation="list_projects")
        return ()


def _render_summary(execution: DarwinCheckExecution) -> None:
    analysis = execution.analysis
    summary = analysis.summary
    st.success(
        "Revisión completada y vinculada al proyecto. El archivo original no fue modificado."
    )
    st.caption(
        f"Ejecución {execution.run.id} · Referencia {analysis.reference_name} "
        f"{analysis.reference_version}"
    )

    rows, matches, review, geography = st.columns(4)
    rows.metric("Registros analizados", summary.analyzed_rows)
    matches.metric("Coincidencias exactas", summary.exact_taxonomy_matches)
    review.metric("Revisión profesional", summary.manual_review_rows)
    geography.metric("Alertas geográficas", summary.geographic_issue_rows)
    st.progress(
        min(max(summary.completeness_percent / 100, 0.0), 1.0),
        text=f"Completitud de campos esenciales: {summary.completeness_percent:.1f}%",
    )

    with st.expander("Cómo se obtuvo este resultado", expanded=True):
        st.markdown(
            f"""
            - **Datos utilizados:** hoja `Ocurrencia` del archivo
              `{execution.run.source_filename}` y referencia
              `{analysis.reference_name} {analysis.reference_version}`.
            - **Regla taxonómica:** solo se corrige cuando existe una coincidencia
              exacta y única. Lo demás se conserva y se marca para revisión.
            - **Regla geográfica:** se interpretan coordenadas decimales o GMS y se
              comparan con rangos geográficos explícitos.
            - **Cálculos:** los índices usan únicamente abundancias numéricas y
              nombres disponibles; los valores no interpretables se excluyen y se
              informan como hallazgo.
            - **Incertidumbre:** una coincidencia de texto no confirma la identidad
              biológica del registro.
            - **Siguiente paso recomendado:** revisar las filas señaladas antes de
              utilizar la planilla en análisis o informes.
            """
        )

    st.markdown("### Índices ecológicos calculados")
    indices = summary.ecological_indices
    index_columns = st.columns(4)
    index_columns[0].metric("Individuos", f"{indices['total_individuals']:.0f}")
    index_columns[1].metric("Riqueza", f"{indices['richness']:.0f}")
    index_columns[2].metric("Shannon", f"{indices['shannon']:.3f}")
    index_columns[3].metric("Simpson", f"{indices['simpson']:.3f}")
    st.caption(
        "Estos son resultados calculados desde la planilla revisada; no son una "
        "evaluación de impacto ni una conclusión regulatoria."
    )

    tabs = st.tabs(["Hallazgos", "Trazabilidad", "Visualizaciones"])
    with tabs[0]:
        findings = pd.DataFrame(
            [finding.as_dict() for finding in analysis.findings]
        )
        if findings.empty:
            st.success("No se generaron hallazgos con las reglas activas.")
        else:
            category = st.multiselect(
                "Filtrar por categoría",
                sorted(findings["category"].unique()),
                key=f"darwincheck_finding_filter_{execution.run.id}",
            )
            visible = findings[
                findings["category"].isin(category)
            ] if category else findings
            visible = visible.rename(
                columns={
                    "row_number": "Fila",
                    "category": "Categoría",
                    "severity": "Nivel",
                    "observed": "Dato observado",
                    "rule": "Regla aplicada",
                    "explanation": "Explicación",
                    "recommendation": "Siguiente acción",
                }
            )
            st.dataframe(visible, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.dataframe(
            analysis.audit_dataframe,
            use_container_width=True,
            hide_index=True,
            height=520,
        )

    with tabs[2]:
        curve = pd.DataFrame(summary.accumulation_curve)
        if not curve.empty:
            figure = px.line(
                curve,
                x="records",
                y="observed_richness",
                markers=True,
                labels={
                    "records": "Registros revisados",
                    "observed_richness": "Riqueza observada acumulada",
                },
                title="Acumulación observada de riqueza",
            )
            figure.update_traces(line_color="#147a55")
            st.plotly_chart(figure, use_container_width=True)
            st.caption(
                "Comparación acumulativa observada en el orden de la planilla; "
                "no corresponde a una estimación de rarefacción."
            )

    export_bytes = st.session_state.get(EXPORT_KEY)
    if not isinstance(export_bytes, bytes):
        try:
            export_bytes = service.export_workbook(
                context,
                execution,
                organization_name=subscription.organization_name,
            )
            st.session_state[EXPORT_KEY] = export_bytes
        except Exception as error:
            _friendly_error(error, operation="export")
            export_bytes = None
    if export_bytes:
        timestamp = execution.run.created_at.strftime("%Y%m%d_%H%M%S")
        st.download_button(
            "Descargar planilla revisada y trazabilidad",
            data=export_bytes,
            file_name=f"DarwinCheck_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )


def _render_history(project_id: str) -> None:
    st.markdown("### Historial del proyecto")
    try:
        runs = service.list_runs(context, project_id, limit=10)
    except Exception as error:
        _friendly_error(error, operation="list_runs")
        if st.button("Reintentar historial", key="retry_darwincheck_history"):
            st.rerun()
        return
    if not runs:
        st.info(
            "Este proyecto todavía no tiene revisiones DarwinCheck. La primera "
            "ejecución aparecerá aquí con su versión y fecha."
        )
        return
    for run in runs:
        summary = run.summary
        with st.container(border=True):
            heading, status = st.columns([4, 1])
            heading.markdown(f"**{run.source_filename}**")
            heading.caption(
                f"{run.created_at.strftime('%d/%m/%Y %H:%M')} · "
                f"{run.reference_name} {run.reference_version}"
            )
            status.markdown("**Completada**")
            st.caption(
                f"{summary.get('analyzed_rows', 0)} registros · "
                f"{summary.get('manual_review_rows', 0)} para revisión · "
                f"{summary.get('geographic_issue_rows', 0)} alertas geográficas"
            )


_render_scope()
projects = _load_projects()
if not projects:
    st.info(
        "DarwinCheck necesita un proyecto para conservar la trazabilidad de la revisión."
    )
    st.page_link(
        "platform_pages/projects.py",
        label="Ir a Proyectos",
        icon="📁",
    )
    st.stop()

project_by_id = {project.id: project for project in projects}
selected_from_projects = st.session_state.get("biocore_selected_project_id")
project_ids = list(project_by_id)
default_index = (
    project_ids.index(str(selected_from_projects))
    if selected_from_projects and str(selected_from_projects) in project_by_id
    else 0
)
selected_project_id = st.selectbox(
    "Proyecto de esta revisión",
    project_ids,
    index=default_index,
    format_func=lambda project_id: (
        f"{project_by_id[project_id].name} · {project_by_id[project_id].code}"
    ),
    help="El archivo, las métricas y los hallazgos quedarán vinculados a este proyecto.",
)
st.session_state["biocore_selected_project_id"] = selected_project_id
selected_project = project_by_id[selected_project_id]
st.caption(
    f"Organización: {subscription.organization_name} · Proyecto: {selected_project.name}"
)

st.markdown("### Nueva revisión")
if not can_run:
    st.info(
        "Tu acceso es de consulta. Puedes revisar el historial, pero no cargar una nueva planilla."
    )
else:
    uploaded = st.file_uploader(
        "Planilla Darwin Core/SMA",
        type=("xlsx", "xls"),
        accept_multiple_files=False,
        help=(
            "Debe incluir una hoja llamada Ocurrencia y al menos 34 columnas. "
            "Tamaño máximo: 25 MB."
        ),
        key=f"darwincheck_upload_{selected_project_id}",
    )
    accepted = st.checkbox(
        "Comprendo que el resultado es preliminar y revisaré los hallazgos antes de utilizar la planilla.",
        key=f"darwincheck_accept_{selected_project_id}",
    )
    if st.button(
        "Revisar planilla",
        type="primary",
        disabled=uploaded is None or not accepted,
        use_container_width=True,
    ):
        try:
            with st.spinner(
                "Revisando estructura, taxonomía, coordenadas e índices…"
            ):
                execution = service.analyze_upload(
                    context,
                    selected_project_id,
                    uploaded.name,
                    uploaded.getvalue(),
                )
            st.session_state[EXECUTION_KEY] = execution
            st.session_state.pop(EXPORT_KEY, None)
            st.session_state[FLASH_KEY] = (
                "La revisión terminó y quedó registrada en el proyecto."
            )
            st.rerun()
        except Exception as error:
            _friendly_error(error, operation="analyze_upload")

flash = st.session_state.pop(FLASH_KEY, None)
if flash:
    st.success(str(flash))
execution = st.session_state.get(EXECUTION_KEY)
if (
    isinstance(execution, DarwinCheckExecution)
    and execution.run.project_id == selected_project_id
):
    _render_summary(execution)

_render_history(selected_project_id)

with st.expander("Acceso temporal a la versión independiente"):
    legacy = configured_external_applications()["darwincheck"]
    st.caption(
        "Se conserva como respaldo durante la validación de la versión nativa. "
        "No comparte automáticamente el proyecto ni el resultado actual."
    )
    if legacy.url:
        st.link_button("Abrir versión independiente", legacy.url)
