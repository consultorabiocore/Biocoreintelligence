from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActivityItem:
    title: str
    detail: str
    occurred_at: datetime
    kind: str


@dataclass(frozen=True)
class ProjectSummary:
    name: str
    client: str
    last_campaign: str
    status: str
    updated_at: datetime


@dataclass(frozen=True)
class CampaignSummary:
    station: str
    project_name: str
    scheduled_for: datetime
    responsible: str
    status: str


@dataclass(frozen=True)
class ReportSummary:
    name: str
    version: str
    published_at: datetime
    status: str


@dataclass(frozen=True)
class DashboardSnapshot:
    active_projects: int | None = None
    completed_campaigns: int | None = None
    upcoming_campaigns: int | None = None
    new_reports: int | None = None
    validated_records: int | None = None
    alerts: int | None = None
    pending_reviews: int | None = None
    last_processing_at: datetime | None = None
    activities: tuple[ActivityItem, ...] = ()
    recent_projects: tuple[ProjectSummary, ...] = ()
    upcoming_campaign_items: tuple[CampaignSummary, ...] = ()
    recent_reports: tuple[ReportSummary, ...] = ()
