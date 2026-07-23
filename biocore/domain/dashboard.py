from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActivityItem:
    title: str
    detail: str
    occurred_at: datetime
    kind: str


@dataclass(frozen=True)
class DashboardSnapshot:
    active_projects: int | None = None
    completed_campaigns: int | None = None
    upcoming_campaigns: int | None = None
    new_reports: int | None = None
    alerts: int | None = None
    pending_reviews: int | None = None
    last_processing_at: datetime | None = None
    activities: tuple[ActivityItem, ...] = ()
