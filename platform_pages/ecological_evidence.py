"""Traceable ecological evidence inside the private BioCore project flow."""

from __future__ import annotations

import logging
from datetime import date, time

import pandas as pd
import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.ecological_evidence import (
    EcologicalEvidence,
    EvidenceFilters,
    EvidenceSource,
    EvidenceType,
    IdentificationStatus,
    ProfessionalReviewStatus,
    TaxonomicGroup,
)
from biocore.domain.projects import ProjectFilters
from biocore.domain.subscriptions import ModuleCode
from biocore.integrations.inaturalist import INaturalistError
from biocore.security.authorization import AuthorizationError
from biocore.security.roles import Permission
from biocore.services.ecological_evidence import (
    EcologicalEvidenceService,
    EvidenceConflict,
    EvidenceInput,
    EvidenceNotFound,
    EvidenceUpload,
    EvidenceValidationError,
    ProfessionalReviewInput,
)


LOGGER = logging.getLogger(__name__)
FLASH_KEY = "biocore_evidence_flash"

GROUP_LABELS = {
    TaxonomicGroup.FLORA: "Flora",
    TaxonomicGroup.FUNGA: "Funga",
    TaxonomicGroup.LICHENS: "Líquenes",
    TaxonomicGroup.FAUNA: "Fauna",
    TaxonomicGroup.OTHER: "Otro",
}
IDENTIFICATION_LABELS = {
    IdentificationStatus.UNIDENTIFIED: "Sin identificar",
    IdentificationStatus.PROPOSED: "Identificación propuesta",
    IdentificationStatus.REVIEW_REQUIRED: "Requiere revisión",
    IdentificationStatus.REVIEWED: "Revisada",
    IdentificationStatus.PROFESSIONALLY_VALIDATED: "Validada profesionalmente",
    IdentificationStatus.UNCERTAIN: "Identificación incierta",
}
REVIEW_LABELS = {
    ProfessionalReviewStatus.NOT_REQUESTED: "No solicitada",
    ProfessionalReviewStatus.REQUESTED: "Solicitada",
    ProfessionalReviewStatus.UNDER_REVIEW: "En revisión",
    ProfessionalReviewStatus.APPROVED: "Aprobada",
    ProfessionalReviewStatus.CORRECTED: "Corregida",
    ProfessionalReviewStatus.UNCERTAIN: "Con incertidumbre",
}
TYPE_LABELS = {
    EvidenceType.OBSERVATION: "Observación",
    EvidenceType.PHOTOGRAPH: "Fotografía",
    EvidenceType.SPECIMEN: "Ejemplar o muestra",
    EvidenceType.DOCUMENT: "Documento",
    EvidenceType.OTHER: "Otro",
}
SOURCE_LABELS = {
    EvidenceSource.BIOCORE: "Registro BioCore",
    EvidenceSource.INATURALIST: "Registro externo · iNaturalist",
    EvidenceSource.EXTERNAL: "Registro externo",
}
LICENSE_OPTIONS = (
    "Todos los derechos reservados",
    "CC BY 4.0",
    "CC BY-SA 4.0",
    "CC BY-NC 4.0",
    "Autorización documentada del autor",
    "Por documentar",
)


context, subscription = require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Proyecto · antecedentes trazables",
    title="Evidencias ecológicas",
    subtitle=(
        "Organiza observaciones, fotografías, procedencia, identificación y revisión "
        "profesional sin confundir una propuesta con un dato validado."
    ),
)

service = st.session_state.get("biocore_ecological_evidence_service")
project_service = st.session_state.get("biocore_project_service")
if not isinstance(service, EcologicalEvidenceService):
    st.error("Evidencias ecológicas no está disponible en esta sesión.")
    st.info("Actualiza la página. Si continúa, vuelve a iniciar sesión.")
    st.stop()
if project_service is None or not callable(getattr(project_service, "list", None)):
    st.error("No pudimos conectar las evidencias con los proyectos.")
    st.stop()


