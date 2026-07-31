"""Guided, organization-scoped project experience."""

from __future__ import annotations

import logging
from datetime import date

import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.projects import (
    PROJECT_MODALITY_LABELS,
    PROJECT_STATUS_LABELS,
    Project,
    ProjectFilters,
    ProjectModality,
    ProjectStatus,
)
from biocore.domain.subscriptions import ModuleCode
from biocore.security.authorization import AuthorizationError
from biocore.security.roles import Permission
from biocore.services.projects import (
    ALLOWED_STATUS_TRANSITIONS,
    ProjectChanges,
    ProjectInput,
    ProjectValidationError,
)


LOGGER = logging.getLogger(__name__)
VIEW_KEY = "biocore_projects_view"
SELECTED_KEY = "biocore_selected_project_id"
FLASH_KEY = "biocore_projects_flash"
CREATE_DRAFT_KEY = "biocore_project_create_draft"


context, subscription = require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión ambiental",
    title="Proyectos",
    subtitle=(
        "Comprende el estado de cada proyecto, sus próximos pasos y la "
        "trazabilidad de los cambios desde un solo lugar."
    ),
)

service = st.session_state.get("biocore_project_service")
if service is None or not callable(getattr(service, "list", None)):
    st.error("La sesión de proyectos no está disponible en este momento.")
    st.info(
        "Actualiza la página. Si el problema continúa, cierra sesión e "
        "ingresa nuevamente."
    )
    st.stop()

can_write = context.has_permission(Permission.PROJECTS_WRITE)


def _show_error(error: Exception, *, operation: str) -> None:
    """Translate expected errors and log technical details privately."""

    if isinstance(error, ProjectValidationError):
        st.error(str(error))
        st.caption("Revisa los campos indicados y vuelve a intentarlo.")
        return
    if isinstance(error, AuthorizationError):
        st.warning("Tu rol no permite realizar esta acción.")
        st.caption(
            "Puedes seguir consultando el proyecto o solicitar acceso a una "
            "persona administradora de tu organización."
        )
        return
    if isinstance(error, LookupError):
        st.warning("El proyecto ya no está disponible en esta organización.")
        st.caption("Vuelve al listado para actualizar la información.")
        return

    LOGGER.exception("Project operation failed: %s", operation)
    st.error("No pudimos completar la operación.")
    st.info(
        "Tu información no se modificó. Actualiza la página y vuelve a "
        "intentarlo; si continúa, contacta al equipo BioCore."
    )


def _flash(message: str) -> None:
    st.session_state[FLASH_KEY] = message


def _render_flash() -> None:
    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(str(message), icon="✅")


def _go(view: str, project_id: str | None = None) -> None:
    st.session_state[VIEW_KEY] = view
    if project_id:
        st.session_state[SELECTED_KEY] = project_id
    st.rerun()


def _format_date(value: date | object | None, *, empty: str = "Por definir") -> str:
    if value is None:
        return empty
    return value.strftime("%d/%m/%Y")  # type: ignore[union-attr]


