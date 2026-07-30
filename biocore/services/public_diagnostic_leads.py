import re
from datetime import datetime
from typing import Any

from biocore.domain.ecological_diagnostics import DiagnosticAssessment


class PublicLeadValidationError(ValueError):
    """Raised when public diagnostic contact data is incomplete or invalid."""


_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_public_lead_contact(
    *,
    contact_name: str,
    contact_email: str,
    project_name: str,
    contact_consent: bool,
) -> None:
    if not contact_name.strip():
        raise PublicLeadValidationError("Ingresa tu nombre para continuar.")
    if not project_name.strip():
        raise PublicLeadValidationError(
            "Ingresa el nombre del proyecto, predio o iniciativa."
        )
    if not _EMAIL_PATTERN.match(contact_email.strip()):
        raise PublicLeadValidationError("Ingresa un correo electrónico válido.")
    if not contact_consent:
        raise PublicLeadValidationError(
            "Debes autorizar el contacto de BioCore para enviar tu diagnóstico."
        )


def serialize_assessment(assessment: DiagnosticAssessment) -> dict[str, object]:
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


def build_public_lead_payload(
    *,
    lead_id: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    organization_name: str,
    project_name: str,
    metadata: dict[str, object],
    responses: dict[str, object],
    assessment: DiagnosticAssessment,
    contact_consent: bool,
    source: str = "public_ecological_diagnostic",
    consented_at: datetime | None = None,
) -> dict[str, object]:
    validate_public_lead_contact(
        contact_name=contact_name,
        contact_email=contact_email,
        project_name=project_name,
        contact_consent=contact_consent,
    )
    consent_time = consented_at or datetime.utcnow()
    return {
        "id": lead_id,
        "source": source,
        "status": "new",
        "contact_name": contact_name.strip(),
        "contact_email": contact_email.strip().lower(),
        "contact_phone": contact_phone.strip(),
        "organization_name": organization_name.strip(),
        "project_name": project_name.strip(),
        "commune": str(metadata.get("commune") or "").strip(),
        "region": str(metadata.get("region") or "").strip(),
        "activity_type": str(metadata.get("activity_type") or "").strip(),
        "surface_hectares": metadata.get("surface_hectares") or None,
        "objective": str(metadata.get("objective") or "").strip(),
        "client_needs": list(metadata.get("client_needs") or []),
        "metadata": metadata,
        "responses": responses,
        "result": serialize_assessment(assessment),
        "questionnaire_version": assessment.questionnaire_version,
        "rules_version": assessment.rules_version,
        "contact_consent": True,
        "consented_at": consent_time.isoformat(),
    }


def save_public_lead(client: Any, payload: dict[str, object]) -> str:
    response = (
        client.table("public_ecological_diagnostic_leads")
        .insert(payload)
        .execute()
    )
    rows = response.data or []
    if rows:
        return str(rows[0].get("id") or payload["id"])
    return str(payload["id"])
