"""Supabase project repository with explicit tenant scoping."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol

from biocore.domain.projects import (
    Project,
    ProjectHistoryEntry,
    ProjectModality,
    ProjectStatus,
)


class ProjectRepository(Protocol):
    def create(self, project: Project) -> Project:
        """Create a project in its trusted organization."""

    def update(self, project: Project) -> Project:
        """Update a project using both project and organization identifiers."""

    def get(self, organization_id: str, project_id: str) -> Project | None:
        """Return one project only when it belongs to the organization."""

    def list_for_organization(
        self, organization_id: str, *, include_archived: bool = False
    ) -> tuple[Project, ...]:
        """List projects scoped to exactly one organization."""

    def code_exists(
        self,
        organization_id: str,
        code: str,
        *,
        exclude_project_id: str | None = None,
    ) -> bool:
        """Check the organization-level code constraint."""

    def append_history(self, entry: ProjectHistoryEntry) -> None:
        """Append an immutable history event."""

    def list_history(
        self, organization_id: str, project_id: str
    ) -> tuple[ProjectHistoryEntry, ...]:
        """List the project's history within the organization."""


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value)[:10])


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def project_from_row(row: dict[str, Any]) -> Project:
    now = datetime.utcnow()
    return Project(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        name=str(row["name"]),
        code=str(row["code"]),
        client_name=str(row.get("client_name") or ""),
        project_type=str(row.get("project_type") or ""),
        region=str(row.get("region") or ""),
        commune=str(row.get("commune") or ""),
        modality=ProjectModality(str(row.get("modality") or "mixed")),
        description=str(row.get("description") or ""),
        objective=str(row.get("objective") or ""),
        status=ProjectStatus(str(row.get("status") or "active")),
        start_date=_parse_date(row.get("start_date")),
        current_stage=str(row.get("current_stage") or "Inicio"),
        progress_percent=int(row.get("progress_percent") or 0),
        responsible_name=str(row.get("responsible_name") or "Por asignar"),
        next_activity=str(row.get("next_activity") or "Por definir"),
        next_activity_date=_parse_date(row.get("next_activity_date")),
        created_by_user_id=str(row.get("created_by_user_id") or ""),
        updated_by_user_id=str(row.get("updated_by_user_id") or ""),
        created_at=_parse_datetime(row.get("created_at")) or now,
        updated_at=_parse_datetime(row.get("updated_at")) or now,
        archived_at=_parse_datetime(row.get("archived_at")),
        metadata=dict(row.get("metadata") or {}),
    )


def project_payload(project: Project) -> dict[str, object]:
    return {
        "id": project.id,
        "organization_id": project.organization_id,
        "name": project.name,
        "code": project.code,
        "client_name": project.client_name,
        "project_type": project.project_type,
        "region": project.region,
        "commune": project.commune,
        "modality": project.modality.value,
        "description": project.description,
        "objective": project.objective,
        "status": project.status.value,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "current_stage": project.current_stage,
        "progress_percent": project.progress_percent,
        "responsible_name": project.responsible_name,
        "next_activity": project.next_activity,
        "next_activity_date": (
            project.next_activity_date.isoformat()
            if project.next_activity_date
            else None
        ),
        "created_by_user_id": project.created_by_user_id or None,
        "updated_by_user_id": project.updated_by_user_id or None,
        "archived_at": (
            project.archived_at.isoformat() if project.archived_at else None
        ),
        "metadata": project.metadata,
    }


def history_from_row(row: dict[str, Any]) -> ProjectHistoryEntry:
    return ProjectHistoryEntry(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        organization_id=str(row["organization_id"]),
        actor_user_id=str(row["actor_user_id"]),
        event_type=str(row["event_type"]),
        changes=dict(row.get("changes") or {}),
        created_at=_parse_datetime(row.get("created_at")) or datetime.utcnow(),
    )


class SupabaseProjectRepository:
    """Trusted server repository; every mutable query includes organization_id."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, project: Project) -> Project:
        response = (
            self._client.table("projects")
            .insert(project_payload(project))
            .execute()
        )
        rows = response.data or []
        return project_from_row(rows[0]) if rows else project

    def update(self, project: Project) -> Project:
        response = (
            self._client.table("projects")
            .update(project_payload(project))
            .eq("id", project.id)
            .eq("organization_id", project.organization_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise LookupError("Project not found for organization")
        return project_from_row(rows[0])

    def get(self, organization_id: str, project_id: str) -> Project | None:
        response = (
            self._client.table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return project_from_row(rows[0]) if rows else None

    def list_for_organization(
        self, organization_id: str, *, include_archived: bool = False
    ) -> tuple[Project, ...]:
        query = (
            self._client.table("projects")
            .select("*")
            .eq("organization_id", organization_id)
        )
        if not include_archived:
            query = query.neq("status", ProjectStatus.ARCHIVED.value)
        response = query.order("updated_at", desc=True).execute()
        return tuple(project_from_row(row) for row in (response.data or []))

    def code_exists(
        self,
        organization_id: str,
        code: str,
        *,
        exclude_project_id: str | None = None,
    ) -> bool:
        query = (
            self._client.table("projects")
            .select("id")
            .eq("organization_id", organization_id)
            .ilike("code", code)
        )
        if exclude_project_id:
            query = query.neq("id", exclude_project_id)
        response = query.limit(1).execute()
        return bool(response.data or [])

    def append_history(self, entry: ProjectHistoryEntry) -> None:
        (
            self._client.table("project_history")
            .insert(
                {
                    "id": entry.id,
                    "project_id": entry.project_id,
                    "organization_id": entry.organization_id,
                    "actor_user_id": entry.actor_user_id,
                    "event_type": entry.event_type,
                    "changes": entry.changes,
                    "created_at": entry.created_at.isoformat(),
                }
            )
            .execute()
        )

    def list_history(
        self, organization_id: str, project_id: str
    ) -> tuple[ProjectHistoryEntry, ...]:
        response = (
            self._client.table("project_history")
            .select("*")
            .eq("project_id", project_id)
            .eq("organization_id", organization_id)
            .order("created_at", desc=True)
            .execute()
        )
        return tuple(history_from_row(row) for row in (response.data or []))
