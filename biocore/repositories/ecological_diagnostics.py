from datetime import datetime
from typing import Any, Protocol

from biocore.domain.ecological_diagnostics import (
    DiagnosticAssessment,
    DiagnosticBundle,
    DiagnosticDimension,
    DiagnosticFinding,
    DiagnosticRecommendation,
    DiagnosticStatus,
    DiagnosticType,
    DimensionScore,
    EcologicalDiagnostic,
    InformationLevel,
    ProfessionalReviewRequest,
    ReviewStatus,
)
from biocore.domain.subscriptions import ModuleCode


class EcologicalDiagnosticRepository(Protocol):
    def create(self, diagnostic: EcologicalDiagnostic) -> EcologicalDiagnostic:
        """Create a diagnostic inside its trusted organization."""

    def update(self, diagnostic: EcologicalDiagnostic) -> EcologicalDiagnostic:
        """Update a diagnostic using both id and organization_id."""

    def save_responses(
        self,
        organization_id: str,
        diagnostic_id: str,
        questionnaire_version: str,
        responses: dict[str, object],
    ) -> None:
        """Upsert versioned responses after verifying organization ownership."""

    def get_bundle(
        self, organization_id: str, diagnostic_id: str
    ) -> DiagnosticBundle | None:
        """Return one diagnostic scoped to exactly one organization."""

    def list_for_organization(
        self, organization_id: str
    ) -> tuple[EcologicalDiagnostic, ...]:
        """List diagnostics from one organization."""

    def save_assessment(
        self, assessment: DiagnosticAssessment
    ) -> DiagnosticAssessment:
        """Append an immutable automatic assessment version."""

    def save_review_request(
        self, request: ProfessionalReviewRequest
    ) -> ProfessionalReviewRequest:
        """Persist a professional review request."""

    def list_review_requests(
        self, organization_id: str | None = None
    ) -> tuple[ProfessionalReviewRequest, ...]:
        """List review requests, optionally scoped to one organization."""


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    normalized = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _diagnostic_from_row(row: dict[str, Any]) -> EcologicalDiagnostic:
    now = datetime.utcnow()
    return EcologicalDiagnostic(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        user_id=str(row["user_id"]),
        title=str(row["title"]),
        diagnostic_type=DiagnosticType(str(row["diagnostic_type"])),
        status=DiagnosticStatus(str(row["status"])),
        questionnaire_version=str(row["questionnaire_version"]),
        disclaimer_accepted_at=_parse_datetime(row.get("disclaimer_accepted_at")),
        project_reference=(
            str(row["project_reference"]) if row.get("project_reference") else None
        ),
        metadata=dict(row.get("metadata") or {}),
        started_at=_parse_datetime(row.get("started_at")) or now,
        submitted_at=_parse_datetime(row.get("submitted_at")),
        completed_at=_parse_datetime(row.get("completed_at")),
        created_at=_parse_datetime(row.get("created_at")) or now,
        updated_at=_parse_datetime(row.get("updated_at")) or now,
    )


def _diagnostic_payload(diagnostic: EcologicalDiagnostic) -> dict[str, object]:
    return {
        "id": diagnostic.id,
        "organization_id": diagnostic.organization_id,
        "user_id": diagnostic.user_id,
        "project_reference": diagnostic.project_reference,
        "title": diagnostic.title,
        "diagnostic_type": diagnostic.diagnostic_type.value,
        "status": diagnostic.status.value,
        "questionnaire_version": diagnostic.questionnaire_version,
        "disclaimer_accepted_at": (
            diagnostic.disclaimer_accepted_at.isoformat()
            if diagnostic.disclaimer_accepted_at
            else None
        ),
        "metadata": diagnostic.metadata,
        "started_at": diagnostic.started_at.isoformat(),
        "submitted_at": (
            diagnostic.submitted_at.isoformat()
            if diagnostic.submitted_at
            else None
        ),
        "completed_at": (
            diagnostic.completed_at.isoformat()
            if diagnostic.completed_at
            else None
        ),
        "created_at": diagnostic.created_at.isoformat(),
        "updated_at": diagnostic.updated_at.isoformat(),
    }


