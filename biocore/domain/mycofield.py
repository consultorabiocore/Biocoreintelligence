"""Domain records for native BioCore MycoField observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class ObservationPrivacy(StrEnum):
    PRIVATE = "private"
    BLURRED = "blurred"
    ORGANIZATION = "organization"


@dataclass(frozen=True)
class MycoFieldPhoto:
    storage_path: str
    filename: str
    content_type: str
    size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "storage_path": self.storage_path,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class MycoFieldObservation:
    id: str
    organization_id: str
    project_id: str
    created_by_user_id: str
    sample_code: str
    observed_on: date
    latitude: float
    longitude: float
    map_latitude: float | None
    map_longitude: float | None
    privacy: ObservationPrivacy
    tentative_name: str
    substrate: str
    habitat: str
    method: str
    effort: str
    observable_traits: tuple[str, ...]
    notes: str
    photos: tuple[MycoFieldPhoto, ...]
    created_at: datetime
    updated_at: datetime