def _friendly_error(error: Exception, *, operation: str) -> None:
    if isinstance(
        error,
        (EvidenceValidationError, EvidenceConflict, EvidenceNotFound, INaturalistError),
    ):
        st.error(str(error))
        st.caption("No se guardaron cambios. Revisa la indicación y vuelve a intentarlo.")
        return
    if isinstance(error, AuthorizationError):
        st.warning("Tu rol no permite realizar esta acción.")
        st.caption("Solicita el permiso correspondiente a la administración BioCore.")
        return
    LOGGER.exception("Ecological evidence operation failed: %s", operation)
    st.error("No pudimos completar la operación de Evidencias ecológicas.")
    st.info(
        "Tus datos permanecen sin cambios. El detalle técnico quedó registrado "
        "para que el equipo BioCore pueda revisarlo."
    )


def _load_projects():
    try:
        with st.spinner("Cargando proyectos de la organización…"):
            return project_service.list(context, ProjectFilters())
    except Exception as error:
        _friendly_error(error, operation="list_projects")
        return ()


def _load_evidence(project_id: str, filters: EvidenceFilters = EvidenceFilters()):
    try:
        with st.spinner("Cargando evidencias del proyecto…"):
            return service.list(context, project_id, filters)
    except Exception as error:
        _friendly_error(error, operation="list_evidence")
        return ()


def _input_fields(prefix: str, current: EcologicalEvidence | None = None):
    identification_options = [
        value
        for value in IdentificationStatus
        if value != IdentificationStatus.PROFESSIONALLY_VALIDATED
    ]
    identity, taxonomy = st.columns(2)
    with identity:
        observation_date = st.date_input(
            "Fecha de observación *",
            value=current.observation_date if current else date.today(),
            key=f"{prefix}_date",
        )
        has_time = st.checkbox(
            "Registrar hora",
            value=bool(current and current.observation_time),
            key=f"{prefix}_has_time",
        )
        observation_time = (
            st.time_input(
                "Hora de observación",
                value=current.observation_time if current and current.observation_time else time(12, 0),
                key=f"{prefix}_time",
            )
            if has_time
            else None
        )
        taxonomic_group = st.selectbox(
            "Grupo taxonómico *",
            list(TaxonomicGroup),
            index=list(TaxonomicGroup).index(current.taxonomic_group) if current else 0,
            format_func=lambda item: GROUP_LABELS[item],
            key=f"{prefix}_group",
        )
        evidence_type = st.selectbox(
            "Tipo de evidencia *",
            list(EvidenceType),
            index=list(EvidenceType).index(current.evidence_type) if current else 0,
            format_func=lambda item: TYPE_LABELS[item],
            key=f"{prefix}_type",
        )
        observation_method = st.text_input(
            "Método de observación *",
            value=current.observation_method if current else "",
            placeholder="Búsqueda activa, transecto, parcela o hallazgo incidental",
            key=f"{prefix}_method",
        )
        if current and current.study_area_id:
            st.text_input(
                "Área de estudio vinculada",
                value=current.study_area_id,
                disabled=True,
                help="El vínculo se gestionará desde Áreas de estudio cuando ese módulo esté operativo.",
                key=f"{prefix}_study_area_locked",
            )
            study_area_id = current.study_area_id
        else:
            st.caption(
                "Área de estudio: vínculo opcional preparado. La selección se habilitará "
                "cuando Áreas de estudio tenga registros persistentes."
            )
            study_area_id = None
    with taxonomy:
        taxon_proposed = st.text_input(
            "Taxón propuesto",
            value=current.taxon_proposed or "" if current else "",
            help="Una propuesta no equivale a identificación profesional.",
            key=f"{prefix}_proposed",
        )
        scientific_name = st.text_input(
            "Nombre científico",
            value=current.scientific_name or "" if current else "",
            key=f"{prefix}_scientific",
        )
        common_name = st.text_input(
            "Nombre común",
            value=current.common_name or "" if current else "",
            key=f"{prefix}_common",
        )
        default_status = current.identification_status if current else IdentificationStatus.UNIDENTIFIED
        if default_status == IdentificationStatus.PROFESSIONALLY_VALIDATED:
            st.text_input(
                "Estado de identificación *",
                value=IDENTIFICATION_LABELS[default_status],
                disabled=True,
                help="Solo otra revisión profesional puede cambiar este estado.",
                key=f"{prefix}_identification_locked",
            )
            identification_status = default_status
        else:
            identification_status = st.selectbox(
                "Estado de identificación *",
                identification_options,
                index=identification_options.index(default_status),
                format_func=lambda item: IDENTIFICATION_LABELS[item],
                key=f"{prefix}_identification",
            )
        author_name = st.text_input(
            "Autor u observador *",
            value=current.author_name if current else "",
            key=f"{prefix}_author",
        )
        license_name = st.selectbox(
            "Condición de uso *",
            LICENSE_OPTIONS,
            index=(
                LICENSE_OPTIONS.index(current.license)
                if current and current.license in LICENSE_OPTIONS
                else 0
            ),
            help="Describe el uso autorizado; no transfiere la autoría.",
            key=f"{prefix}_license",
        )

    has_coordinates = st.checkbox(
        "La evidencia tiene coordenadas revisadas",
        value=bool(current and current.latitude is not None),
        key=f"{prefix}_has_coordinates",
    )
    latitude = longitude = accuracy = None
    if has_coordinates:
        latitude_col, longitude_col, accuracy_col = st.columns(3)
        latitude = latitude_col.number_input(
            "Latitud WGS84",
            min_value=-90.0,
            max_value=90.0,
            value=current.latitude if current and current.latitude is not None else None,
            format="%.6f",
            key=f"{prefix}_latitude",
        )
        longitude = longitude_col.number_input(
            "Longitud WGS84",
            min_value=-180.0,
            max_value=180.0,
            value=current.longitude if current and current.longitude is not None else None,
            format="%.6f",
            key=f"{prefix}_longitude",
        )
        accuracy = accuracy_col.number_input(
            "Precisión aproximada (m)",
            min_value=0.0,
            value=(
                current.location_accuracy_m
                if current and current.location_accuracy_m is not None
                else None
            ),
            key=f"{prefix}_accuracy",
        )
    notes = st.text_area(
        "Notas observadas",
        value=current.notes if current else "",
        placeholder="Describe hábitat, sustrato, rasgos observados y limitaciones.",
        key=f"{prefix}_notes",
    )
    return EvidenceInput(
        observation_date=observation_date,
        observation_time=observation_time,
        study_area_id=study_area_id or None,
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=accuracy,
        taxon_proposed=taxon_proposed or None,
        scientific_name=scientific_name or None,
        common_name=common_name or None,
        taxonomic_group=taxonomic_group,
        identification_status=identification_status,
        evidence_type=evidence_type,
        observation_method=observation_method,
        notes=notes,
        author_name=author_name,
        license=license_name,
    )


