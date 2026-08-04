"""Domain records produced by a deterministic DarwinCheck audit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DarwinCheckFinding:
    """One explainable observation produced by an audit rule."""

    row_number: int
    category: str
    severity: str
    observed: str
    rule: str
    explanation: str
    recommendation: str

    def as_dict(self) -> dict[str, object]:
        return {
            "row_number": self.row_number,
            "category": self.category,
            "severity": self.severity,
            "observed": self.observed,
            "rule": self.rule,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class DarwinCheckSummary:
    """Small, serializable audit summary for project history."""

    input_rows: int
    analyzed_rows: int
    header_rows: int
    exact_taxonomy_matches: int
    corrected_rows: int
    manual_review_rows: int
    geographic_issue_rows: int
    completeness_percent: float
    ecological_indices: dict[str, float]
    accumulation_curve: tuple[dict[str, float], ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "input_rows": self.input_rows,
            "analyzed_rows": self.analyzed_rows,
            "header_rows": self.header_rows,
            "exact_taxonomy_matches": self.exact_taxonomy_matches,
            "corrected_rows": self.corrected_rows,
            "manual_review_rows": self.manual_review_rows,
            "geographic_issue_rows": self.geographic_issue_rows,
            "completeness_percent": self.completeness_percent,
            "ecological_indices": dict(self.ecological_indices),
            "accumulation_curve": [dict(point) for point in self.accumulation_curve],
        }


@dataclass(frozen=True)
class DarwinCheckAnalysis:
    """In-memory analysis used by the native Streamlit experience."""

    original_dataframe: Any
    audit_dataframe: Any
    summary: DarwinCheckSummary
    findings: tuple[DarwinCheckFinding, ...]
    reference_name: str
    reference_version: str


@dataclass(frozen=True)
class DarwinCheckRun:
    """Persisted, organization-scoped trace of an executed audit."""

    id: str
    organization_id: str
    project_id: str
    created_by_user_id: str
    source_filename: str
    source_sha256: str
    reference_name: str
    reference_version: str
    summary: dict[str, object]
    findings: tuple[dict[str, object], ...]
    created_at: datetime


@dataclass(frozen=True)
class DarwinCheckExecution:
    """Result returned after analysis and project trace persistence."""

    run: DarwinCheckRun
    analysis: DarwinCheckAnalysis = field(repr=False)
