from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Organization:
    id: str
    name: str


@dataclass(frozen=True)
class Project:
    id: str
    organization_id: str
    name: str


@dataclass(frozen=True)
class Campaign:
    id: str
    organization_id: str
    project_id: str
    area_id: str
    name: str
    start_date: date
    end_date: date | None
    campaign_type: str
    methodology: str
    status: str
