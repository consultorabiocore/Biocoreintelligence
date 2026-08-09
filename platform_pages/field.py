"""Native MycoField capture, evidence, map and project history."""

from __future__ import annotations

import logging
from io import BytesIO

import pandas as pd
import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.config.brand import BRAND
from biocore.domain.mycofield import MycoFieldObservation, ObservationPrivacy
from biocore.domain.projects import ProjectFilters
from biocore.domain.subscriptions import ModuleCode
from biocore.security.authorization import AuthorizationError
from biocore.security.roles import Permission
from biocore.services.mycofield import (
    MycoFieldConflictError,
    MycoFieldInput,
    MycoFieldProjectNotFound,
    MycoFieldValidationError,
    PhotoUpload,
)


LOGGER = logging.getLogger(__name__)
FLASH_KEY = "biocore_mycofield_flash"
PRIVACY_LABELS = {
    ObservationPrivacy.PRIVATE: "Privado: solo quien creó el registro",
    ObservationPrivacy.BLURRED: "Zona aproximada: coordenadas redondeadas",
    ObservationPrivacy.ORGANIZATION: "Organización: ubicación exacta",
}


context, subscription = require_module_page(
    ModuleCode.FIELD,
    kicker="Terreno y evidencia",
    title="BioCore MycoField",
    subtitle=(
        "Registra observaciones de hongos, fotografías y contexto ecológico "
        "sin perder la relación con el proyecto."
    ),
)

service = st.session_state.get("biocore_mycofield_service")
project_service = st.session_state.get("biocore_project_service")
if service is None or not callable(getattr(service, "create", None)):
    st.error("MycoField no está disponible en esta sesión.")
    st.info("Actualiza la página. Si el problema continúa, vuelve a iniciar sesión.")
    st.stop()
if project_service is None or not callable(getattr(project_service, "list", None)):
    st.error("No pudimos conectar MycoField con los proyectos.")
    st.stop()


def _friendly_error(error: Exception, *, operation: str) -> None:
    if isinstance(
        error,
        (MycoFieldValidationError, MycoFieldConflictError, MycoFieldProjectNotFound),
    ):
        st.error(str(error))
        st.caption("Revisa los campos señalados y vuelve a intentarlo.")
        return
    if isinstance(error, AuthorizationError):
        st.warning("Tu rol permite consultar MycoField, pero no crear registros.")
        st.caption("Solicita acceso de edición a la administración de tu organización.")
        return
    LOGGER.exception("MycoField operation failed: %s", operation)
    st.error("No pudimos completar la operación de MycoField.")
    st.info(
        "Tus datos permanecen sin cambios. El detalle técnico quedó registrado; "
        "vuelve a intentarlo o contacta al equipo BioCore."
    )

def _load_projects():
    try:
        with st.spinner("Cargando proyectos de la organización…"):
            return project_service.list(context, ProjectFilters())
    except Exception as error:
        _friendly_error(error, operation="list_projects")
        return ()


def _load_observations(project_id: str) -> tuple[MycoFieldObservation, ...]:
    try:
        with st.spinner("Cargando la bitácora del proyecto…"):
            return service.list_observations(context, project_id)
    except Exception as error:
        _friendly_error(error, operation="list_observations")
        return ()


def _export_observations(observations: tuple[MycoFieldObservation, ...]) -> bytes:
    rows = []
    for item in observations:
        rows.append(
            {
                "Código de muestra": item.sample_code,
                "Fecha": item.observed_on.isoformat(),
                "Nombre tentativo": item.tentative_name,
                "Sustrato": item.substrate,
                "Hábitat": item.habitat,
                "Método": item.method,
                "Esfuerzo": item.effort,
                "Privacidad": PRIVACY_LABELS[item.privacy],
                "Latitud compartida": item.map_latitude,
                "Longitud compartida": item.map_longitude,
                "Rasgos observados": "; ".join(item.observable_traits),
                "Notas": item.notes,
                "Fotografías": len(item.photos),
                "Registrado": item.created_at.isoformat(),
            }
        )
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="Observaciones")
    return buffer.getvalue()


if BRAND.field_logo.is_file():
    st.image(str(BRAND.field_logo), width=180)