def _assessment_result(assessment: DiagnosticAssessment) -> dict[str, object]:
    return {
        "general_level": assessment.general_level.value,
        "scores": [
            {
                "dimension": item.dimension.value,
                "score": item.score,
                "level": item.level.value,
                "confidence": item.confidence,
                "found": list(item.found),
                "missing": list(item.missing),
                "relevance": item.relevance,
                "recommended_action": item.recommended_action,
            }
            for item in assessment.scores
        ],
        "findings": [
            {
                "dimension": item.dimension.value,
                "priority": item.priority,
                "title": item.title,
                "explanation": item.explanation,
            }
            for item in assessment.findings
        ],
        "recommendations": [
            {
                "priority": item.priority,
                "title": item.title,
                "detail": item.detail,
                "module_code": item.module_code.value,
            }
            for item in assessment.recommendations
        ],
    }


def _assessment_from_row(row: dict[str, Any]) -> DiagnosticAssessment:
    result = dict(row.get("result") or {})
    return DiagnosticAssessment(
        diagnostic_id=str(row["diagnostic_id"]),
        organization_id=str(row["organization_id"]),
        assessment_version=int(row["assessment_version"]),
        questionnaire_version=str(row["questionnaire_version"]),
        rules_version=str(row["rules_version"]),
        general_level=InformationLevel(str(result["general_level"])),
        scores=tuple(
            DimensionScore(
                dimension=DiagnosticDimension(str(item["dimension"])),
                score=int(item["score"]),
                level=InformationLevel(str(item["level"])),
                confidence=str(item["confidence"]),
                found=tuple(str(value) for value in item.get("found", [])),
                missing=tuple(str(value) for value in item.get("missing", [])),
                relevance=str(item["relevance"]),
                recommended_action=str(item["recommended_action"]),
            )
            for item in result.get("scores", [])
        ),
        findings=tuple(
            DiagnosticFinding(
                dimension=DiagnosticDimension(str(item["dimension"])),
                priority=str(item["priority"]),
                title=str(item["title"]),
                explanation=str(item["explanation"]),
            )
            for item in result.get("findings", [])
        ),
        recommendations=tuple(
            DiagnosticRecommendation(
                priority=str(item["priority"]),
                title=str(item["title"]),
                detail=str(item["detail"]),
                module_code=ModuleCode(str(item["module_code"])),
            )
            for item in result.get("recommendations", [])
        ),
        created_at=_parse_datetime(row.get("created_at")) or datetime.utcnow(),
    )


def _review_from_row(row: dict[str, Any]) -> ProfessionalReviewRequest:
    return ProfessionalReviewRequest(
        id=str(row["id"]),
        diagnostic_id=str(row["diagnostic_id"]),
        organization_id=str(row["organization_id"]),
        user_id=str(row["user_id"]),
        status=ReviewStatus(str(row["status"])),
        message=str(row.get("message") or ""),
        requested_at=_parse_datetime(row.get("requested_at")) or datetime.utcnow(),
    )


