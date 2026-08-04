"""Application service for native DarwinCheck analysis and traceability."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from biocore.modules.darwincheck.analyzer import DarwinCheckAnalyzer
from biocore.modules.darwincheck.domain import (
    DarwinCheckExecution,
    DarwinCheckRun,
)
from biocore.modules.darwincheck.excel import (
    export_audit_workbook,
    read_occurrence_workbook,
)
from biocore.repositories.darwincheck import DarwinCheckRunRepository
from biocore.repositories.projects import ProjectRepository
from biocore.security.authorization import UserContext, require_permission
from biocore.security.roles import Permission


MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class DarwinCheckProjectNotFound(LookupError):
    """Raised when a project does not belong to the active organization."""


class DarwinCheckUploadError(ValueError):
    """Raised for an unsafe or unsupported upload."""


class DarwinCheckService:
    """Authorize, analyze and persist a project-scoped DarwinCheck run."""

    def __init__(
        self,
        runs: DarwinCheckRunRepository,
        projects: ProjectRepository,
        analyzer: DarwinCheckAnalyzer,
    ) -> None:
        self._runs = runs
        self._projects = projects
        self._analyzer = analyzer

    def _project(self, context: UserContext, project_id: str):
        project = self._projects.get(context.organization_id, project_id)
        if project is None:
            raise DarwinCheckProjectNotFound(
                "El proyecto no está disponible en la organización activa."
            )
        return project

    def analyze_upload(
        self,
        context: UserContext,
        project_id: str,
        source_filename: str,
        payload: bytes,
    ) -> DarwinCheckExecution:
        require_permission(context, Permission.DARWINCHECK_WRITE)
        project = self._project(context, project_id)
        filename = Path(source_filename).name.strip()
        if not filename:
            raise DarwinCheckUploadError("El archivo debe tener un nombre.")
        if Path(filename).suffix.casefold() not in {".xlsx", ".xls"}:
            raise DarwinCheckUploadError(
                "DarwinCheck admite planillas Excel .xlsx o .xls."
            )
        if len(payload) > MAX_UPLOAD_BYTES:
            raise DarwinCheckUploadError(
                "El archivo supera el límite de 25 MB para esta versión."
            )
        dataframe = read_occurrence_workbook(payload)
        analysis = self._analyzer.analyze(dataframe)
        now = datetime.now(timezone.utc)
        run = DarwinCheckRun(
            id=str(uuid4()),
            organization_id=context.organization_id,
            project_id=project.id,
            created_by_user_id=context.user_id,
            source_filename=filename,
            source_sha256=hashlib.sha256(payload).hexdigest(),
            reference_name=analysis.reference_name,
            reference_version=analysis.reference_version,
            summary=analysis.summary.as_dict(),
            findings=tuple(finding.as_dict() for finding in analysis.findings),
            created_at=now,
        )
        saved = self._runs.create(run)
        return DarwinCheckExecution(run=saved, analysis=analysis)

    def list_runs(
        self,
        context: UserContext,
        project_id: str,
        *,
        limit: int = 20,
    ) -> tuple[DarwinCheckRun, ...]:
        require_permission(context, Permission.DARWINCHECK_READ)
        project = self._project(context, project_id)
        return self._runs.list_for_project(
            context.organization_id,
            project.id,
            limit=limit,
        )

    def export_workbook(
        self,
        context: UserContext,
        execution: DarwinCheckExecution,
        *,
        organization_name: str,
    ) -> bytes:
        require_permission(context, Permission.DARWINCHECK_READ)
        if execution.run.organization_id != context.organization_id:
            raise DarwinCheckProjectNotFound(
                "El resultado no pertenece a la organización activa."
            )
        project = self._project(context, execution.run.project_id)
        return export_audit_workbook(
            execution.analysis,
            organization_id=context.organization_id,
            organization_name=organization_name,
            project_id=project.id,
            project_name=project.name,
            user_id=context.user_id,
            run_id=execution.run.id,
        )