st.markdown(
    """
    <section class="bc-private-card">
        <h3>Una bitácora científica dentro de BioCore</h3>
        <p>
            MycoField conserva datos observados y evidencia. Un nombre tentativo
            es una hipótesis de terreno: no confirma la identidad de una especie
            y debe revisarse con caracteres diagnósticos y apoyo especialista.
        </p>
    </section>
    """,
    unsafe_allow_html=True,
)

projects = _load_projects()
if not projects:
    st.info("MycoField necesita un proyecto para mantener la trazabilidad del registro.")
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
    "Proyecto de estas observaciones",
    project_ids,
    index=default_index,
    format_func=lambda project_id: (
        f"{project_by_id[project_id].name} · {project_by_id[project_id].code}"
    ),
    help="El registro y sus fotografías quedarán vinculados a este proyecto.",
)
st.session_state["biocore_selected_project_id"] = selected_project_id
st.caption(
    f"Organización: {subscription.organization_name} · "
    f"Proyecto: {project_by_id[selected_project_id].name}"
)

flash = st.session_state.pop(FLASH_KEY, None)
if flash:
    st.success(str(flash))

capture_tab, history_tab, guide_tab = st.tabs(
    ["Nueva observación", "Bitácora y mapa", "Guía de registro"]
)

with capture_tab:
    if not context.has_permission(Permission.FIELD_WRITE):
        st.info("Tu acceso es de consulta. Puedes revisar la bitácora, pero no crear registros.")
    else:
        st.markdown("### Registrar lo observado")
        st.caption("Los campos con * son obligatorios. Revisa el resumen antes de guardar.")
        with st.form("mycofield_observation_form", clear_on_submit=True):
            location, observation = st.columns(2)
            with location:
                sample_code = st.text_input(
                    "Código de muestra *",
                    placeholder="BIO-001",
                    help="Identificador único dentro de este proyecto.",
                )
                observed_on = st.date_input("Fecha del hallazgo *")
                latitude = st.number_input(
                    "Latitud WGS84 *", min_value=-90.0, max_value=90.0,
                    value=-36.820000, format="%.6f",
                )
                longitude = st.number_input(
                    "Longitud WGS84 *", min_value=-180.0, max_value=180.0,
                    value=-73.030000, format="%.6f",
                )
                privacy = st.radio(
                    "Visibilidad de la ubicación *",
                    list(ObservationPrivacy),
                    format_func=lambda value: PRIVACY_LABELS[value],
                    help="Privado no publica coordenadas; zona aproximada redondea el punto.",
                )
            with observation:
                tentative_name = st.text_input(
                    "Nombre tentativo",
                    value="Por determinar",
                    help="Es una hipótesis de terreno, no una identificación confirmada.",
                )
                substrate = st.selectbox(
                    "Sustrato *",
                    ["Suelo", "Madera muerta", "Madera viva", "Hojarasca", "Otro"],
                )
                habitat = st.text_input(
                    "Hábitat *", placeholder="Bosque nativo caducifolio"
                )
                method = st.selectbox(
                    "Método *", ["Búsqueda activa", "Transecto", "Parcela", "Hallazgo incidental"]
                )
                effort = st.text_input(
                    "Esfuerzo *", placeholder="2 personas · 90 minutos · 1 ha"
                )

            traits = st.multiselect(
                "Rasgos observables",
                [
                    "Sombrero viscoso", "Sombrero escamoso", "Láminas decurrentes",
                    "Poros", "Agujas", "Anillo presente", "Volva presente",
                    "Oxidación o cambio de color", "Olor distintivo",
                ],
                help="Registra lo observado sin convertirlo automáticamente en una especie.",
            )
            notes = st.text_area(
                "Notas de terreno",
                placeholder="Color, dimensiones, asociación vegetal, microhábitat y dudas pendientes.",
            )
            photos = st.file_uploader(
                "Fotografías técnicas",
                type=("jpg", "jpeg", "png", "webp"),
                accept_multiple_files=True,
                help="Hasta 6 imágenes de 10 MB. Se guardan en almacenamiento privado.",
            )
            accepted = st.checkbox(
                "Confirmo que el nombre indicado es tentativo y que los datos fueron revisados antes de guardar."
            )
            submitted = st.form_submit_button(
                "Guardar observación en el proyecto",
                type="primary",
                use_container_width=True,
                disabled=not accepted,
            )

        if submitted:
            try:
                uploads = tuple(
                    PhotoUpload(
                        filename=photo.name,
                        content_type=photo.type or "application/octet-stream",
                        payload=photo.getvalue(),
                    )
                    for photo in photos
                )
                with st.spinner("Guardando registro y evidencia privada…"):
                    saved = service.create(
                        context,
                        selected_project_id,
                        MycoFieldInput(
                            sample_code=sample_code,
                            observed_on=observed_on,
                            latitude=latitude,
                            longitude=longitude,
                            privacy=privacy,
                            tentative_name=tentative_name,
                            substrate=substrate,
                            habitat=habitat,
                            method=method,
                            effort=effort,
                            observable_traits=tuple(traits),
                            notes=notes,
                        ),
                        uploads,
                    )
                st.session_state[FLASH_KEY] = (
                    f"Observación {saved.sample_code} guardada con {len(saved.photos)} fotografía(s)."
                )
                st.rerun()
            except Exception as error:
                _friendly_error(error, operation="create_observation")

