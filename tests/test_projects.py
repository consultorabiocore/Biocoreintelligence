from dataclasses import replace
from datetime import date

import pytest

from biocore.domain.projects import (
    Project,
    ProjectFilters,
    ProjectHistoryEntry,
    ProjectModality,
    ProjectStatus,
)
from biocore.security.authorization import AuthorizationError, UserContext
from biocore.security.roles import Role
from biocore.services.projects import (
    ProjectChanges,
    ProjectConflictError,
    ProjectInput,
    ProjectService,
    ProjectValidationError,
)


class InMemoryProjectRepository:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.events: list[ProjectHistoryEntry] = []

    def create(self, project: Project) -> Project:
        self.projects[project.id] = project
        return project

    def update(self, project: Project) -> Project:
        current = self.projects.get(project.id)
        if current is None or current.organization_id != project.organization_id:
            raise LookupError
        self.projects[project.id] = project
        return project

    def get(self, organization_id: str, project_id: str) -> Project | None:
        project = self.projects.get(project_id)
        if project is None or project.organization_id != organization_id:
            return None
        return project

    def list_for_organization(
        self, organization_id: str, *, include_archived: bool = False
    ) -> tuple[Project, ...]:
        return tuple(
            project
            for project in self.projects.values()
            if project.organization_id == organization_id
            and (include_archived or project.status != ProjectStatus.ARCHIVED)
        )

    def code_exists(
        self,
        organization_id: str,
        code: str,
        *,
        exclude_project_id: str | None = None,
    ) -> bool:
        return any(
            project.organization_id == organization_id
            and project.code.casefold() == code.casefold()
            and project.id != exclude_project_id
            for project in self.projects.values()
        )

    def append_history(self, entry: ProjectHistoryEntry) -> None:
        self.events.append(entry)

    def list_history(
        self, organization_id: str, project_id: str
    ) -> tuple[ProjectHistoryEntry, ...]:
        return tuple(
            event
            for event in reversed(self.events)
            if event.organization_id == organization_id
            and event.project_id == project_id
        )


def context(
    role: Role = Role.CLIENT_ADMIN,
    organization_id: str = "org-a",
    user_id: str = "user-1",
) -> UserContext:
    return UserContext(user_id, organization_id, frozenset({role}))


def project_input(
    *,
    code: str = "bio-2026-001",
    name: str = "Línea base bosque",
    status: ProjectStatus = ProjectStatus.PLANNING,
) -> ProjectInput:
    return ProjectInput(
        name=name,
        code=code,
        client_name="Entidad solicitante",
        project_type="Caracterización ecológica",
        region="Los Lagos",
        commune="Puerto Montt",
        modality=ProjectModality.MIXED,
        description="Levantamiento y organización de antecedentes ecológicos.",
        objective="Consolidar información para análisis técnico.",
        status=status,
        start_date=date(2026, 8, 1),
        current_stage="Preparación",
        progress_percent=15,
        responsible_name="Especialista BioCore",
        next_activity="Revisar antecedentes",
        next_activity_date=date(2026, 8, 5),
    )


def test_create_normalizes_code_and_records_creator_and_history() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)

    project = service.create(context(), project_input())

    assert project.code == "BIO-2026-001"
    assert project.organization_id == "org-a"
    assert project.created_by_user_id == "user-1"
    assert project.current_stage == "Preparación"
    assert project.progress_percent == 15
    assert project.next_activity_date == date(2026, 8, 5)
    assert service.history(context(), project.id)[0].event_type == "created"


def test_list_and_open_are_isolated_by_organization() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    own = service.create(context(), project_input())
    service.create(
        context(organization_id="org-b", user_id="user-2"),
        project_input(code="BIO-B-001", name="Proyecto ajeno"),
    )

    listed = service.list(context())

    assert listed == (own,)
    with pytest.raises(LookupError):
        service.get(context(organization_id="org-b"), own.id)


def test_search_and_filters_cover_business_fields() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    service.create(context(), project_input())
    second = service.create(
        context(),
        replace(
            project_input(code="BIO-2026-002", name="Monitoreo costero"),
            region="Valparaíso",
            modality=ProjectModality.FIELD,
            status=ProjectStatus.ACTIVE,
        ),
    )

    found = service.list(
        context(),
        ProjectFilters(
            search="valpara",
            statuses=frozenset({ProjectStatus.ACTIVE}),
            modalities=frozenset({ProjectModality.FIELD}),
        ),
    )

    assert found == (second,)


def test_duplicate_code_is_rejected_only_inside_same_organization() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    service.create(context(), project_input())

    with pytest.raises(ProjectConflictError):
        service.create(context(), project_input(code="BIO-2026-001"))

    other = service.create(
        context(organization_id="org-b"),
        project_input(code="BIO-2026-001"),
    )
    assert other.organization_id == "org-b"


def test_edit_status_and_archive_keep_a_basic_history() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    project = service.create(context(), project_input())

    updated = service.update(
        context(),
        project.id,
        ProjectChanges(
            name="Línea base ecológica actualizada",
            objective="Preparar campañas comparables.",
            current_stage="Campaña de terreno",
            progress_percent=45,
            responsible_name="Equipo de terreno",
            next_activity="Validar registros",
            next_activity_date=date(2026, 9, 1),
            next_activity_date_supplied=True,
        ),
    )
    active = service.change_status(
        context(), project.id, ProjectStatus.ACTIVE
    )
    archived = service.archive(context(), project.id)

    assert updated.name == "Línea base ecológica actualizada"
    assert updated.current_stage == "Campaña de terreno"
    assert updated.progress_percent == 45
    assert updated.next_activity == "Validar registros"
    assert active.status == ProjectStatus.ACTIVE
    assert archived.status == ProjectStatus.ARCHIVED
    assert archived.archived_at is not None
    assert service.list(context()) == ()
    assert service.list(
        context(), ProjectFilters(include_archived=True)
    ) == (archived,)
    assert [event.event_type for event in service.history(context(), project.id)] == [
        "archived",
        "status_changed",
        "updated",
        "created",
    ]


def test_archived_projects_cannot_be_edited_or_reactivated() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    project = service.create(context(), project_input())
    service.archive(context(), project.id)

    with pytest.raises(ProjectValidationError):
        service.update(
            context(), project.id, ProjectChanges(name="Cambio no permitido")
        )
    with pytest.raises(ProjectValidationError):
        service.change_status(
            context(), project.id, ProjectStatus.ACTIVE
        )


def test_reader_can_list_but_cannot_create_edit_or_archive() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    project = service.create(context(), project_input())
    reader = context(Role.CLIENT_READER, user_id="reader-1")

    assert service.list(reader) == (project,)
    with pytest.raises(AuthorizationError):
        service.create(reader, project_input(code="BIO-READER"))
    with pytest.raises(AuthorizationError):
        service.update(reader, project.id, ProjectChanges(name="No autorizado"))
    with pytest.raises(AuthorizationError):
        service.archive(reader, project.id)


def test_required_fields_and_initial_status_are_validated() -> None:
    service = ProjectService(InMemoryProjectRepository())
    with pytest.raises(ProjectValidationError):
        service.create(context(), replace(project_input(), name="  "))
    with pytest.raises(ProjectValidationError):
        service.create(
            context(),
            replace(project_input(), status=ProjectStatus.ARCHIVED),
        )
    with pytest.raises(ProjectValidationError):
        service.validate_input(
            replace(project_input(), progress_percent=101)
        )
    with pytest.raises(ProjectValidationError):
        service.validate_input(
            replace(project_input(), responsible_name="  ")
        )
