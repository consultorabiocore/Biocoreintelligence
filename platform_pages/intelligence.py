"""Native project monitoring with versioned multisatellite evidence."""

from __future__ import annotations

import logging
from datetime import date
from io import BytesIO

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from biocore.components.module_access import require_module_page
from biocore.config.brand import BRAND, available_logo
from biocore.domain.intelligence import IntelligenceRun
from biocore.domain.projects import ProjectFilters
from biocore.domain.subscriptions import ModuleCode
from biocore.modules.intelligence.copernicus import (
    CopernicusAnalysisError,
    CopernicusQuotaExceeded,
    CopernicusUnavailable,
)
from biocore.modules.intelligence.earth_engine import (
    EarthEngineAnalysisError,
    EarthEngineUnavailable,
)
from biocore.security.authorization import AuthorizationError
from biocore.security.roles import Permission
from biocore.services.intelligence import (
    IntelligenceProjectNotFound,
    IntelligenceValidationError,
)


LOGGER = logging.getLogger(__name__)
FLASH_KEY = "biocore_intelligence_flash"


context, subscription = require_module_page(
    ModuleCode.INTELLIGENCE,
    kicker="Vigilancia ecológica multisatelital",
    title="BioCore Intelligence",
    subtitle=(
        "Compara indicadores ecológicos, conserva la evidencia y explica qué "
        "cambió, con qué datos y qué conviene revisar después."
    ),
)

service = st.session_state.get("biocore_intelligence_service")
project_service = st.session_state.get("biocore_project_service")
if service is None or not callable(getattr(service, "run", None)):
    st.error("BioCore Intelligence no está disponible en esta sesión.")
    st.info("Actualiza la página. Si el problema continúa, vuelve a iniciar sesión.")
    st.stop()
if project_service is None or not callable(getattr(project_service, "list", None)):
    st.error("No pudimos conectar Intelligence con los proyectos.")
    st.stop()


def _friendly_error(error: Exception, *, operation: str) -> None:
    if isinstance(
        error,
        (
            IntelligenceValidationError,
            IntelligenceProjectNotFound,
            CopernicusAnalysisError,
            CopernicusQuotaExceeded,
            CopernicusUnavailable,
            EarthEngineAnalysisError,
            EarthEngineUnavailable,
        ),
    ):
        st.error(str(error))
        st.caption("Revisa el polígono, la línea base o la disponibilidad de imágenes y reintenta.")
        return
    if isinstance(error, AuthorizationError):
        st.warning("Tu rol permite consultar el monitoreo, pero no ejecutar uno nuevo.")
        return
    LOGGER.exception("Intelligence operation failed: %s", operation)
    st.error("No pudimos completar el monitoreo satelital.")
    st.info(
        "No se guardó un resultado incompleto. El detalle técnico quedó registrado "
        "para que BioCore pueda revisarlo."
    )


def _load_projects():
    try:
        with st.spinner("Cargando proyectos de la organización…"):
            return project_service.list(context, ProjectFilters())
    except Exception as error:
        _friendly_error(error, operation="list_projects")
        return ()


def _load_runs(project_id: str) -> tuple[IntelligenceRun, ...]:
    try:
        with st.spinner("Cargando el historial satelital…"):
            return service.list_runs(context, project_id)
    except Exception as error:
        _friendly_error(error, operation="list_runs")
        return ()


def _render_geometry(run: IntelligenceRun) -> None:
    coordinates = run.geometry.get("coordinates", [[]])[0]
    if not coordinates:
        return
    latitudes = [float(point[1]) for point in coordinates]
    longitudes = [float(point[0]) for point in coordinates]
    map_object = folium.Map(
        location=[sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)],
        zoom_start=12,
        tiles="OpenStreetMap",
    )
    folium.Polygon(
        locations=[[point[1], point[0]] for point in coordinates],
        color="#147a55",
        fill=True,
        fill_opacity=0.2,
        tooltip="Área analizada",
    ).add_to(map_object)
    st_folium(map_object, use_container_width=True, height=380, returned_objects=[])