projects = _load_projects()
if not projects:
    st.info(
        "Evidencias ecológicas necesita un proyecto para conservar contexto, "
        "responsables e historial."
    )
    st.page_link("platform_pages/projects.py", label="Ir a Proyectos", icon="📁")
    st.stop()

project_by_id = {project.id: project for project in projects}
project_ids = list(project_by_id)
selected_state = str(st.session_state.get("biocore_selected_project_id") or "")
selected_project_id = st.selectbox(
    "Proyecto",
    project_ids,
    index=project_ids.index(selected_state) if selected_state in project_by_id else 0,
    format_func=lambda item: f"{project_by_id[item].name} · {project_by_id[item].code}",
    help="Todas las consultas y cambios quedan limitados a este proyecto y organización.",
)
st.session_state["biocore_selected_project_id"] = selected_project_id
st.caption(
    f"Organización: {subscription.organization_name} · "
    f"Proyecto: {project_by_id[selected_project_id].name}"
)

flash = st.session_state.pop(FLASH_KEY, None)
if flash:
    st.success(str(flash))

records_tab, new_tab, import_tab, review_tab = st.tabs(
    ["Registros y mapa", "Nuevo registro", "Importar desde iNaturalist", "Calidad y revisión"]
)

with records_tab:
    st.markdown("### Evidencias del proyecto")
    st.caption(
        "Los conteos organizan antecedentes; no representan por sí solos riqueza, "
        "abundancia, calidad ecológica ni impacto ambiental."
    )
    filter_group, filter_status, filter_source, filter_review = st.columns(4)
    group_filter = filter_group.selectbox(
        "Grupo",
        [None, *TaxonomicGroup],
        format_func=lambda item: "Todos" if item is None else GROUP_LABELS[item],
    )
    status_filter = filter_status.selectbox(
        "Identificación",
        [None, *IdentificationStatus],
        format_func=lambda item: "Todos" if item is None else IDENTIFICATION_LABELS[item],
    )
    source_filter = filter_source.selectbox(
        "Fuente",
        [None, *EvidenceSource],
        format_func=lambda item: "Todas" if item is None else SOURCE_LABELS[item],
    )
    review_filter = filter_review.selectbox(
        "Revisión",
        [None, *ProfessionalReviewStatus],
        format_func=lambda item: "Todas" if item is None else REVIEW_LABELS[item],
    )
    use_date_filter = st.checkbox("Filtrar por rango de fechas")
    date_from = date_to = None
    if use_date_filter:
        date_start_col, date_end_col = st.columns(2)
        date_from = date_start_col.date_input("Desde", value=date.today().replace(month=1, day=1))
        date_to = date_end_col.date_input("Hasta", value=date.today())
    records = _load_evidence(
        selected_project_id,
        EvidenceFilters(
            taxonomic_group=group_filter,
            identification_status=status_filter,
            source_type=source_filter,
            review_status=review_filter,
            date_from=date_from,
            date_to=date_to,
        ),
    )
    summary = service.summary(records)
    first_metrics = st.columns(4)
    for column, label, value in zip(
        first_metrics,
        ("Total", "Registros BioCore", "Registros externos", "Taxones distintos"),
        (summary.total, summary.own_records, summary.external_records, summary.distinct_taxa),
    ):
        column.metric(label, value)
    second_metrics = st.columns(4)
    for column, label, value in zip(
        second_metrics,
        ("Validados", "Pendientes de revisión", "Con coordenadas", "Con alertas de calidad"),
        (summary.validated, summary.pending_review, summary.georeferenced, summary.incomplete),
    ):
        column.metric(label, value)

    if not records:
        st.info(
            "No hay evidencias que coincidan con los filtros. Puedes crear un "
            "registro propio o referenciar una observación pública de iNaturalist."
        )
    else:
        table = pd.DataFrame(
            [
                {
                    "Fecha": item.observation_date,
                    "Taxón": item.display_taxon,
                    "Grupo": GROUP_LABELS[item.taxonomic_group],
                    "Fuente": SOURCE_LABELS[item.source_type],
                    "Identificación": IDENTIFICATION_LABELS[item.identification_status],
                    "Revisión": REVIEW_LABELS[item.professional_review_status],
                    "Fotos": len(item.media),
                    "Ubicación": "Sí" if item.latitude is not None else "Falta",
                }
                for item in records
            ]
        )
        st.dataframe(table, use_container_width=True, hide_index=True)
        map_rows = [
            {
                "lat": item.latitude,
                "lon": item.longitude,
                "taxon": item.display_taxon,
                "source": SOURCE_LABELS[item.source_type],
            }
            for item in records
            if item.latitude is not None and item.longitude is not None
        ]
        if map_rows:
            st.markdown("### Mapa básico de evidencias")
            st.map(pd.DataFrame(map_rows))
            st.caption(
                "Vista operativa inicial. El mapa avanzado y la gestión de sensibilidad "
                "espacial se incorporarán en el módulo cartográfico."
            )

        selected_id = st.selectbox(
            "Abrir una evidencia",
            [item.id for item in records],
            format_func=lambda item_id: next(
                f"{item.observation_date:%d/%m/%Y} · {item.display_taxon} · {SOURCE_LABELS[item.source_type]}"
                for item in records
                if item.id == item_id
            ),
        )
        selected = next(item for item in records if item.id == selected_id)
        with st.container(border=True):
            st.markdown(f"#### {selected.display_taxon}")
            if selected.source_type == EvidenceSource.BIOCORE:
                st.success("Registro BioCore · antecedente propio del proyecto")
            else:
                st.warning(
                    f"{SOURCE_LABELS[selected.source_type]} · conserva autoría, URL y licencia"
                )
            st.write(
                f"**Grupo:** {GROUP_LABELS[selected.taxonomic_group]}  \n"
                f"**Identificación:** {IDENTIFICATION_LABELS[selected.identification_status]}  \n"
                f"**Revisión profesional:** {REVIEW_LABELS[selected.professional_review_status]}  \n"
                f"**Autor/observador:** {selected.author_name}  \n"
                f"**Condición de uso:** {selected.license}"
            )
            if selected.source_url:
                st.link_button("Abrir fuente original", selected.source_url)
            st.write(f"**Método:** {selected.observation_method}")
            st.write(f"**Notas:** {selected.notes or 'Sin notas adicionales'}")
            findings = service.quality_findings(selected, records)
            if findings:
                st.markdown("##### Control de calidad determinista")
                for finding in findings:
                    st.markdown(f"**{finding.message}**")
                    st.caption(
                        f"Datos utilizados: {finding.data_used}  \n"
                        f"Regla aplicada: {finding.rule_applied}  \n"
                        f"Próximo paso: {finding.next_step}"
                    )
            try:
                media_urls = service.media_urls(context, selected.id)
                if media_urls:
                    st.markdown("##### Fotografías y referencias")
                    columns = st.columns(min(3, len(media_urls)))
                    for index, (media, url) in enumerate(media_urls):
                        target = columns[index % len(columns)]
                        if url and media.source_type == EvidenceSource.BIOCORE:
                            target.image(
                                url,
                                caption=f"{media.author_name} · {media.license}",
                            )
                        elif url:
                            target.link_button(
                                "Abrir fotografía en la fuente original", url
                            )
                            target.caption(f"{media.author_name} · {media.license}")
                            target.warning(
                                "Referencia externa: BioCore no copió este archivo. "
                                "Revisa la licencia antes de reutilizarlo."
                            )
            except Exception as error:
                _friendly_error(error, operation="media_urls")

            if context.has_permission(Permission.EVIDENCE_WRITE):
                action_request, action_archive = st.columns(2)
                if action_request.button(
                    "Solicitar revisión profesional",
                    disabled=selected.professional_review_status
                    in {
                        ProfessionalReviewStatus.REQUESTED,
                        ProfessionalReviewStatus.UNDER_REVIEW,
                        ProfessionalReviewStatus.APPROVED,
                    },
                    use_container_width=True,
                ):
                    try:
                        service.request_review(context, selected.id)
                        st.session_state[FLASH_KEY] = "Revisión profesional solicitada."
                        st.rerun()
                    except Exception as error:
                        _friendly_error(error, operation="request_review")
                confirm_archive = action_archive.checkbox(
                    "Confirmar archivado",
                    key=f"archive_confirmation_{selected.id}",
                    help="El registro y su historial se conservan; no se elimina físicamente.",
                )
                if action_archive.button(
                    "Archivar evidencia",
                    disabled=not confirm_archive,
                    use_container_width=True,
                ):
                    try:
                        service.archive(context, selected.id)
                        st.session_state[FLASH_KEY] = "Evidencia archivada sin eliminar su historial."
                        st.rerun()
                    except Exception as error:
                        _friendly_error(error, operation="archive")

                with st.expander("Editar datos observados"):
                    with st.form(f"edit_evidence_{selected.id}"):
                        edited = _input_fields(f"edit_{selected.id}", selected)
                        save_edit = st.form_submit_button(
                            "Guardar cambios trazables", type="primary", use_container_width=True
                        )
                    if save_edit:
                        try:
                            service.update(context, selected.id, edited)
                            st.session_state[FLASH_KEY] = "Cambios guardados y registrados en el historial."
                            st.rerun()
                        except Exception as error:
                            _friendly_error(error, operation="update")

                with st.expander("Añadir o archivar fotografías"):
                    with st.form(f"add_media_{selected.id}", clear_on_submit=True):
                        extra_author = st.text_input("Autor de las nuevas fotografías *")
                        extra_license = st.selectbox(
                            "Licencia de las nuevas fotografías *", LICENSE_OPTIONS
                        )
                        extra_photos = st.file_uploader(
                            "Nuevas fotografías privadas",
                            type=("jpg", "jpeg", "png", "webp"),
                            accept_multiple_files=True,
                        )
                        add_media_submitted = st.form_submit_button(
                            "Agregar fotografías", type="primary", use_container_width=True
                        )
                    if add_media_submitted:
                        try:
                            if not extra_photos:
                                raise EvidenceValidationError(
                                    "Selecciona al menos una fotografía."
                                )
                            uploads = tuple(
                                EvidenceUpload(
                                    filename=photo.name,
                                    content_type=photo.type or "application/octet-stream",
                                    payload=photo.getvalue(),
                                    author_name=extra_author,
                                    license=extra_license,
                                )
                                for photo in extra_photos
                            )
                            service.add_media(context, selected.id, uploads)
                            st.session_state[FLASH_KEY] = (
                                "Fotografías agregadas con autoría y licencia."
                            )
                            st.rerun()
                        except Exception as error:
                            _friendly_error(error, operation="add_media")

                    active_media = [
                        item for item in selected.media if item.archived_at is None
                    ]
                    if active_media:
                        media_to_archive = st.selectbox(
                            "Fotografía o referencia que deseas archivar",
                            [item.id for item in active_media],
                            format_func=lambda item_id: next(
                                item.filename
                                for item in active_media
                                if item.id == item_id
                            ),
                            key=f"media_archive_select_{selected.id}",
                        )
                        confirm_media_archive = st.checkbox(
                            "Confirmo el archivado lógico; el objeto privado se conserva para recuperación.",
                            key=f"media_archive_confirm_{selected.id}",
                        )
                        if st.button(
                            "Archivar fotografía",
                            disabled=not confirm_media_archive,
                            key=f"media_archive_button_{selected.id}",
                        ):
                            try:
                                service.archive_media(
                                    context, selected.id, media_to_archive
                                )
                                st.session_state[FLASH_KEY] = (
                                    "Fotografía archivada y cambio registrado en el historial."
                                )
                                st.rerun()
                            except Exception as error:
                                _friendly_error(error, operation="archive_media")

            try:
                history = service.history(context, selected.id)
                with st.expander("Historial de cambios"):
                    if not history:
                        st.info("Aún no hay cambios posteriores a la creación.")
                    for event in history:
                        st.write(
                            f"**{event.event_type}** · {event.created_at:%d/%m/%Y %H:%M}"
                        )
            except Exception as error:
                _friendly_error(error, operation="history")

