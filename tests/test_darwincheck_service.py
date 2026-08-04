from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from biocore.modules.darwincheck.domain import (
    DarwinCheckAnalysis,
    DarwinCheckSummary,
)
from biocore.security.authorization import AuthorizationError, UserContext
from biocore.security.roles import Role
from biocore.services.darwincheck import (
    DarwinCheckProjectNotFound,
    DarwinCheckService,
)


class FakeRunRepository:
    def __init__(self) -> None:
        self.saved = []

    def create(self, run):
        self.saved.append(run)
        return run

    def list_for_project(self, organization_id, project_id, *, limit=20):
        return tuple(
            run
            for run in reversed(self.saved)
            if run.organization_id == organization_id and run.project_id == project_id
        )[:limit]


class FakeProjectRepository:
    def get(self, organization_id, project_id):
        if organization_id == "org-a" and project_id == "project-a":
            return SimpleNamespace(id="project-a", name="Bosque A")
        return None


class FakeAnalyzer:
    def analyze(self, dataframe):
        return DarwinCheckAnalysis(
            original_dataframe=dataframe,
            audit_dataframe=pd.DataFrame(),
            summary=DarwinCheckSummary(
                input_rows=1,
                analyzed_rows=1,
                header_rows=0,
                exact_taxonomy_matches=0,
                corrected_rows=0,
                manual_review_rows=1,
                geographic_issue_rows=0,
                completeness_percent=60.0,
                ecological_indices={},
            ),
            findings=(),
            reference_name="SIMBIO",
            reference_version="test",
        )


def _service() -> tuple[DarwinCheckService, FakeRunRepository]:
    runs = FakeRunRepository()
    return DarwinCheckService(runs, FakeProjectRepository(), FakeAnalyzer()), runs


def test_writer_run_is_persisted_with_trusted_tenant_and_hash(monkeypatch) -> None:
    monkeypatch.setattr(
        "biocore.services.darwincheck.read_occurrence_workbook",
        lambda payload: pd.DataFrame([[""] * 34]),
    )
    service, runs = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))

    execution = service.analyze_upload(
        context,
        "project-a",
        "../planilla.xlsx",
        b"safe workbook bytes",
    )

    assert execution.run.organization_id == "org-a"
    assert execution.run.project_id == "project-a"
    assert execution.run.created_by_user_id == "user-a"
    assert execution.run.source_filename == "planilla.xlsx"
    assert len(execution.run.source_sha256) == 64
    assert runs.saved == [execution.run]


def test_project_from_another_organization_is_rejected_before_persistence(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "biocore.services.darwincheck.read_occurrence_workbook",
        lambda payload: pd.DataFrame([[""] * 34]),
    )
    service, runs = _service()
    context = UserContext("user-b", "org-b", frozenset({Role.CLIENT_EDITOR}))

    with pytest.raises(DarwinCheckProjectNotFound):
        service.analyze_upload(
            context,
            "project-a",
            "planilla.xlsx",
            b"safe workbook bytes",
        )
    assert not runs.saved


def test_reader_can_view_history_but_cannot_run_audit(monkeypatch) -> None:
    monkeypatch.setattr(
        "biocore.services.darwincheck.read_occurrence_workbook",
        lambda payload: pd.DataFrame([[""] * 34]),
    )
    service, _ = _service()
    reader = UserContext("reader", "org-a", frozenset({Role.CLIENT_READER}))

    assert service.list_runs(reader, "project-a") == ()
    with pytest.raises(AuthorizationError):
        service.analyze_upload(
            reader,
            "project-a",
            "planilla.xlsx",
            b"safe workbook bytes",
        )