def _project_input(
    *,
    prefix: str,
    defaults: object | None = None,
    include_status: bool = False,
) -> ProjectInput:
    value = defaults

    st.markdown("#### Identificación")
    left, right = st.columns(2)
    name = left.text_input(
        "Nombre del proyecto *",
        value=getattr(value, "name", ""),
        key=f"{prefix}_name",
        help="Usa un nombre reconocible para el equipo y el cliente.",
    )
    code = right.text_input(
        "Código interno *",
        value=getattr(value, "code", ""),
        key=f"{prefix}_code",
        help="Debe ser único en la organización. Ejemplo: BIO-2026-001.",
    )
    client_name = left.text_input(
        "Cliente o entidad asociada *",
        value=getattr(value, "client_name", ""),
        key=f"{prefix}_client",
    )
    project_type = right.text_input(
        "Tipo de proyecto *",
        value=getattr(value, "project_type", ""),
        key=f"{prefix}_type",
        help="Ejemplo: caracterización ecológica o monitoreo de vegetación.",
    )

    st.markdown("#### Ubicación y alcance")
    location_left, location_right = st.columns(2)
    region = location_left.text_input(
        "Región *",
        value=getattr(value, "region", ""),
        key=f"{prefix}_region",
    )
    commune = location_right.text_input(
        "Comuna *",
        value=getattr(value, "commune", ""),
        key=f"{prefix}_commune",
    )
    modality_options = list(ProjectModality)
    current_modality = getattr(value, "modality", ProjectModality.MIXED)
    modality = location_left.selectbox(
        "Modalidad *",
        modality_options,
        index=modality_options.index(current_modality),
        format_func=lambda item: PROJECT_MODALITY_LABELS[item],
        key=f"{prefix}_modality",
        help="Indica si el trabajo será online, en terreno o mixto.",
    )
    current_start = getattr(value, "start_date", None)
    has_start_date = location_right.checkbox(
        "Definir fecha de inicio",
        value=current_start is not None,
        key=f"{prefix}_has_start",
    )
    start_date = (
        location_right.date_input(
            "Fecha de inicio",
            value=current_start or date.today(),
            key=f"{prefix}_start",
        )
        if has_start_date
        else None
    )
    description = st.text_area(
        "Descripción *",
        value=getattr(value, "description", ""),
        key=f"{prefix}_description",
        height=90,
        help="Resume el contexto y el alcance conocido.",
    )
    objective = st.text_area(
        "Objetivo *",
        value=getattr(value, "objective", ""),
        key=f"{prefix}_objective",
        height=90,
        help="Explica qué resultado se espera obtener.",
    )

    st.markdown("#### Seguimiento")
    workflow_left, workflow_right = st.columns(2)
    current_stage = workflow_left.text_input(
        "Etapa actual *",
        value=getattr(value, "current_stage", "Inicio"),
        key=f"{prefix}_stage",
        help="Ejemplo: preparación, campaña de terreno, análisis o cierre.",
    )
    progress_percent = workflow_right.slider(
        "Avance estimado",
        min_value=0,
        max_value=100,
        value=int(getattr(value, "progress_percent", 0)),
        step=5,
        key=f"{prefix}_progress",
        help="Indicador operativo, no una certificación de cumplimiento.",
    )
    responsible_name = workflow_left.text_input(
        "Responsable *",
        value=getattr(value, "responsible_name", "Por asignar"),
        key=f"{prefix}_responsible",
    )
    next_activity = workflow_right.text_input(
        "Próxima actividad relevante *",
        value=getattr(value, "next_activity", "Por definir"),
        key=f"{prefix}_next_activity",
    )
    current_next_date = getattr(value, "next_activity_date", None)
    has_next_date = workflow_right.checkbox(
        "Definir fecha de próxima actividad",
        value=current_next_date is not None,
        key=f"{prefix}_has_next_date",
    )
    next_activity_date = (
        workflow_right.date_input(
            "Fecha de próxima actividad",
            value=current_next_date or date.today(),
            key=f"{prefix}_next_date",
        )
        if has_next_date
        else None
    )

    status = getattr(value, "status", ProjectStatus.PLANNING)
    if include_status:
        status_options = [
            ProjectStatus.PLANNING,
            ProjectStatus.ACTIVE,
            ProjectStatus.PAUSED,
        ]
        status = workflow_left.selectbox(
            "Estado inicial *",
            status_options,
            index=status_options.index(
                status if status in status_options else ProjectStatus.PLANNING
            ),
            format_func=lambda item: PROJECT_STATUS_LABELS[item],
            key=f"{prefix}_status",
        )

    return ProjectInput(
        name=name,
        code=code,
        client_name=client_name,
        project_type=project_type,
        region=region,
        commune=commune,
        modality=modality,
        description=description,
        objective=objective,
        status=status,
        start_date=start_date,
        current_stage=current_stage,
        progress_percent=progress_percent,
        responsible_name=responsible_name,
        next_activity=next_activity,
        next_activity_date=next_activity_date,
    )