def _export_run(run: IntelligenceRun) -> bytes:
    metadata = pd.DataFrame(
        [
            {
                "Campo": "Naturaleza del resultado",
                "Valor": "Monitoreo satelital calculado con observaciones reales",
            },
            {"Campo": "Ejecución", "Valor": run.id},
            {"Campo": "Período actual", "Valor": run.current_period},
            {"Campo": "Período de línea base", "Valor": run.baseline_period},
            {"Campo": "Proveedor y reglas", "Valor": run.provider_version},
            {"Campo": "Proveedor", "Valor": run.evidence.get("provider")},
            {"Campo": "Colección", "Valor": run.evidence.get("collection")},
            {
                "Campo": "Regla de composición",
                "Valor": run.evidence.get("composite_rule"),
            },
            {"Campo": "Imágenes actuales", "Valor": run.evidence.get("recent_image_count")},
            {"Campo": "Imágenes línea base", "Valor": run.evidence.get("baseline_image_count")},
            {"Campo": "Nubosidad media", "Valor": run.evidence.get("mean_cloud_percent")},
            {
                "Campo": "Muestras válidas actuales",
                "Valor": run.evidence.get("current_valid_pixel_samples"),
            },
            {
                "Campo": "Muestras válidas línea base",
                "Valor": run.evidence.get("baseline_valid_pixel_samples"),
            },
            {
                "Campo": "Persistencia",
                "Valor": "Conservado en el historial del proyecto",
            },
            {
                "Campo": "Limitación",
                "Valor": (
                    "Resultado calculado y preliminar. No determina causas, impactos, "
                    "cumplimiento ni reemplaza verificación de terreno."
                ),
            },
        ]
    )
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(run.metrics).to_excel(writer, index=False, sheet_name="Indicadores")
        pd.DataFrame(run.findings).to_excel(writer, index=False, sheet_name="Hallazgos")
        metadata.to_excel(writer, index=False, sheet_name="Trazabilidad")
    return buffer.getvalue()