with new_tab:
    if not context.has_permission(Permission.EVIDENCE_WRITE):
        st.info("Tu acceso es de consulta. Puedes revisar evidencias, pero no crearlas.")
    else:
        st.markdown("### Nuevo registro BioCore")
        st.caption(
            "Registra lo observado y sus limitaciones. No se asignan nombres científicos "
            "automáticos ni se presentan propuestas como hechos confirmados."
        )
        with st.form("new_ecological_evidence", clear_on_submit=True):
            new_data = _input_fields("new")
            photo_author = st.text_input(
                "Autor de las fotografías",
                help="Obligatorio cuando adjuntas fotografías.",
            )
            photo_license = st.selectbox("Licencia de las fotografías", LICENSE_OPTIONS)
            photos = st.file_uploader(
                "Fotografías privadas",
                type=("jpg", "jpeg", "png", "webp"),
                accept_multiple_files=True,
                help="Hasta 10 fotografías de 15 MB. No quedan públicamente accesibles.",
            )
            acknowledged = st.checkbox(
                "Confirmo la autoría/procedencia y que una identificación propuesta requiere revisión."
            )
            create_submitted = st.form_submit_button(
                "Guardar evidencia en el proyecto",
                type="primary",
                use_container_width=True,
                disabled=not acknowledged,
            )
        if create_submitted:
            try:
                if photos and not photo_author.strip():
                    raise EvidenceValidationError(
                        "Informa el autor de las fotografías antes de guardarlas."
                    )
                uploads = tuple(
                    EvidenceUpload(
                        filename=photo.name,
                        content_type=photo.type or "application/octet-stream",
                        payload=photo.getvalue(),
                        author_name=photo_author,
                        license=photo_license,
                        is_primary=index == 0,
                    )
                    for index, photo in enumerate(photos)
                )
                with st.spinner("Guardando evidencia y archivos privados…"):
                    saved = service.create(
                        context, selected_project_id, new_data, uploads
                    )
                st.session_state[FLASH_KEY] = (
                    f"Evidencia {saved.display_taxon} guardada con trazabilidad."
                )
                st.rerun()
            except Exception as error:
                _friendly_error(error, operation="create")