def _project_changes(project: Project, draft: ProjectInput) -> ProjectChanges:
    return ProjectChanges(
        name=draft.name,
        code=draft.code,
        client_name=draft.client_name,
        project_type=draft.project_type,
        region=draft.region,
        commune=draft.commune,
        modality=draft.modality,
        description=draft.description,
        objective=draft.objective,
        start_date=draft.start_date,
        start_date_supplied=True,
        current_stage=draft.current_stage,
        progress_percent=draft.progress_percent,
        responsible_name=draft.responsible_name,
        next_activity=draft.next_activity,
        next_activity_date=draft.next_activity_date,
        next_activity_date_supplied=True,
    )


def _is_dirty(project: Project, draft: ProjectInput) -> bool:
    comparable = (
        "name",
        "code",
        "client_name",
        "project_type",
        "region",
        "commune",
        "modality",
        "description",
        "objective",
        "start_date",
        "current_stage",
        "progress_percent",
        "responsible_name",
        "next_activity",
        "next_activity_date",
    )
    return any(getattr(project, name) != getattr(draft, name) for name in comparable)


def _render_project_summary(project: Project) -> None:
    st.markdown(f"### {project.name}")
    st.caption(
        f"{project.code} · {subscription.organization_name} · "
        f"Última actualización {_format_date(project.updated_at)}"
    )
    status_col, stage_col, responsible_col = st.columns(3)
    status_col.metric("Estado general", PROJECT_STATUS_LABELS[project.status])
    stage_col.metric("Etapa actual", project.current_stage)
    responsible_col.metric("Responsable", project.responsible_name)
    st.progress(project.progress_percent, text=f"Avance estimado: {project.progress_percent}%")

    st.markdown("#### Resumen ejecutivo")
    st.write(project.description)
    st.write(f"**Objetivo:** {project.objective}")
    st.write(
        f"**Cliente o entidad:** {project.client_name}  \n"
        f"**Tipo:** {project.project_type}  \n"
        f"**Ubicación:** {project.commune}, {project.region}  \n"
        f"**Modalidad:** {PROJECT_MODALITY_LABELS[project.modality]}"
    )


def _render_timeline(project: Project) -> None:
    st.markdown("#### Línea de tiempo")
    events = [
        ("Proyecto creado", _format_date(project.created_at)),
        ("Inicio previsto", _format_date(project.start_date)),
        ("Última actualización", _format_date(project.updated_at)),
        (
            project.next_activity,
            _format_date(project.next_activity_date),
        ),
    ]
    for label, moment in events:
        st.markdown(f"- **{label}:** {moment}")


def _render_history(project: Project) -> None:
    st.markdown("#### Actividad reciente")
    try:
        with st.spinner("Cargando actividad…"):
            history = service.history(context, project.id)
    except Exception as error:
        _show_error(error, operation="load_history")
        return
    if not history:
        st.info("Aún no hay actividad registrada para este proyecto.")
        return
    event_labels = {
        "created": "Proyecto creado",
        "updated": "Ficha actualizada",
        "status_changed": "Estado actualizado",
        "archived": "Proyecto archivado",
    }
    for event in history[:5]:
        st.markdown(
            f"**{event_labels.get(event.event_type, event.event_type)}**  \n"
            f"{event.created_at.strftime('%d/%m/%Y %H:%M')}"
        )