def _render_run(run: IntelligenceRun, project_code: str) -> None:
    st.success("Monitoreo disponible y conservado en el historial del proyecto.")
    st.caption(
        f"Período actual: {run.current_period} · Línea base: {run.baseline_period} · "
        f"Reglas: {run.provider_version}"
    )
    evidence = run.evidence
    current_images, baseline_images, clouds = st.columns(3)
    current_images.metric(
        "Fechas con imágenes actuales",
        evidence.get("recent_image_count", 0),
    )
    baseline_images.metric(
        "Fechas con imágenes de base",
        evidence.get("baseline_image_count", 0),
    )
    cloud_value = evidence.get("mean_cloud_percent")
    clouds.metric(
        "Nubosidad media de escenas",
        f"{cloud_value:.1f}%" if cloud_value is not None else "No disponible",
    )

    st.markdown("### Indicadores calculados")
    metric_columns = st.columns(3)
    for index, metric in enumerate(run.metrics):
        current = metric.get("current")
        change = metric.get("relative_change_percent")
        unit = str(metric.get("unit") or "")
        current_text = "No disponible" if current is None else f"{float(current):.3f} {unit}".strip()
        change_text = None if change is None else f"{float(change):+.1f}% vs base"
        metric_columns[index % 3].metric(
            str(metric.get("label")), current_text, change_text
        )

    chart_rows = [
        metric
        for metric in run.metrics
        if metric.get("current") is not None and metric.get("baseline") is not None
    ]
    if chart_rows:
        figure = go.Figure()
        figure.add_bar(
            name="Línea base",
            x=[item["label"] for item in chart_rows],
            y=[item["baseline"] for item in chart_rows],
        )
        figure.add_bar(
            name="Período actual",
            x=[item["label"] for item in chart_rows],
            y=[item["current"] for item in chart_rows],
        )
        figure.update_layout(barmode="group", height=420, legend_title_text="Comparación")
        st.plotly_chart(figure, use_container_width=True)

    result_tab, evidence_tab, map_tab = st.tabs(
        ["Hallazgos explicables", "Fuentes y trazabilidad", "Área analizada"]
    )
    with result_tab:
        findings = pd.DataFrame(run.findings).rename(
            columns={
                "dimension": "Dimensión",
                "classification": "Clasificación",
                "observed": "Comparación",
                "rule": "Regla aplicada",
                "explanation": "Qué significa",
                "confidence": "Confianza",
                "limitation": "Limitación",
                "recommendation": "Siguiente acción",
            }
        )
        st.dataframe(findings, use_container_width=True, hide_index=True)
    with evidence_tab:
        sources = pd.DataFrame(run.metrics)[
            ["label", "source", "resolution"]
        ].drop_duplicates()
        st.dataframe(
            sources.rename(
                columns={"label": "Indicador", "source": "Fuente", "resolution": "Resolución"}
            ),
            use_container_width=True,
            hide_index=True,
        )
        traceability = pd.DataFrame(
            [
                {
                    "Proveedor": run.evidence.get("provider") or "Histórico",
                    "Colección": run.evidence.get("collection") or "Ver fuentes",
                    "Regla de composición": run.evidence.get("composite_rule")
                    or "Registrada en la versión del proveedor",
                    "Ventana": (
                        f"{run.evidence.get('window_days')} días"
                        if run.evidence.get("window_days")
                        else "Ver período"
                    ),
                    "Nubosidad máxima por escena": (
                        f"{run.evidence.get('max_scene_cloud_percent')}%"
                        if run.evidence.get("max_scene_cloud_percent") is not None
                        else "No registrada"
                    ),
                }
            ]
        )
        st.dataframe(traceability, use_container_width=True, hide_index=True)
        st.warning(
            "Resultado calculado y preliminar. No determina la causa del cambio, "
            "no confirma impactos y no reemplaza una campaña o revisión profesional."
        )
    with map_tab:
        _render_geometry(run)

    st.download_button(
        "Descargar informe histórico de indicadores",
        data=_export_run(run),
        file_name=f"BioCore_Intelligence_{project_code}_{run.created_at:%Y%m%d_%H%M}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


logo = available_logo(BRAND.intelligence_logo)
if logo:
    st.image(str(logo), width=180)

st.markdown(
    """
    <section class="bc-private-card">
        <h3>Vigilancia conectada al proyecto</h3>
        <p>
            BioCore usa imágenes reales Sentinel-2 de Copernicus para comparar
            vegetación y humedad vegetal. Distingue el dato observado, el cálculo,
            la comparación y la recomendación; nunca presenta una inferencia como
            hecho confirmado.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

projects = _load_projects()
if not projects:
    st.info("Intelligence necesita un proyecto para conservar cada monitoreo.")
    st.page_link("platform_pages/projects.py", label="Ir a Proyectos", icon="📁")
    st.stop()

project_by_id = {project.id: project for project in projects}
project_ids = list(project_by_id)
selected_from_projects = st.session_state.get("biocore_selected_project_id")
default_index = (
    project_ids.index(str(selected_from_projects))
    if selected_from_projects and str(selected_from_projects) in project_by_id
    else 0
)
selected_project_id = st.selectbox(
    "Proyecto que deseas vigilar",
    project_ids,
    index=default_index,
    format_func=lambda project_id: (
        f"{project_by_id[project_id].name} · {project_by_id[project_id].code}"
    ),
)
st.session_state["biocore_selected_project_id"] = selected_project_id
selected_project = project_by_id[selected_project_id]
st.caption(f"Organización: {subscription.organization_name} · Proyecto: {selected_project.name}")

flash = st.session_state.pop(FLASH_KEY, None)
if flash:
    st.success(str(flash))

new_tab, history_tab = st.tabs(["Nuevo monitoreo", "Historial del proyecto"])
with new_tab:
    if not service.provider_configured:
        st.warning(
            "BioCore Intelligence ya está integrado con el proyecto y conserva su "
            "historial. Falta conectar las credenciales gratuitas de Copernicus Data "
            "Space para ejecutar un monitoreo nuevo con imágenes reales."
        )
        st.caption(
            "No necesitas activar una prueba de Google Cloud ni registrar una tarjeta. "
            "Mientras se completa la conexión, el historial real permanece disponible."
        )
        st.info(
            "Los resultados solo se habilitarán cuando provengan de observaciones "
            "satelitales reales y puedan conservar su fuente y período."
        )
    elif not context.has_permission(Permission.INTELLIGENCE_WRITE):
        st.info("Tu acceso es de consulta. Puedes revisar resultados históricos.")
    else:
        st.markdown("### Definir el área y la comparación")
        with st.form("intelligence_monitoring_form"):
            geojson = st.file_uploader(
                "Polígono del área de estudio en GeoJSON *",
                type=("geojson", "json"),
                help="Usa coordenadas WGS84. El archivo se valida antes de consultar fuentes satelitales.",
            )
            baseline_year = st.selectbox(
                "Año de línea base *",
                list(range(date.today().year - 1, 2016, -1)),
                help="Se compara la misma ventana aproximada de 90 días en ambos períodos.",
            )
            accepted = st.checkbox(
                "Comprendo que es una comparación preliminar y revisaré los cambios con antecedentes y terreno."
            )
            submitted = st.form_submit_button(
                "Analizar área",
                type="primary",
                use_container_width=True,
                disabled=geojson is None or not accepted,
            )
        if submitted:
            try:
                with st.spinner(
                    "Consultando Sentinel-2 en Copernicus. Esto puede tardar unos minutos…"
                ):
                    completed = service.run(
                        context,
                        selected_project_id,
                        geojson.getvalue(),
                        int(baseline_year),
                    )
                st.session_state[FLASH_KEY] = (
                    "Monitoreo completado. El resultado y sus fuentes quedaron en el historial."
                )
                st.session_state["biocore_intelligence_selected_run"] = completed.id
                st.rerun()
            except Exception as error:
                _friendly_error(error, operation="run_monitoring")

with history_tab:
    runs = _load_runs(selected_project_id)
    if not runs:
        st.info(
            "Este proyecto todavía no tiene monitoreos. El primero aparecerá aquí "
            "con período, fuentes, reglas y limitaciones."
        )
    else:
        selected_run_id = st.selectbox(
            "Resultado histórico",
            [run.id for run in runs],
            index=next(
                (
                    index
                    for index, run in enumerate(runs)
                    if run.id == st.session_state.get("biocore_intelligence_selected_run")
                ),
                0,
            ),
            format_func=lambda run_id: next(
                f"{run.created_at:%d/%m/%Y %H:%M} · base {run.baseline_year}"
                for run in runs
                if run.id == run_id
            ),
        )
        selected_run = next(run for run in runs if run.id == selected_run_id)
        _render_run(selected_run, selected_project.code)
