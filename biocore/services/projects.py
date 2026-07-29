"""Application service for organization-scoped project management."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from uuid import uuid4

from biocore.domain.projects import (
    Project,
    ProjectFilters,
    ProjectHistoryEntry,
    ProjectModality,
    ProjectStatus,
)
from biocore.repositories.projects import ProjectRepository
from biocore.security.authorization import UserContext, require_permission
from biocore.security.roles import Permission


CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{1,47}$")


class ProjectValidationError(ValueError):
    """Raised when project input is incomplete or inconsistent."""


class ProjectConflictError(ProjectValidationError):
    """Raised when a unique business identifier already exists."""


@dataclass(frozen=True)
class ProjectInput:
    name: str
    code: str
    client_name: str
    project_type: str
    region: str
    commune: str
    modality: ProjectModality
    description: str
    objective: str
    status: ProjectStatus = ProjectStatus.PLANNING
    start_date: date | None = None


@dataclass(frozen=True)
class ProjectChanges:
    name: str | None = None
    code: str | None = None
    client_name: str | None = None
    project_type: str | None = None
    region: str | None = None
    commune: str | None = None
    modality: ProjectModality | None = None
    description: str | None = None
    objective: str | None = None
    start_date: date | None = None
    start_date_supplied: bool = False


ALLOWED_STATUS_TRANSITIONS: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    ProjectStatus.PLANNING: frozenset(
        {ProjectStatus.ACTIVE, ProjectStatus.PAUSED, ProjectStatus.ARCHIVED}
    ),
    ProjectStatus.ACTIVE: frozenset(
        {ProjectStatus.PAUSED, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED}
    ),
    ProjectStatus.PAUSED: frozenset(
        {ProjectStatus.ACTIVE, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED}
    ),
    ProjectStatus.COMPLETED: frozenset(
        {ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED}
    ),
    ProjectStatus.ARCHIVED: frozenset(),
}


def _normalized_text(value: str, label: str, *, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ProjectValidationError(f"{label} es obligatorio")
    if len(normalized) > maximum:
        raise ProjectValidationError(
            f"{label} no puede superar {maximum} caracteres"
        )
    return normalized


def _normalized_code(value: str) -> str:
    code = value.strip().upper()
    if not CODE_PATTERN.fullmatch(code):
        raise ProjectValidationError(
            "El código debe tener 2 a 48 caracteres y usar letras, números, "
            "punto, guion, barra o guion bajo"
        )
    return code


def _serializable(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (ProjectStatus, ProjectModality)):
        return value.value
    return value


class ProjectService:
    """Enforce permissions, validation, tenant isolation and history."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    def _validated_input(self, data: ProjectInput) -> ProjectInput:
        return ProjectInput(
            name=_normalized_text(data.name, "El nombre", maximum=160),
            code=_normalized_code(data.code),
            client_name=_normalized_text(
                data.client_name, "El cliente o entidad", maximum=160
            ),
            project_type=_normalized_text(
                data.project_type, "El tipo de proyecto", maximum=120
            ),
            region=_normalized_text(data.region, "La región", maximum=120),
            commune=_normalized_text(data.commune, "La comuna", maximum=120),
            modality=ProjectModality(data.modality),
            description=_normalized_text(
                data.description, "La descripción", maximum=2000
            ),
            objective=_normalized_text(data.objective, "El objetivo", maximum=2000),
            status=ProjectStatus(data.status),
            start_date=data.start_date,
        )

    def _append_history(
        self,
        project: Project,
        actor_user_id: str,
        event_type: str,
        changes: dict[str, object],
    ) -> None:
        self._repository.append_history(
            ProjectHistoryEntry(
                id=str(uuid4()),
                project_id=project.id,
                organization_id=project.organization_id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                changes=changes,
                created_at=datetime.utcnow(),
            )
        )

    def create(self, context: UserContext, data: ProjectInput) -> Project:
        require_permission(context, Permission.PROJECTS_WRITE)
        validated = self._validated_input(data)
        if validated.status not in {
            ProjectStatus.PLANNING,
            ProjectStatus.ACTIVE,
            ProjectStatus.PAUSED,
        }:
            raise ProjectValidationError(
                "El estado inicial debe ser planificación, activo o pausado"
            )
        if self._repository.code_exists(
            context.organization_id, validated.code
        ):
            raise ProjectConflictError(
                "Ya existe un proyecto con ese código en la organización"
            )
        now = datetime.utcnow()
        project = Project(
            id=str(uuid4()),
            organization_id=context.organization_id,
            name=validated.name,
            code=validated.code,
            client_name=validated.client_name,
            project_type=validated.project_type,
            region=validated.region,
            commune=validated.commune,
            modality=validated.modality,
            description=validated.description,
            objective=validated.objective,
            status=validated.status,
            start_date=validated.start_date,
            created_by_user_id=context.user_id,
            updated_by_user_id=context.user_id,
            created_at=now,
            updated_at=now,
        )
        saved = self._repository.create(project)
        self._append_history(
            saved,
            context.user_id,
            "created",
            {"status": saved.status.value},
        )
        return saved

    def list(
        self,
        context: UserContext,
        filters: ProjectFilters | None = None,
    ) -> tuple[Project, ...]:
        require_permission(context, Permission.PROJECTS_READ)
        selected = filters or ProjectFilters()
        projects = self._repository.list_for_organization(
            context.organization_id,
            include_archived=selected.include_archived,
        )
        query = selected.search.strip().casefold()
        result = []
        for project in projects:
            if selected.statuses and project.status not in selected.statuses:
                continue
            if selected.modalities and project.modality not in selected.modalities:
                continue
            if query and not any(
                query in value.casefold()
                for value in (
                    project.name,
                    project.code,
                    project.client_name,
                    project.project_type,
                    project.region,
                    project.commune,
                )
            ):
                continue
            result.append(project)
        return tuple(result)

    def get(self, context: UserContext, project_id: str) -> Project:
        require_permission(context, Permission.PROJECTS_READ)
        project = self._repository.get(context.organization_id, project_id)
        if project is None:
            raise LookupError("Proyecto no encontrado en esta organización")
        return project

    def history(
        self, context: UserContext, project_id: str
    ) -> tuple[ProjectHistoryEntry, ...]:
        self.get(context, project_id)
        return self._repository.list_history(
            context.organization_id, project_id
        )

    def update(
        self,
        context: UserContext,
        project_id: str,
        changes: ProjectChanges,
    ) -> Project:
        require_permission(context, Permission.PROJECTS_WRITE)
        current = self.get(context, project_id)
        if current.status == ProjectStatus.ARCHIVED:
            raise ProjectValidationError(
                "Un proyecto archivado no puede editarse"
            )

        values = {
            "name": changes.name if changes.name is not None else current.name,
            "code": changes.code if changes.code is not None else current.code,
            "client_name": (
                changes.client_name
                if changes.client_name is not None
                else current.client_name
            ),
            "project_type": (
                changes.project_type
                if changes.project_type is not None
                else current.project_type
            ),
            "region": (
                changes.region if changes.region is not None else current.region
            ),
            "commune": (
                changes.commune if changes.commune is not None else current.commune
            ),
            "modality": changes.modality or current.modality,
            "description": (
                changes.description
                if changes.description is not None
                else current.description
            ),
            "objective": (
                changes.objective
                if changes.objective is not None
                else current.objective
            ),
            "status": current.status,
            "start_date": (
                changes.start_date
                if changes.start_date_supplied
                else current.start_date
            ),
        }
        validated = self._validated_input(ProjectInput(**values))
        if validated.code != current.code and self._repository.code_exists(
            context.organization_id,
            validated.code,
            exclude_project_id=current.id,
        ):
            raise ProjectConflictError(
                "Ya existe un proyecto con ese código en la organización"
            )
        updated = replace(
            current,
            name=validated.name,
            code=validated.code,
            client_name=validated.client_name,
            project_type=validated.project_type,
            region=validated.region,
            commune=validated.commune,
            modality=validated.modality,
            description=validated.description,
            objective=validated.objective,
            start_date=validated.start_date,
            updated_by_user_id=context.user_id,
            updated_at=datetime.utcnow(),
        )
        saved = self._repository.update(updated)
        field_changes = {
            field: {
                "from": _serializable(getattr(current, field)),
                "to": _serializable(getattr(saved, field)),
            }
            for field in (
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
            )
            if getattr(current, field) != getattr(saved, field)
        }
        if field_changes:
            self._append_history(
                saved, context.user_id, "updated", field_changes
            )
        return saved

    def change_status(
        self,
        context: UserContext,
        project_id: str,
        status: ProjectStatus,
    ) -> Project:
        require_permission(context, Permission.PROJECTS_WRITE)
        current = self.get(context, project_id)
        target = ProjectStatus(status)
        if target == current.status:
            return current
        if target not in ALLOWED_STATUS_TRANSITIONS[current.status]:
            raise ProjectValidationError(
                f"No se puede cambiar de {current.status.value} a {target.value}"
            )
        if target == ProjectStatus.ARCHIVED:
            return self.archive(context, project_id)
        updated = replace(
            current,
            status=target,
            updated_by_user_id=context.user_id,
            updated_at=datetime.utcnow(),
        )
        saved = self._repository.update(updated)
        self._append_history(
            saved,
            context.user_id,
            "status_changed",
            {"from": current.status.value, "to": target.value},
        )
        return saved

    def archive(self, context: UserContext, project_id: str) -> Project:
        require_permission(context, Permission.PROJECTS_WRITE)
        current = self.get(context, project_id)
        if current.status == ProjectStatus.ARCHIVED:
            return current
        now = datetime.utcnow()
        archived = replace(
            current,
            status=ProjectStatus.ARCHIVED,
            archived_at=now,
            updated_by_user_id=context.user_id,
            updated_at=now,
        )
        saved = self._repository.update(archived)
        self._append_history(
            saved,
            context.user_id,
            "archived",
            {"from": current.status.value, "to": ProjectStatus.ARCHIVED.value},
        )
        return saved