def _render_list() -> None:
    title_col, action_col = st.columns([4, 1.3])
    title_col.markdown("### Proyectos de la organización")
    if can_write and action_col.button(
        "Crear proyecto", type="primary", use_container_width=True
    ):
        st.session_state.pop(CREATE_DRAFT_KEY, None)
        _go("create")

    filters_col, status_col, modality_col, archived_col = st.columns(
        [2.2, 1.4, 1.4, 1]
    )
    search = filters_col.text_input(
        "Buscar",
        placeholder="Nombre, código, cliente, tipo, región o comuna",
        key="project_search",
    )
    selected_statuses = status_col.multiselect(
        "Estado",
        list(ProjectStatus),
        format_func=lambda item: PROJECT_STATUS_LABELS[item],
        key="project_status_filter",
    )
    selected_modalities = modality_col.multiselect(
        "Modalidad",
        list(ProjectModality),
        format_func=lambda item: PROJECT_MODALITY_LABELS[item],
        key="project_modality_filter",
    )
    include_archived = archived_col.checkbox(
        "Ver archivados", key="project_archived_filter"
    )

    try:
        with st.spinner("Cargando proyectos…"):
            projects = service.list(
                context,
                ProjectFilters(
                    search=search,
                    statuses=frozenset(selected_statuses),
                    modalities=frozenset(selected_modalities),
                    include_archived=include_archived,
                ),
            )
    except Exception as error:
        _show_error(error, operation="list")
        if st.button("Reintentar", key="retry_project_list"):
            st.rerun()
        return

    st.caption(
        f"{len(projects)} proyecto{'s' if len(projects) != 1 else ''} · "
        f"{subscription.organization_name}"
    )
    if not projects:
        st.info(
            "No hay proyectos para mostrar. Ajusta los filtros o crea el "
            "primer proyecto de esta organización."
        )
        if not can_write:
            st.caption(
                "Tu rol es de consulta. Solicita a una persona administradora "
                "que cree el proyecto."
            )
        return

    for project in projects:
        with st.container(border=True):
            heading, state = st.columns([4, 1])
            heading.markdown(f"#### {project.name}")
            heading.caption(f"{project.code} · {subscription.organization_name}")
            state.markdown(f"**{PROJECT_STATUS_LABELS[project.status]}**")
            if project.status == ProjectStatus.ARCHIVED:
                state.caption("Solo lectura")

            stage, progress, responsible, updated = st.columns(4)
            stage.markdown(f"**Etapa**  \n{project.current_stage}")
            progress.markdown(f"**Avance**  \n{project.progress_percent}%")
            responsible.markdown(
                f"**Responsable**  \n{project.responsible_name}"
            )
            updated.markdown(
                f"**Actualizado**  \n{_format_date(project.updated_at)}"
            )
            st.progress(project.progress_percent)
            st.caption(
                f"Próxima actividad: {project.next_activity} · "
                f"{_format_date(project.next_activity_date)}"
            )

            open_col, edit_col, archive_col, spacer = st.columns(
                [1, 1, 1, 2.2]
            )
            if open_col.button(
                "Abrir",
                key=f"open_{project.id}",
                use_container_width=True,
            ):
                _go("detail", project.id)
            if edit_col.button(
                "Editar",
                key=f"edit_{project.id}",
                disabled=not can_write or project.status == ProjectStatus.ARCHIVED,
                use_container_width=True,
            ):
                _go("edit", project.id)
            if archive_col.button(
                "Archivar",
                key=f"archive_{project.id}",
                disabled=not can_write or project.status == ProjectStatus.ARCHIVED,
                use_container_width=True,
            ):
                _go("archive", project.id)


