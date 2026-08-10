"""Traceable ecological evidence owned by a BioCore organization."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import StrEnum


class TaxonomicGroup(StrEnum):
    FLORA = "flora"
    FUNGA = "funga"
    LICHENS = "lichens"
    FAUNA = "fauna"
    OTHER = "other"


class IdentificationStatus(StrEnum):
    UNIDENTIFIED = "unidentified"
    PROPOSED = "proposed"
    REVIEW_REQUIRED = "review_required"
    REVIEWED = "reviewed"
    PROFESSIONALLY_VALIDATED = "professionally_validated"
    UNCERTAIN = "uncertain"


class ProfessionalReviewStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    REQUESTED = "requested"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    CORRECTED = "corrected"
    UNCERTAIN = "uncertain"


class EvidenceType(StrEnum):
    OBSERVATION = "observation"
    PHOTOGRAPH = "photograph"
    SPECIMEN = "specimen"
    DOCUMENT = "document"
    OTHER = "other"


class EvidenceSource(StrEnum):
    BIOCORE = "biocore"
    INATURALIST = "inaturalist"
    EXTERNAL = "external"


@dataclass(frozen=True)
class EvidenceMedia:
    id: str
    organization_id: str
    evidence_id: str
    storage_path: str | None
    filename: str
    content_type: str | None
    size_bytes: int | None
    author_name: str
    license: str
    source_type: EvidenceSource
    source_url: str | None = None
    sha256: str | None = None
    is_primary: bool = False
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
    archived_at: datetime | None = None


@dataclass(frozen=True)
class EcologicalEvidence:
    id: str
    organization_id: str
    project_id: str
    study_area_id: str | None
    created_by_user_id: str
    observation_date: date
    observation_time: time | None
    latitude: float | None
    longitude: float | None
    location_accuracy_m: float | None
    taxon_proposed: str | None
    scientific_name: str | None
    common_name: str | None
    taxonomic_group: TaxonomicGroup
    identification_status: IdentificationStatus
    evidence_type: EvidenceType
    observation_method: str
    notes: str
    source_type: EvidenceSource
    source_name: str
    source_url: str | None
    external_id: str | None
    license: str
    author_name: str
    professional_review_status: ProfessionalReviewStatus
    review_notes: str = ""
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    media: tuple[EvidenceMedia, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
    archived_at: datetime | None = None

    @property
    def is_external(self) -> bool:
        return self.source_type != EvidenceSource.BIOCORE

    @property
    def display_taxon(self) -> str:
        return (
            self.scientific_name
            or self.taxon_proposed
            or self.common_name
            or "Sin identificación"
        )


@dataclass(frozen=True)
class EvidenceHistoryEntry:
    id: str
    organization_id: str
    evidence_id: str
    actor_user_id: str
    event_type: str
    changes: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class EvidenceFilters:
    taxonomic_group: TaxonomicGroup | None = None
    identification_status: IdentificationStatus | None = None
    source_type: EvidenceSource | None = None
    review_status: ProfessionalReviewStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    include_archived: bool = False


@dataclass(frozen=True)
class EvidenceSummary:
    total: int
    own_records: int
    external_records: int
    distinct_taxa: int
    validated: int
    pending_review: int
    georeferenced: int
    incomplete: int


@dataclass(frozen=True)
class EvidenceQualityFinding:
    code: str
    severity: str
    message: str
    field_name: str | None = None
    data_used: str = ""
    rule_applied: str = ""
    next_step: str = ""


@dataclass(frozen=True)
class ExternalMediaReference:
    url: str
    author_name: str
    license: str
    attribution: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ExternalObservation:
    external_id: str
    source_url: str
    observer_name: str
    observation_date: date
    observation_time: time | None
    latitude: float | None
    longitude: float | None
    location_accuracy_m: float | None
    taxon_proposed: str | None
    scientific_name: str | None
    common_name: str | None
    taxonomic_group: TaxonomicGroup
    identification_status: IdentificationStatus
    observation_license: str
    quality_grade: str | None
    media: tuple[ExternalMediaReference, ...] = ()
