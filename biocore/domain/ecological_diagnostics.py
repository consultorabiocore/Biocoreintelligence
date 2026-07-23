from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from biocore.domain.subscriptions import ModuleCode


class DiagnosticType(StrEnum):
    BRIEF = "brief"
    DETAILED = "detailed"


class DiagnosticStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTOMATICALLY_ASSESSED = "automatically_assessed"
    PROFESSIONAL_REVIEW_REQUESTED = "professional_review_requested"
    UNDER_REVIEW = "under_review"
    REVIEWED = "reviewed"
    CONVERTED_TO_PROJECT = "converted_to_project"
    ARCHIVED = "archived"


class ReviewStatus(StrEnum):
    REQUESTED = "requested"
    CONTACTED = "contacted"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DiagnosticDimension(StrEnum):
    DOCUMENT_COMPLETENESS = "document_completeness"
    SPATIAL_COVERAGE = "spatial_coverage"
    TEMPORAL_COVERAGE = "temporal_coverage"
    TAXONOMIC_COVERAGE = "taxonomic_coverage"
    RECORD_QUALITY = "record_quality"
    TRACEABILITY = "traceability"
    GEOSPATIAL_READINESS = "geospatial_readiness"
    CAMPAIGN_COMPARISON_READINESS = "campaign_comparison_readiness"


class InformationLevel(StrEnum):
    REQUIRES_ADDITIONAL_WORK = "requires_additional_work"
    INITIAL = "initial_information"
    PARTIAL = "partial_information"
    SUFFICIENT_FOR_REVIEW = "sufficient_for_review"


class QuestionKind(StrEnum):
    BOOLEAN = "boolean"
    MULTIPLE = "multiple"


@dataclass(frozen=True)
class QuestionDefinition:
    key: str
    section: str
    prompt: str
    kind: QuestionKind
    required: bool = True
    options: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ScoringRule:
    question_key: str
    weight: float
    mode: str
    found_text: str
    missing_text: str
    expected_values: frozenset[str] = frozenset()
    target_count: int = 1


@dataclass(frozen=True)
class EcologicalDiagnostic:
    id: str
    organization_id: str
    user_id: str
    title: str
    diagnostic_type: DiagnosticType
    status: DiagnosticStatus
    questionnaire_version: str
    disclaimer_accepted_at: datetime | None
    project_reference: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class DimensionScore:
    dimension: DiagnosticDimension
    score: int
    level: InformationLevel
    confidence: str
    found: tuple[str, ...]
    missing: tuple[str, ...]
    relevance: str
    recommended_action: str


@dataclass(frozen=True)
class DiagnosticFinding:
    dimension: DiagnosticDimension
    priority: str
    title: str
    explanation: str


@dataclass(frozen=True)
class DiagnosticRecommendation:
    priority: str
    title: str
    detail: str
    module_code: ModuleCode


@dataclass(frozen=True)
class DiagnosticAssessment:
    diagnostic_id: str
    organization_id: str
    assessment_version: int
    questionnaire_version: str
    rules_version: str
    general_level: InformationLevel
    scores: tuple[DimensionScore, ...]
    findings: tuple[DiagnosticFinding, ...]
    recommendations: tuple[DiagnosticRecommendation, ...]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class ProfessionalReviewRequest:
    id: str
    diagnostic_id: str
    organization_id: str
    user_id: str
    status: ReviewStatus
    message: str
    requested_at: datetime = field(default_factory=datetime.utcnow)


@dataclass(frozen=True)
class DiagnosticBundle:
    diagnostic: EcologicalDiagnostic
    responses: dict[str, Any] = field(default_factory=dict)
    assessments: tuple[DiagnosticAssessment, ...] = ()
    review_requests: tuple[ProfessionalReviewRequest, ...] = ()


@dataclass(frozen=True)
class AttachmentPolicy:
    allowed_extensions: frozenset[str] = frozenset(
        {".kml", ".kmz", ".geojson", ".zip", ".pdf", ".png", ".jpg", ".jpeg"}
    )
    max_size_bytes: int = 15 * 1024 * 1024

    def validate(self, filename: str, size_bytes: int) -> None:
        normalized = filename.lower().strip()
        if not any(normalized.endswith(item) for item in self.allowed_extensions):
            raise ValueError("Tipo de archivo no permitido")
        if size_bytes <= 0 or size_bytes > self.max_size_bytes:
            raise ValueError("Tamaño de archivo no permitido")