with import_tab:
    st.markdown("### Referenciar una observación de iNaturalist")
    st.info(
        "BioCore consulta la API pública solo cuando tú lo solicitas. Conserva URL, "
        "autoría y licencias; las fotografías externas no se copian al almacenamiento "
        "privado durante este MVP."
    )
    if not context.has_permission(Permission.EVIDENCE_WRITE):
        st.info("Tu acceso es de consulta y no permite importar referencias.")
    else:
        with st.form("inaturalist_import"):
            identifier = st.text_input(
                "URL o ID de observación",
                placeholder="https://www.inaturalist.org/observations/123456",
            )
            accepted_external = st.checkbox(
                "Comprendo que la calidad de iNaturalist no equivale a validación profesional BioCore."
            )
            import_submitted = st.form_submit_button(
                "Importar referencia",
                type="primary",
                disabled=not accepted_external,
                use_container_width=True,
            )
        if import_submitted:
            try:
                with st.spinner("Consultando la observación pública…"):
                    saved = service.import_from_inaturalist(
                        context, selected_project_id, identifier
                    )
                st.session_state[FLASH_KEY] = (
                    f"Referencia iNaturalist {saved.external_id} incorporada sin copiar archivos."
                )
                st.rerun()
            except Exception as error:
                _friendly_error(error, operation="import_inaturalist")

