"""Project management domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectModality(StrEnum):
    ONLINE = "online"
    FIELD = "field"
    MIXED = "mixed"


PROJECT_STATUS_LABELS: dict[ProjectStatus, str] = {
    ProjectStatus.PLANNING: "Planificación",
    ProjectStatus.ACTIVE: "Activo",
    ProjectStatus.PAUSED: "Pausado",
    ProjectStatus.COMPLETED: "Completado",
    ProjectStatus.ARCHIVED: "Archivado",
}


PROJECT_MODALITY_LABELS: dict[ProjectModality, str] = {
    ProjectModality.ONLINE: "Online",
    ProjectModality.FIELD: "Terreno",
    ProjectModality.MIXED: "Mixta",
}


@dataclass(frozen=True)
class Project:
    id: str
    organization_id: str
    name: str
    code: str
    client_name: str
    project_type: str
    region: str
    commune: str
    modality: ProjectModality
    description: str
    objective: str
    status: ProjectStatus
    start_date: date | None
    created_by_user_id: str
    updated_by_user_id: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectHistoryEntry:
    id: str
    project_id: str
    organization_id: str
    actor_user_id: str
    event_type: str
    changes: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class ProjectFilters:
    search: str = ""
    statuses: frozenset[ProjectStatus] = frozenset()
    modalities: frozenset[ProjectModality] = frozenset()
    include_archived: bool = False