def _render_create() -> None:
    if not can_write:
        st.warning("Tu rol permite consultar proyectos, pero no crearlos.")
        if st.button("Volver al listado"):
            _go("list")
        return

    st.markdown("### Crear proyecto")
    st.caption(
        "Completa la información en bloques. Revisaremos los datos antes de "
        "guardarlos."
    )
    draft = st.session_state.get(CREATE_DRAFT_KEY)

    if not isinstance(draft, ProjectInput):
        with st.form("create_project_form"):
            candidate = _project_input(
                prefix="create_project",
                include_status=True,
            )
            review = st.form_submit_button(
                "Revisar datos",
                type="primary",
                use_container_width=True,
            )
        cancel_col, _ = st.columns([1, 4])
        if cancel_col.button("Cancelar", use_container_width=True):
            _go("list")
        if review:
            try:
                st.session_state[CREATE_DRAFT_KEY] = service.validate_input(
                    candidate
                )
                st.rerun()
            except Exception as error:
                _show_error(error, operation="validate_create")
        return

    st.success("Los datos obligatorios están completos.")
    st.markdown("#### Confirma antes de crear")
    review_left, review_right = st.columns(2)
    review_left.write(
        f"**Proyecto:** {draft.name}  \n"
        f"**Código:** {draft.code}  \n"
        f"**Cliente:** {draft.client_name}  \n"
        f"**Tipo:** {draft.project_type}  \n"
        f"**Ubicación:** {draft.commune}, {draft.region}"
    )
    review_right.write(
        f"**Estado:** {PROJECT_STATUS_LABELS[draft.status]}  \n"
        f"**Etapa:** {draft.current_stage}  \n"
        f"**Avance:** {draft.progress_percent}%  \n"
        f"**Responsable:** {draft.responsible_name}  \n"
        f"**Próxima actividad:** {draft.next_activity}"
    )
    st.info(
        "Al confirmar, el proyecto quedará disponible solo para la "
        "organización activa y se registrará quién lo creó."
    )
    confirm_col, edit_col, cancel_col = st.columns(3)
    if confirm_col.button(
        "Confirmar y crear", type="primary", use_container_width=True
    ):
        try:
            with st.spinner("Creando el proyecto…"):
                created = service.create(context, draft)
            st.session_state.pop(CREATE_DRAFT_KEY, None)
            _flash(
                f"Proyecto {created.code} creado. Ya estás en su portada."
            )
            _go("detail", created.id)
        except Exception as error:
            _show_error(error, operation="create")
    if edit_col.button("Corregir datos", use_container_width=True):
        st.session_state.pop(CREATE_DRAFT_KEY, None)
        st.rerun()
    if cancel_col.button("Cancelar", use_container_width=True):
        st.session_state.pop(CREATE_DRAFT_KEY, None)
        _go("list")


def _load_selected_project() -> Project | None:
    project_id = st.session_state.get(SELECTED_KEY)
    if not project_id:
        st.info("Selecciona un proyecto desde el listado.")
        if st.button("Ir al listado"):
            _go("list")
        return None
    try:
        with st.spinner("Cargando proyecto…"):
            return service.get(context, str(project_id))
    except Exception as error:
        _show_error(error, operation="get")
        if st.button("Volver al listado"):
            _go("list")
        return None


def _render_detail() -> None:
    project = _load_selected_project()
    if project is None:
        return

    back, edit, state, archive, _ = st.columns([1, 1, 1.2, 1, 2])
    if back.button("← Proyectos", use_container_width=True):
        _go("list")
    if edit.button(
        "Editar",
        disabled=not can_write or project.status == ProjectStatus.ARCHIVED,
        use_container_width=True,
    ):
        _go("edit", project.id)
    allowed = [
        status
        for status in ALLOWED_STATUS_TRANSITIONS[project.status]
        if status != ProjectStatus.ARCHIVED
    ]
    target = state.selectbox(
        "Cambiar estado",
        allowed or [project.status],
        format_func=lambda item: PROJECT_STATUS_LABELS[item],
        label_visibility="collapsed",
        disabled=not can_write or not allowed,
        key=f"detail_status_{project.id}",
    )
    if state.button(
        "Aplicar estado",
        disabled=not can_write or not allowed,
        key=f"apply_status_{project.id}",
        use_container_width=True,
    ):
        try:
            service.change_status(context, project.id, target)
            _flash("Estado actualizado correctamente.")
            st.rerun()
        except Exception as error:
            _show_error(error, operation="change_status")
    if archive.button(
        "Archivar",
        disabled=not can_write or project.status == ProjectStatus.ARCHIVED,
        use_container_width=True,
    ):
        _go("archive", project.id)

    if project.status == ProjectStatus.ARCHIVED:
        st.info(
            "Este proyecto está archivado. Su información e historial se "
            "conservan en modo de consulta."
        )

    _render_project_summary(project)

    next_col, timeline_col = st.columns(2)
    with next_col:
        st.markdown("#### Próximo hito")
        st.info(
            f"**{project.next_activity}**  \n"
            f"{_format_date(project.next_activity_date)}"
        )
        st.markdown("#### Documentos y registros recientes")
        st.caption(
            "Aún no hay documentos vinculados a este proyecto. Cuando se "
            "incorporen, aparecerán aquí sin necesidad de revisar otra pantalla."
        )
    with timeline_col:
        _render_timeline(project)

    _render_history(project)


