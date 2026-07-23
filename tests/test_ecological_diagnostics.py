from dataclasses import replace
from datetime import datetime

import pytest

from biocore.config.ecological_diagnostic import (
    DIAGNOSTIC_DISCLAIMER,
    PRELIMINARY_REPORT_LABEL,
    QUESTIONNAIRE_VERSION,
    RULES_VERSION,
)
from biocore.domain.ecological_diagnostics import (
    AttachmentPolicy,
    DiagnosticAssessment,
    DiagnosticBundle,
    DiagnosticStatus,
    EcologicalDiagnostic,
    ProfessionalReviewRequest,
)
from biocore.domain.subscriptions import ModuleCode
from biocore.security.authorization import AuthorizationError, UserContext
from biocore.security.roles import Role
from biocore.services.ecological_diagnostics import (
    DiagnosticValidationError,
    EcologicalDiagnosticService,
)


class InMemoryDiagnosticRepository:
    def __init__(self) -> None:
        self.bundles: dict[str, DiagnosticBundle] = {}
        self.review_requests: list[ProfessionalReviewRequest] = []

    def create(self, diagnostic: EcologicalDiagnostic) -> EcologicalDiagnostic:
        self.bundles[diagnostic.id] = DiagnosticBundle(diagnostic)
        return diagnostic

    def update(self, diagnostic: EcologicalDiagnostic) -> EcologicalDiagnostic:
        bundle = self.bundles[diagnostic.id]
        self.bundles[diagnostic.id] = replace(bundle, diagnostic=diagnostic)
        return diagnostic

    def save_responses(
        self,
        organization_id: str,
        diagnostic_id: str,
        questionnaire_version: str,
        responses: dict[str, object],
    ) -> None:
        bundle = self.get_bundle(organization_id, diagnostic_id)
        if bundle is None:
            raise LookupError
        self.bundles[diagnostic_id] = replace(
            bundle,
            responses=dict(responses),
        )

    def get_bundle(
        self, organization_id: str, diagnostic_id: str
    ) -> DiagnosticBundle | None:
        bundle = self.bundles.get(diagnostic_id)
        if bundle is None:
            return None
        if bundle.diagnostic.organization_id != organization_id:
            return None
        return bundle

    def list_for_organization(
        self, organization_id: str
    ) -> tuple[EcologicalDiagnostic, ...]:
        return tuple(
            bundle.diagnostic
            for bundle in self.bundles.values()
            if bundle.diagnostic.organization_id == organization_id
        )

    def save_assessment(
        self, assessment: DiagnosticAssessment
    ) -> DiagnosticAssessment:
        bundle = self.get_bundle(
            assessment.organization_id, assessment.diagnostic_id
        )
        if bundle is None:
            raise LookupError
        self.bundles[assessment.diagnostic_id] = replace(
            bundle,
            assessments=bundle.assessments + (assessment,),
        )
        return assessment

    def save_review_request(
        self, request: ProfessionalReviewRequest
    ) -> ProfessionalReviewRequest:
        bundle = self.get_bundle(
            request.organization_id, request.diagnostic_id
        )
        if bundle is None:
            raise LookupError
        self.review_requests.append(request)
        self.bundles[request.diagnostic_id] = replace(
            bundle,
            review_requests=bundle.review_requests + (request,),
        )
        return request

    def list_review_requests(
        self, organization_id: str | None = None
    ) -> tuple[ProfessionalReviewRequest, ...]:
        return tuple(
            request
            for request in self.review_requests
            if organization_id is None
            or request.organization_id == organization_id
        )


def complete_responses() -> dict[str, object]:
    return {
        "has_area_polygon": True,
        "has_coordinates": True,
        "has_cartography": True,
        "components_of_interest": [
            "flora_vascular",
            "vegetation",
            "fungi",
            "lichens",
        ],
        "components_with_records": [
            "flora_vascular",
            "vegetation",
            "fungi",
            "lichens",
        ],
        "campaign_seasons": ["autumn", "spring", "summer"],
        "has_multiple_years": True,
        "has_comparable_methods": True,
        "has_species_lists": True,
        "has_photographs": True,
        "has_georeferenced_records": True,
        "has_documented_methodology": True,
        "available_record_fields": [
            "unique_id",
            "date",
            "coordinates",
            "precision",
            "observer",
            "methodology",
            "taxon",
            "photograph",
            "sample",
            "habitat",
            "substrate",
            "campaign",
            "validator",
            "file_version",
            "backup",
        ],
        "identifications_reviewed": True,
        "has_prior_report": True,
    }


def sparse_responses() -> dict[str, object]:
    responses = complete_responses()
    return {
        key: (
            ["flora_vascular"]
            if key == "components_of_interest"
            else []
            if isinstance(value, list)
            else False
        )
        for key, value in responses.items()
    }


def client_admin(
    user_id: str = "user-1", organization_id: str = "org-a"
) -> UserContext:
    return UserContext(
        user_id,
        organization_id,
        frozenset({Role.CLIENT_ADMIN}),
    )


