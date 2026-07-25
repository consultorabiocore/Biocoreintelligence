from datetime import datetime

import pytest

from biocore.config.ecological_diagnostic import BRIEF_QUESTIONS
from biocore.domain.ecological_diagnostics import QuestionKind
from biocore.services.ecological_diagnostics import EcologicalDiagnosticService
from biocore.services.public_diagnostic_leads import (
    PublicLeadValidationError,
    build_public_lead_payload,
)


def complete_public_responses() -> dict[str, object]:
    responses: dict[str, object] = {}
    for question in BRIEF_QUESTIONS:
        if question.kind == QuestionKind.BOOLEAN:
            responses[question.key] = True
        else:
            responses[question.key] = [value for value, _ in question.options]
    return responses


def test_public_lead_is_independent_from_subscription_identity() -> None:
    responses = complete_public_responses()
    assessment = EcologicalDiagnosticService(None).assess(  # type: ignore[arg-type]
        "lead-1",
        "public-prospect",
        responses,
        assessment_version=1,
    )
    payload = build_public_lead_payload(
        lead_id="lead-1",
        contact_name="Loreto Campos",
        contact_email="LORETO@example.com",
        contact_phone="+56 9 1234 5678",
        organization_name="BioCore Prospecto",
        project_name="Predio piloto",
        metadata={"region": "Biobío", "client_needs": ["Planificar campaña"]},
        responses=responses,
        assessment=assessment,
        contact_consent=True,
        consented_at=datetime(2026, 7, 24, 12, 0, 0),
    )

    assert "organization_id" not in payload
    assert "user_id" not in payload
    assert payload["contact_email"] == "loreto@example.com"
    assert payload["status"] == "new"
    assert payload["contact_consent"] is True
    assert payload["questionnaire_version"] == assessment.questionnaire_version
    assert payload["result"]["scores"]


def test_public_lead_requires_valid_email_and_contact_consent() -> None:
    responses = complete_public_responses()
    assessment = EcologicalDiagnosticService(None).assess(  # type: ignore[arg-type]
        "lead-2",
        "public-prospect",
        responses,
        assessment_version=1,
    )
    common = {
        "lead_id": "lead-2",
        "contact_name": "Persona interesada",
        "contact_phone": "",
        "organization_name": "",
        "project_name": "Proyecto",
        "metadata": {},
        "responses": responses,
        "assessment": assessment,
    }

    with pytest.raises(PublicLeadValidationError):
        build_public_lead_payload(
            **common,
            contact_email="correo-invalido",
            contact_consent=True,
        )
    with pytest.raises(PublicLeadValidationError):
        build_public_lead_payload(
            **common,
            contact_email="persona@example.com",
            contact_consent=False,
        )
