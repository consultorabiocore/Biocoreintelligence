from datetime import date

import streamlit as st

from biocore.components.module_access import require_module_page
from biocore.domain.projects import (
    PROJECT_MODALITY_LABELS,
    PROJECT_STATUS_LABELS,
    ProjectFilters,
    ProjectModality,
    ProjectStatus,
)
from biocore.domain.subscriptions import ModuleCode
from biocore.security.roles import Permission
from biocore.services.projects import (
    ALLOWED_STATUS_TRANSITIONS,
    ProjectChanges,
    ProjectInput,
    ProjectValidationError,
)


context, _ = require_module_page(
    ModuleCode.PLATFORM_CORE,
    kicker="Gestión ambiental",
    title="Proyectos",
    subtitle=(
        "Organiza áreas de estudio, equipos, campañas y productos bajo un "
        "mismo historial ambiental."
    ),
)

service = st.session_state.get("biocore_project_service")
if service is None or not callable(getattr(service, "list", None)):
    st.error("El servicio de proyectos no está disponible en esta sesión.")
    st.stop()

can_write = context.has_permission(Permission.PROJECTS_WRITE)


def _show_error(error: Exception) -> None:
    if isinstance(error, (ProjectValidationError, LookupError)):
        st.error(str(error))
    else:
        st.error(
            "No fue posible completar la operación. Verifica que la migración "
            "0008 esté aplicada e inténtalo nuevamente."
        )


def _project_input(
    *,
    prefix: str,
    defaults: object | None = None,
) -> tuple[ProjectInput, bool]:
    value = defaults
    left, right = st.columns(2)
    name = left.text_input(
        "Nombre del proyecto",
        value=getattr(value, "name", ""),
        key=f"{prefix}_name",
    )
    code = right.text_input(
        "Código interno",
        value=getattr(value, "code", ""),
        key=f"{prefix}_code",
        help="Único dentro de la organización. Ejemplo: BIO-2026-001.",
    )
    client_name = left.text_input(
        "Cliente o entidad asociada",
        value=getattr(value, "client_name", ""),
        key=f"{prefix}_client",
    )
    project_type = right.text_input(
        "Tipo de proyecto",
        value=getattr(value, "project_type", ""),
        key=f"{prefix}_type",
    )
    region = left.text_input(
        "Región",
        value=getattr(value, "region", ""),
        key=f"{prefix}_region",
    )
    commune = right.text_input(
        "Comuna",
        value=getattr(value, "commune", ""),
        key=f"{prefix}_commune",
    )
    modality_options = list(ProjectModality)
    current_modality = getattr(value, "modality", ProjectModality.MIXED)
    modality = left.selectbox(
        "Modalidad",
        modality_options,
        index=modality_options.index(current_modality),
        format_func=lambda item: PROJECT_MODALITY_LABELS[item],
        key=f"{prefix}_modality",
    )
    current_start = getattr(value, "start_date", None)
    has_start_date = right.checkbox(
        "Definir fecha de inicio",
        value=current_start is not None,
        key=f"{prefix}_has_start",
    )
    start_date = (
        right.date_input(
            "Fecha de inicio",
            value=current_start or date.today(),
            key=f"{prefix}_start",
        )
        if has_start_date
        else None
    )
    description = st.text_area(
        "Descripción",
        value=getattr(value, "description", ""),
        key=f"{prefix}_description",
        height=100,
    )
    objective = st.text_area(
        "Objetivo",
        value=getattr(value, "objective", ""),
        key=f"{prefix}_objective",
        height=100,
    )
    return (
        ProjectInput(
            name=name,
            code=code,
            client_name=client_name,
            project_type=project_type,
            region=region,
            commune=commune,
            modality=modality,
            description=description,
            objective=objective,
            start_date=start_date,
        ),
        has_start_date,
    )


filters_col, status_col, modality_col, archived_col = st.columns([2.2, 1.4, 1.4, 1])
search = filters_col.text_input(
    "Buscar",
    placeholder="Nombre, código, cliente, tipo, región o comuna",
)
selected_statuses = status_col.multiselect(
    "Estado",
    list(ProjectStatus),
    format_func=lambda item: PROJECT_STATUS_LABELS[item],
)
selected_modalities = modality_col.multiselect(
    "Modalidad",
    list(ProjectModality),
    format_func=lambda item: PROJECT_MODALITY_LABELS[item],
)
include_archived = archived_col.checkbox("Ver archivados")

try:
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
    _show_error(error)
    st.stop()

st.caption(
    f"{len(projects)} proyecto{'s' if len(projects) != 1 else ''} "
    "en la organización activa."
)