def test_scoring_is_deterministic_versioned_and_has_eight_dimensions() -> None:
    service = EcologicalDiagnosticService(InMemoryDiagnosticRepository())
    first = service.assess(
        "diagnostic-1", "org-a", complete_responses(), assessment_version=1
    )
    second = service.assess(
        "diagnostic-1", "org-a", complete_responses(), assessment_version=1
    )
    assert len(first.scores) == 8
    assert [(item.dimension, item.score) for item in first.scores] == [
        (item.dimension, item.score) for item in second.scores
    ]
    assert first.questionnaire_version == QUESTIONNAIRE_VERSION
    assert first.rules_version == RULES_VERSION
    assert all(item.score >= 95 for item in first.scores)


def test_sparse_answers_generate_explainable_current_service_recommendations() -> None:
    service = EcologicalDiagnosticService(InMemoryDiagnosticRepository())
    result = service.assess(
        "diagnostic-1", "org-a", sparse_responses(), assessment_version=1
    )
    allowed = {
        ModuleCode.FIELD,
        ModuleCode.DARWINCHECK,
        ModuleCode.INTELLIGENCE,
        ModuleCode.REPORTS,
        ModuleCode.ACADEMY,
    }
    assert result.findings
    assert result.recommendations
    assert all(item.module_code in allowed for item in result.recommendations)
    assert all(item.explanation for item in result.findings)


def test_save_recover_and_organization_isolation() -> None:
    repository = InMemoryDiagnosticRepository()
    service = EcologicalDiagnosticService(repository)
    context = client_admin()
    diagnostic = service.create_diagnostic(
        context,
        title="Predio de prueba",
        metadata={"region": "Los Lagos"},
    )
    service.save_progress(context, diagnostic.id, sparse_responses())
    own_bundle = service.get_bundle(context, diagnostic.id)
    assert own_bundle is not None
    assert own_bundle.responses["has_area_polygon"] is False

    other_context = client_admin("user-2", "org-b")
    assert service.get_bundle(other_context, diagnostic.id) is None


def test_disclaimer_is_required_and_submission_creates_new_version() -> None:
    repository = InMemoryDiagnosticRepository()
    service = EcologicalDiagnosticService(repository)
    context = client_admin()
    diagnostic = service.create_diagnostic(
        context,
        title="Proyecto ecológico",
        metadata={},
    )
    with pytest.raises(DiagnosticValidationError):
        service.submit(
            context,
            diagnostic.id,
            complete_responses(),
            disclaimer_accepted=False,
        )

    updated, first = service.submit(
        context,
        diagnostic.id,
        complete_responses(),
        disclaimer_accepted=True,
    )
    _, second = service.submit(
        context,
        diagnostic.id,
        sparse_responses(),
        disclaimer_accepted=True,
    )
    assert updated.disclaimer_accepted_at is not None
    assert updated.status == DiagnosticStatus.AUTOMATICALLY_ASSESSED
    assert first.assessment_version == 1
    assert second.assessment_version == 2


def test_preliminary_report_contains_scope_and_version_label() -> None:
    repository = InMemoryDiagnosticRepository()
    service = EcologicalDiagnosticService(repository)
    context = client_admin()
    diagnostic = service.create_diagnostic(
        context,
        title="Predio El Bosque",
        metadata={},
    )
    diagnostic, assessment = service.submit(
        context,
        diagnostic.id,
        complete_responses(),
        disclaimer_accepted=True,
    )
    report = service.render_preliminary_report(
        diagnostic,
        assessment,
        organization_name="Organización A",
    ).decode("utf-8")
    assert PRELIMINARY_REPORT_LABEL in report
    assert DIAGNOSTIC_DISCLAIMER in report
    assert RULES_VERSION in report


def test_review_request_enters_admin_queue() -> None:
    repository = InMemoryDiagnosticRepository()
    service = EcologicalDiagnosticService(repository)
    context = client_admin()
    diagnostic = service.create_diagnostic(
        context,
        title="Predio con revisión",
        metadata={},
    )
    service.submit(
        context,
        diagnostic.id,
        complete_responses(),
        disclaimer_accepted=True,
    )
    request = service.request_professional_review(
        context,
        diagnostic.id,
        "Necesitamos revisar cobertura temporal.",
    )
    admin = UserContext(
        "admin-1",
        "org-a",
        frozenset({Role.BIOCORE_ADMIN}),
    )
    queue = service.list_review_queue(admin)
    assert queue[0][0] == request
    assert queue[0][1] is not None


def test_client_reader_cannot_create_or_request_review() -> None:
    service = EcologicalDiagnosticService(InMemoryDiagnosticRepository())
    reader = UserContext(
        "reader-1",
        "org-a",
        frozenset({Role.CLIENT_READER}),
    )
    with pytest.raises(AuthorizationError):
        service.create_diagnostic(reader, title="Sin permiso", metadata={})


def test_attachment_policy_rejects_type_and_oversize() -> None:
    policy = AttachmentPolicy()
    policy.validate("area.geojson", 1024)
    with pytest.raises(ValueError):
        policy.validate("datos.exe", 1024)
    with pytest.raises(ValueError):
        policy.validate("mapa.pdf", policy.max_size_bytes + 1)


def test_status_model_supports_future_project_conversion_without_performing_it() -> None:
    assert DiagnosticStatus.CONVERTED_TO_PROJECT.value == "converted_to_project"
    assert isinstance(datetime.utcnow(), datetime)