with review_tab:
    all_records = _load_evidence(selected_project_id)
    st.markdown("### Calidad y revisión profesional")
    st.caption(
        "Cada alerta indica los datos utilizados y la regla aplicada. No es una "
        "interpretación automática de biodiversidad ni un pronunciamiento regulatorio."
    )
    pending = [
        item
        for item in all_records
        if item.professional_review_status
        in {
            ProfessionalReviewStatus.REQUESTED,
            ProfessionalReviewStatus.UNDER_REVIEW,
        }
    ]
    st.metric("Solicitudes pendientes", len(pending))
    if not context.has_permission(Permission.EVIDENCE_REVIEW):
        st.info(
            "Puedes solicitar una revisión desde cada registro. La aprobación y "
            "corrección están reservadas a especialistas BioCore."
        )
    elif not pending:
        st.info("No hay evidencias esperando revisión profesional en este proyecto.")
    else:
        review_id = st.selectbox(
            "Evidencia por revisar",
            [item.id for item in pending],
            format_func=lambda item_id: next(
                f"{item.display_taxon} · {item.observation_date:%d/%m/%Y}"
                for item in pending
                if item.id == item_id
            ),
        )
        review_record = next(item for item in pending if item.id == review_id)
        st.write(f"**Dato utilizado:** {review_record.display_taxon}")
        st.write(f"**Fuente:** {SOURCE_LABELS[review_record.source_type]}")
        st.write(f"**Limitación actual:** {IDENTIFICATION_LABELS[review_record.identification_status]}")
        with st.form(f"professional_review_{review_record.id}"):
            review_status = st.selectbox(
                "Resultado de la revisión",
                [
                    ProfessionalReviewStatus.APPROVED,
                    ProfessionalReviewStatus.CORRECTED,
                    ProfessionalReviewStatus.UNCERTAIN,
                ],
                format_func=lambda item: REVIEW_LABELS[item],
            )
            reviewed_scientific_name = st.text_input(
                "Nombre científico revisado",
                value=review_record.scientific_name or "",
            )
            reviewed_common_name = st.text_input(
                "Nombre común revisado", value=review_record.common_name or ""
            )
            review_notes = st.text_area(
                "Fundamento, caracteres revisados e incertidumbres *"
            )
            review_submit = st.form_submit_button(
                "Registrar revisión profesional", type="primary", use_container_width=True
            )
        if review_submit:
            try:
                service.review(
                    context,
                    review_record.id,
                    ProfessionalReviewInput(
                        status=review_status,
                        identification_status=review_record.identification_status,
                        scientific_name=reviewed_scientific_name or None,
                        common_name=reviewed_common_name or None,
                        notes=review_notes,
                    ),
                )
                st.session_state[FLASH_KEY] = "Revisión profesional registrada con responsable y fecha."
                st.rerun()
            except Exception as error:
                _friendly_error(error, operation="professional_review")