if projects:
    st.dataframe(
        [
            {
                "Código": project.code,
                "Proyecto": project.name,
                "Cliente / entidad": project.client_name,
                "Tipo": project.project_type,
                "Ubicación": f"{project.commune}, {project.region}",
                "Modalidad": PROJECT_MODALITY_LABELS[project.modality],
                "Estado": PROJECT_STATUS_LABELS[project.status],
                "Actualizado": project.updated_at.strftime("%d/%m/%Y"),
            }
            for project in projects
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "No hay proyectos que coincidan con los filtros. "
        "No se muestran datos de demostración."
    )

detail_tab, create_tab = st.tabs(
    ["Abrir proyecto", "Crear proyecto" if can_write else "Creación restringida"]
)

with create_tab:
    if not can_write:
        st.info("Tu rol permite consultar proyectos, pero no crearlos ni editarlos.")
    else:
        st.subheader("Nuevo proyecto")
        with st.form("create_project_form", clear_on_submit=True):
            new_project, _ = _project_input(prefix="create")
            status_options = [
                ProjectStatus.PLANNING,
                ProjectStatus.ACTIVE,
                ProjectStatus.PAUSED,
            ]
            new_status = st.selectbox(
                "Estado inicial",
                status_options,
                format_func=lambda item: PROJECT_STATUS_LABELS[item],
            )
            submitted = st.form_submit_button(
                "Crear proyecto", type="primary", use_container_width=True
            )
        if submitted:
            try:
                created = service.create(
                    context,
                    ProjectInput(
                        **{
                            **new_project.__dict__,
                            "status": new_status,
                        }
                    ),
                )
                st.session_state["biocore_selected_project_id"] = created.id
                st.success(f"Proyecto {created.code} creado correctamente.")
                st.rerun()
            except Exception as error:
                _show_error(error)

with detail_tab:
    if not projects:
        st.caption("Crea un proyecto o ajusta los filtros para abrir su ficha.")
    else:
        project_ids = [project.id for project in projects]
        selected_id = st.session_state.get("biocore_selected_project_id")
        selected_index = (
            project_ids.index(selected_id) if selected_id in project_ids else 0
        )
        selected_project_id = st.selectbox(
            "Proyecto",
            project_ids,
            index=selected_index,
            format_func=lambda project_id: next(
                f"{project.code} · {project.name}"
                for project in projects
                if project.id == project_id
            ),
        )
        st.session_state["biocore_selected_project_id"] = selected_project_id
        try:
            project = service.get(context, selected_project_id)
        except Exception as error:
            _show_error(error)
            st.stop()

        st.markdown(f"### {project.name}")
        summary_left, summary_middle, summary_right = st.columns(3)
        summary_left.metric("Código", project.code)
        summary_middle.metric("Estado", PROJECT_STATUS_LABELS[project.status])
        summary_right.metric(
            "Modalidad", PROJECT_MODALITY_LABELS[project.modality]
        )
        start_label = (
            project.start_date.strftime("%d/%m/%Y")
            if project.start_date
            else "Sin definir"
        )
        st.write(
            f"**Cliente o entidad:** {project.client_name}  \n"
            f"**Tipo:** {project.project_type}  \n"
            f"**Ubicación:** {project.commune}, {project.region}  \n"
            f"**Inicio:** {start_label}"
        )
        st.write(f"**Descripción:** {project.description}")
        st.write(f"**Objetivo:** {project.objective}")

        if can_write and project.status != ProjectStatus.ARCHIVED:
            edit_panel, status_panel = st.tabs(["Editar ficha", "Estado y archivo"])
            with edit_panel:
                with st.form(f"edit_project_{project.id}"):
                    edited, _ = _project_input(
                        prefix=f"edit_{project.id}", defaults=project
                    )
                    save_edit = st.form_submit_button(
                        "Guardar cambios", type="primary"
                    )
                if save_edit:
                    try:
                        service.update(
                            context,
                            project.id,
                            ProjectChanges(
                                name=edited.name,
                                code=edited.code,
                                client_name=edited.client_name,
                                project_type=edited.project_type,
                                region=edited.region,
                                commune=edited.commune,
                                modality=edited.modality,
                                description=edited.description,
                                objective=edited.objective,
                                start_date=edited.start_date,
                                start_date_supplied=True,
                            ),
                        )
                        st.success("Ficha actualizada.")
                        st.rerun()
                    except Exception as error:
                        _show_error(error)

            with status_panel:
                allowed = [
                    status
                    for status in ALLOWED_STATUS_TRANSITIONS[project.status]
                    if status != ProjectStatus.ARCHIVED
                ]
                if allowed:
                    target_status = st.selectbox(
                        "Nuevo estado",
                        allowed,
                        format_func=lambda item: PROJECT_STATUS_LABELS[item],
                    )
                    if st.button("Cambiar estado", type="secondary"):
                        try:
                            service.change_status(
                                context, project.id, target_status
                            )
                            st.success("Estado actualizado.")
                            st.rerun()
                        except Exception as error:
                            _show_error(error)
                confirm_archive = st.checkbox(
                    "Confirmo que deseo archivar este proyecto",
                    key=f"archive_confirm_{project.id}",
                )
                if st.button(
                    "Archivar proyecto",
                    disabled=not confirm_archive,
                    type="secondary",
                ):
                    try:
                        service.archive(context, project.id)
                        st.success("Proyecto archivado sin eliminar su historial.")
                        st.rerun()
                    except Exception as error:
                        _show_error(error)

        with st.expander("Historial básico"):
            try:
                history = service.history(context, project.id)
                if not history:
                    st.caption("Aún no hay eventos registrados.")
                for event in history:
                    st.markdown(
                        f"**{event.event_type.replace('_', ' ').title()}** · "
                        f"{event.created_at.strftime('%d/%m/%Y %H:%M')}"
                    )
                    if event.changes:
                        st.json(event.changes, expanded=False)
            except Exception as error:
                _show_error(error)
