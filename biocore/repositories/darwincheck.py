"""Organization-scoped persistence for native DarwinCheck runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from biocore.modules.darwincheck.domain import DarwinCheckRun


class DarwinCheckRunRepository(Protocol):
    def create(self, run: DarwinCheckRun) -> DarwinCheckRun:
        """Persist one immutable completed run."""

    def list_for_project(
        self, organization_id: str, project_id: str, *, limit: int = 20
    ) -> tuple[DarwinCheckRun, ...]:
        """List runs only inside the trusted organization and project."""


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def run_from_row(row: dict[str, Any]) -> DarwinCheckRun:
    return DarwinCheckRun(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        created_by_user_id=str(row["created_by_user_id"]),
        source_filename=str(row["source_filename"]),
        source_sha256=str(row["source_sha256"]),
        reference_name=str(row["reference_name"]),
        reference_version=str(row["reference_version"]),
        summary=dict(row.get("summary") or {}),
        findings=tuple(dict(item) for item in (row.get("findings") or [])),
        created_at=_parse_datetime(row["created_at"]),
    )


def run_payload(run: DarwinCheckRun) -> dict[str, object]:
    return {
        "id": run.id,
        "organization_id": run.organization_id,
        "project_id": run.project_id,
        "created_by_user_id": run.created_by_user_id,
        "source_filename": run.source_filename,
        "source_sha256": run.source_sha256,
        "reference_name": run.reference_name,
        "reference_version": run.reference_version,
        "summary": run.summary,
        "findings": list(run.findings),
        "created_at": run.created_at.isoformat(),
    }


class SupabaseDarwinCheckRunRepository:
    """Trusted-server repository with defense-in-depth tenant filters."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, run: DarwinCheckRun) -> DarwinCheckRun:
        response = (
            self._client.table("darwincheck_runs")
            .insert(run_payload(run))
            .execute()
        )
        rows = response.data or []
        return run_from_row(rows[0]) if rows else run

    def list_for_project(
        self, organization_id: str, project_id: str, *, limit: int = 20
    ) -> tuple[DarwinCheckRun, ...]:
        response = (
            self._client.table("darwincheck_runs")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 100)))
            .execute()
        )
        return tuple(run_from_row(row) for row in (response.data or []))