with history_tab:
    observations = _load_observations(selected_project_id)
    if not observations:
        st.info(
            "Este proyecto aún no tiene observaciones visibles. La primera aparecerá "
            "aquí con su evidencia y trazabilidad."
        )
    else:
        total, photographed, pending = st.columns(3)
        total.metric("Observaciones", len(observations))
        photographed.metric("Con fotografías", sum(bool(item.photos) for item in observations))
        pending.metric(
            "Por determinar",
            sum(item.tentative_name.casefold() == "por determinar" for item in observations),
        )

        map_rows = [
            {
                "lat": item.map_latitude,
                "lon": item.map_longitude,
                "Código": item.sample_code,
                "Nombre tentativo": item.tentative_name,
            }
            for item in observations
            if item.map_latitude is not None and item.map_longitude is not None
        ]
        if map_rows:
            st.markdown("### Distribución de observaciones compartidas")
            st.map(pd.DataFrame(map_rows))
            st.caption(
                "Los puntos aproximados se muestran redondeados. Los registros privados no aparecen en el mapa."
            )

        table = pd.DataFrame(
            [
                {
                    "Código": item.sample_code,
                    "Fecha": item.observed_on,
                    "Nombre tentativo": item.tentative_name,
                    "Sustrato": item.substrate,
                    "Hábitat": item.habitat,
                    "Privacidad": PRIVACY_LABELS[item.privacy],
                    "Fotos": len(item.photos),
                }
                for item in observations
            ]
        )
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar bitácora del proyecto",
            data=_export_observations(observations),
            file_name=f"MycoField_{project_by_id[selected_project_id].code}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        selected_record_id = st.selectbox(
            "Ver evidencia de una observación",
            [item.id for item in observations],
            format_func=lambda item_id: next(
                item.sample_code for item in observations if item.id == item_id
            ),
        )
        selected_record = next(item for item in observations if item.id == selected_record_id)
        with st.container(border=True):
            st.markdown(f"#### {selected_record.sample_code} · {selected_record.tentative_name}")
            st.caption(
                "Dato observado por el equipo de terreno. El nombre es tentativo hasta su revisión profesional."
            )
            st.write(f"**Hábitat:** {selected_record.habitat}")
            st.write(f"**Rasgos:** {', '.join(selected_record.observable_traits) or 'No informados'}")
            st.write(f"**Notas:** {selected_record.notes or 'Sin notas adicionales'}")
            if selected_record.photos:
                try:
                    evidence = service.evidence_urls(context, selected_record)
                    columns = st.columns(min(3, len(evidence)))
                    for index, (photo, url) in enumerate(evidence):
                        if url:
                            columns[index % len(columns)].image(url, caption=photo.filename)
                except Exception as error:
                    _friendly_error(error, operation="load_evidence")

with guide_tab:
    st.markdown("### Qué registrar para permitir una revisión posterior")
    st.markdown(
        """
        1. Fotografía general del basidioma o ascoma en su ambiente.
        2. Superficie fértil: láminas, poros, agujas, pliegues u otra estructura.
        3. Pie completo y base, sin cortar estructuras diagnósticas.
        4. Escala, sustrato, vegetación asociada y coordenadas revisadas.
        5. Cambios de color, olor u otros rasgos observados, sin inferirlos.

        **Limitación:** una fotografía o una regla de campo no confirma por sí sola
        la identidad taxonómica ni reemplaza la revisión microscópica o especialista.
        """
    )