def _render_edit() -> None:
    project = _load_selected_project()
    if project is None:
        return
    if not can_write:
        st.warning("Tu rol no permite editar proyectos.")
        if st.button("Volver al proyecto"):
            _go("detail", project.id)
        return
    if project.status == ProjectStatus.ARCHIVED:
        st.info("Un proyecto archivado se mantiene en modo de consulta.")
        if st.button("Volver al proyecto"):
            _go("detail", project.id)
        return

    st.markdown(f"### Editar {project.name}")
    st.caption(
        f"Última modificación: {_format_date(project.updated_at)} · "
        "Los cambios se atribuirán al usuario de la sesión actual."
    )
    draft = _project_input(
        prefix=f"edit_project_{project.id}",
        defaults=project,
    )
    dirty = _is_dirty(project, draft)
    if dirty:
        st.warning(
            "Tienes cambios sin guardar. Si vuelves al proyecto o recargas la "
            "página, estos cambios se perderán."
        )
    else:
        st.info("No hay cambios pendientes.")

    save_col, discard_col, _ = st.columns([1.2, 1.2, 3])
    if save_col.button(
        "Guardar cambios",
        type="primary",
        disabled=not dirty,
        use_container_width=True,
    ):
        try:
            service.validate_input(draft)
            with st.spinner("Guardando cambios…"):
                service.update(context, project.id, _project_changes(project, draft))
            _flash("Cambios guardados y registrados en la actividad reciente.")
            _go("detail", project.id)
        except Exception as error:
            _show_error(error, operation="update")
    confirm_discard = discard_col.checkbox(
        "Descartar cambios",
        disabled=not dirty,
        key=f"discard_edit_{project.id}",
    )
    if discard_col.button(
        "Volver al proyecto",
        disabled=dirty and not confirm_discard,
        use_container_width=True,
    ):
        _go("detail", project.id)


def _render_archive() -> None:
    project = _load_selected_project()
    if project is None:
        return
    if not can_write:
        st.warning("Tu rol no permite archivar proyectos.")
        if st.button("Volver al proyecto"):
            _go("detail", project.id)
        return

    st.markdown(f"### Archivar {project.name}")
    st.warning(
        "Archivar no elimina el proyecto. Lo retira del listado de activos, "
        "bloquea su edición y conserva su información e historial."
    )
    st.write(
        f"**Código:** {project.code}  \n"
        f"**Etapa actual:** {project.current_stage}  \n"
        f"**Avance registrado:** {project.progress_percent}%  \n"
        f"**Próxima actividad:** {project.next_activity}"
    )
    confirmed = st.checkbox(
        "Comprendo las consecuencias y confirmo el archivado",
        key=f"confirm_archive_{project.id}",
    )
    archive_col, cancel_col, _ = st.columns([1.2, 1, 3])
    if archive_col.button(
        "Archivar proyecto",
        type="primary",
        disabled=not confirmed,
        use_container_width=True,
    ):
        try:
            with st.spinner("Archivando sin eliminar información…"):
                service.archive(context, project.id)
            _flash(
                "Proyecto archivado. Puedes consultarlo activando “Ver "
                "archivados” en el listado."
            )
            _go("list")
        except Exception as error:
            _show_error(error, operation="archive")
    if cancel_col.button("Cancelar", use_container_width=True):
        _go("detail", project.id)


_render_flash()
view = str(st.session_state.get(VIEW_KEY, "list"))
if view == "create":
    _render_create()
elif view == "detail":
    _render_detail()
elif view == "edit":
    _render_edit()
elif view == "archive":
    _render_archive()
else:
    st.session_state[VIEW_KEY] = "list"
    _render_list()
