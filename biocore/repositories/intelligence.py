"""Organization-scoped persistence for BioCore Intelligence runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from biocore.domain.intelligence import IntelligenceRun


class IntelligenceRunRepository(Protocol):
    def create(self, run: IntelligenceRun) -> IntelligenceRun:
        """Persist an immutable monitoring run."""

    def list_for_project(
        self, organization_id: str, project_id: str, *, limit: int = 50
    ) -> tuple[IntelligenceRun, ...]:
        """List monitoring runs within one project and organization."""


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def run_from_row(row: dict[str, Any]) -> IntelligenceRun:
    return IntelligenceRun(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        created_by_user_id=str(row["created_by_user_id"]),
        geometry=dict(row.get("geometry") or {}),
        baseline_year=int(row["baseline_year"]),
        current_period=str(row["current_period"]),
        baseline_period=str(row["baseline_period"]),
        metrics=tuple(dict(item) for item in (row.get("metrics") or [])),
        findings=tuple(dict(item) for item in (row.get("findings") or [])),
        provider_version=str(row["provider_version"]),
        evidence=dict(row.get("evidence") or {}),
        created_at=_parse_datetime(row["created_at"]),
    )


def run_payload(run: IntelligenceRun) -> dict[str, object]:
    return {
        "id": run.id,
        "organization_id": run.organization_id,
        "project_id": run.project_id,
        "created_by_user_id": run.created_by_user_id,
        "geometry": run.geometry,
        "baseline_year": run.baseline_year,
        "current_period": run.current_period,
        "baseline_period": run.baseline_period,
        "metrics": list(run.metrics),
        "findings": list(run.findings),
        "provider_version": run.provider_version,
        "evidence": run.evidence,
        "created_at": run.created_at.isoformat(),
    }


class SupabaseIntelligenceRunRepository:
    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, run: IntelligenceRun) -> IntelligenceRun:
        response = (
            self._client.table("intelligence_monitoring_runs")
            .insert(run_payload(run))
            .execute()
        )
        rows = response.data or []
        return run_from_row(rows[0]) if rows else run

    def list_for_project(
        self, organization_id: str, project_id: str, *, limit: int = 50
    ) -> tuple[IntelligenceRun, ...]:
        response = (
            self._client.table("intelligence_monitoring_runs")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 200)))
            .execute()
        )
        return tuple(run_from_row(row) for row in (response.data or []))