class SupabaseEcologicalDiagnosticRepository:
    """Persist diagnostic data with server credentials and explicit tenant filters."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, diagnostic: EcologicalDiagnostic) -> EcologicalDiagnostic:
        response = (
            self._client.table("ecological_diagnostics")
            .insert(_diagnostic_payload(diagnostic))
            .execute()
        )
        rows = response.data or []
        return _diagnostic_from_row(rows[0]) if rows else diagnostic

    def update(self, diagnostic: EcologicalDiagnostic) -> EcologicalDiagnostic:
        response = (
            self._client.table("ecological_diagnostics")
            .update(_diagnostic_payload(diagnostic))
            .eq("id", diagnostic.id)
            .eq("organization_id", diagnostic.organization_id)
            .execute()
        )
        rows = response.data or []
        return _diagnostic_from_row(rows[0]) if rows else diagnostic

    def save_responses(
        self,
        organization_id: str,
        diagnostic_id: str,
        questionnaire_version: str,
        responses: dict[str, object],
    ) -> None:
        diagnostic = (
            self._client.table("ecological_diagnostics")
            .select("id")
            .eq("id", diagnostic_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        if not (diagnostic.data or []):
            raise LookupError("Diagnostic not found for organization")

        rows = [
            {
                "diagnostic_id": diagnostic_id,
                "organization_id": organization_id,
                "question_key": key,
                "response_value": value,
                "questionnaire_version": questionnaire_version,
                "updated_at": datetime.utcnow().isoformat(),
            }
            for key, value in responses.items()
            if value is not None
        ]
        if rows:
            (
                self._client.table("ecological_diagnostic_responses")
                .upsert(rows, on_conflict="diagnostic_id,question_key")
                .execute()
            )

    def get_bundle(
        self, organization_id: str, diagnostic_id: str
    ) -> DiagnosticBundle | None:
        diagnostic_response = (
            self._client.table("ecological_diagnostics")
            .select("*")
            .eq("id", diagnostic_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        diagnostic_rows = diagnostic_response.data or []
        if not diagnostic_rows:
            return None

        responses_response = (
            self._client.table("ecological_diagnostic_responses")
            .select("question_key,response_value")
            .eq("diagnostic_id", diagnostic_id)
            .eq("organization_id", organization_id)
            .execute()
        )
        assessments_response = (
            self._client.table("ecological_diagnostic_assessments")
            .select("*")
            .eq("diagnostic_id", diagnostic_id)
            .eq("organization_id", organization_id)
            .order("assessment_version")
            .execute()
        )
        reviews_response = (
            self._client.table("ecological_diagnostic_review_requests")
            .select("*")
            .eq("diagnostic_id", diagnostic_id)
            .eq("organization_id", organization_id)
            .order("requested_at")
            .execute()
        )
        return DiagnosticBundle(
            diagnostic=_diagnostic_from_row(diagnostic_rows[0]),
            responses={
                str(row["question_key"]): row.get("response_value")
                for row in (responses_response.data or [])
            },
            assessments=tuple(
                _assessment_from_row(row)
                for row in (assessments_response.data or [])
            ),
            review_requests=tuple(
                _review_from_row(row) for row in (reviews_response.data or [])
            ),
        )

    def list_for_organization(
        self, organization_id: str
    ) -> tuple[EcologicalDiagnostic, ...]:
        response = (
            self._client.table("ecological_diagnostics")
            .select("*")
            .eq("organization_id", organization_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return tuple(_diagnostic_from_row(row) for row in (response.data or []))

    def save_assessment(
        self, assessment: DiagnosticAssessment
    ) -> DiagnosticAssessment:
        payload = {
            "diagnostic_id": assessment.diagnostic_id,
            "organization_id": assessment.organization_id,
            "assessment_version": assessment.assessment_version,
            "questionnaire_version": assessment.questionnaire_version,
            "rules_version": assessment.rules_version,
            "result": _assessment_result(assessment),
            "report_label": "Resultado preliminar no revisado profesionalmente",
            "created_at": assessment.created_at.isoformat(),
        }
        response = (
            self._client.table("ecological_diagnostic_assessments")
            .insert(payload)
            .execute()
        )
        rows = response.data or []
        return _assessment_from_row(rows[0]) if rows else assessment

    def save_review_request(
        self, request: ProfessionalReviewRequest
    ) -> ProfessionalReviewRequest:
        payload = {
            "id": request.id,
            "diagnostic_id": request.diagnostic_id,
            "organization_id": request.organization_id,
            "user_id": request.user_id,
            "status": request.status.value,
            "message": request.message,
            "requested_at": request.requested_at.isoformat(),
        }
        response = (
            self._client.table("ecological_diagnostic_review_requests")
            .insert(payload)
            .execute()
        )
        rows = response.data or []
        return _review_from_row(rows[0]) if rows else request

    def list_review_requests(
        self, organization_id: str | None = None
    ) -> tuple[ProfessionalReviewRequest, ...]:
        query = (
            self._client.table("ecological_diagnostic_review_requests")
            .select("*")
            .order("requested_at", desc=True)
        )
        if organization_id is not None:
            query = query.eq("organization_id", organization_id)
        response = query.execute()
        return tuple(_review_from_row(row) for row in (response.data or []))
