"""Versioned outputs from BioCore Intelligence satellite monitoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SatelliteMetric:
    code: str
    label: str
    current: float | None
    baseline: float | None
    unit: str
    source: str
    resolution: str

    @property
    def absolute_change(self) -> float | None:
        if self.current is None or self.baseline is None:
            return None
        return self.current - self.baseline

    @property
    def relative_change_percent(self) -> float | None:
        if (
            self.current is None
            or self.baseline is None
            or abs(self.baseline) < 0.000001
        ):
            return None
        return (self.current - self.baseline) / abs(self.baseline) * 100

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "label": self.label,
            "current": self.current,
            "baseline": self.baseline,
            "unit": self.unit,
            "source": self.source,
            "resolution": self.resolution,
            "absolute_change": self.absolute_change,
            "relative_change_percent": self.relative_change_percent,
        }


@dataclass(frozen=True)
class IntelligenceFinding:
    dimension: str
    classification: str
    observed: str
    rule: str
    explanation: str
    confidence: str
    limitation: str
    recommendation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "dimension": self.dimension,
            "classification": self.classification,
            "observed": self.observed,
            "rule": self.rule,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "limitation": self.limitation,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class SatelliteSnapshot:
    metrics: tuple[SatelliteMetric, ...]
    current_period: str
    baseline_period: str
    recent_image_count: int
    baseline_image_count: int
    mean_cloud_percent: float | None
    provider_version: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class IntelligenceRun:
    id: str
    organization_id: str
    project_id: str
    created_by_user_id: str
    geometry: dict[str, object]
    baseline_year: int
    current_period: str
    baseline_period: str
    metrics: tuple[dict[str, object], ...]
    findings: tuple[dict[str, str], ...]
    provider_version: str
    evidence: dict[str, object]
    created_at: datetime
