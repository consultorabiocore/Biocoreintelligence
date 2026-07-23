import base64
from dataclasses import replace
from datetime import datetime
from html import escape
from statistics import mean
from uuid import uuid4

from biocore.config.ecological_diagnostic import (
    BRIEF_QUESTIONS,
    DIAGNOSTIC_DISCLAIMER,
    DIMENSION_CONTEXT,
    DIMENSION_LABELS,
    DIMENSION_RULES,
    PRELIMINARY_REPORT_LABEL,
    QUESTIONNAIRE_VERSION,
    RULES_VERSION,
)
from biocore.config.brand import BRAND
from biocore.domain.ecological_diagnostics import (
    DiagnosticAssessment,
    DiagnosticBundle,
    DiagnosticFinding,
    DiagnosticRecommendation,
    DiagnosticStatus,
    DiagnosticType,
    DimensionScore,
    EcologicalDiagnostic,
    InformationLevel,
    ProfessionalReviewRequest,
    ReviewStatus,
    ScoringRule,
    QuestionKind,
)
from biocore.repositories.ecological_diagnostics import (
    EcologicalDiagnosticRepository,
)
from biocore.domain.subscriptions import ModuleCode
from biocore.security.authorization import UserContext, require_permission
from biocore.security.roles import Permission


class DiagnosticValidationError(ValueError):
    """Raised when required diagnostic input is incomplete or inconsistent."""


LEVEL_LABELS = {
    InformationLevel.REQUIRES_ADDITIONAL_WORK: "Requiere trabajo adicional",
    InformationLevel.INITIAL: "Información inicial",
    InformationLevel.PARTIAL: "Información parcial",
    InformationLevel.SUFFICIENT_FOR_REVIEW: "Información suficiente para revisión",
}

MODULE_RECOMMENDATION_TITLES = {
    "field": "Planificar una revisión o campaña con BioCore Field",
    "darwincheck": "Organizar y validar registros con DarwinCheck",
    "intelligence": "Preparar análisis geoespacial con BioCore Intelligence",
    "reports": "Ordenar productos y versiones con BioCore Reports",
    "academy": "Fortalecer capacidades con BioCore Academy",
}


def _level_for(score: int) -> InformationLevel:
    if score < 25:
        return InformationLevel.REQUIRES_ADDITIONAL_WORK
    if score < 50:
        return InformationLevel.INITIAL
    if score < 75:
        return InformationLevel.PARTIAL
    return InformationLevel.SUFFICIENT_FOR_REVIEW


def _as_selection(value: object) -> frozenset[str]:
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(str(item) for item in value)
    return frozenset()


def _earned_fraction(rule: ScoringRule, responses: dict[str, object]) -> float:
    value = responses.get(rule.question_key)
    if rule.mode == "boolean":
        return 1.0 if value is True else 0.0
    if rule.mode == "count":
        selected = _as_selection(value)
        return min(len(selected) / max(rule.target_count, 1), 1.0)
    if rule.mode == "selection_coverage":
        selected = _as_selection(value)
        if not rule.expected_values:
            return 0.0
        return len(selected & rule.expected_values) / len(rule.expected_values)
    if rule.mode == "component_coverage":
        selected = _as_selection(value)
        components_of_interest = _as_selection(
            responses.get("components_of_interest")
        )
        if not components_of_interest:
            return 0.0
        return len(selected & components_of_interest) / len(components_of_interest)
    raise DiagnosticValidationError(f"Regla de puntuación desconocida: {rule.mode}")


def _confidence_for(
    rules: tuple[ScoringRule, ...],
    responses: dict[str, object],
) -> str:
    keys = {rule.question_key for rule in rules}
    answered = sum(key in responses for key in keys)
    ratio = answered / len(keys) if keys else 0
    if ratio >= 0.8:
        return "alta"
    if ratio >= 0.5:
        return "media"
    return "baja"


def _priority_for(score: int) -> str:
    if score < 40:
        return "alta"
    if score < 65:
        return "media"
    return "baja"


class EcologicalDiagnosticService:
    """Versioned, deterministic and auditable ecological diagnostic rules."""

    def __init__(self, repository: EcologicalDiagnosticRepository) -> None:
        self._repository = repository

    def validate_responses(self, responses: dict[str, object]) -> None:
        missing = [
            question.key
            for question in BRIEF_QUESTIONS
            if question.required and question.key not in responses
        ]
        if missing:
            raise DiagnosticValidationError(
                "Faltan respuestas requeridas: " + ", ".join(missing)
            )
        questions_by_key = {question.key: question for question in BRIEF_QUESTIONS}
        invalid = []
        for key, question in questions_by_key.items():
            value = responses.get(key)
            if question.kind == QuestionKind.BOOLEAN and not isinstance(value, bool):
                invalid.append(key)
            if (
                question.kind == QuestionKind.MULTIPLE
                and not isinstance(value, (list, tuple, set, frozenset))
            ):
                invalid.append(key)
        if invalid:
            raise DiagnosticValidationError(
                "Respuestas con formato inválido: " + ", ".join(invalid)
            )
        if not _as_selection(responses.get("components_of_interest")):
            raise DiagnosticValidationError(
                "Selecciona al menos un componente ecológico de interés"
            )

    def assess(
        self,
        diagnostic_id: str,
        organization_id: str,
        responses: dict[str, object],
        *,
        assessment_version: int,
    ) -> DiagnosticAssessment:
        self.validate_responses(responses)
        scores: list[DimensionScore] = []
        findings: list[DiagnosticFinding] = []
        recommendations_by_module: dict[str, DiagnosticRecommendation] = {}

        for dimension, rules in DIMENSION_RULES.items():
            fractions = [(rule, _earned_fraction(rule, responses)) for rule in rules]
            score = min(
                100,
                round(sum(rule.weight * fraction for rule, fraction in fractions)),
            )
            found = tuple(
                rule.found_text for rule, fraction in fractions if fraction >= 0.99
            )
            missing = tuple(
                rule.missing_text for rule, fraction in fractions if fraction < 0.99
            )
            relevance, action, module_code = DIMENSION_CONTEXT[dimension]
            dimension_score = DimensionScore(
                dimension=dimension,
                score=score,
                level=_level_for(score),
                confidence=_confidence_for(rules, responses),
                found=found,
                missing=missing,
                relevance=relevance,
                recommended_action=action,
            )
            scores.append(dimension_score)

            if missing:
                findings.append(
                    DiagnosticFinding(
                        dimension=dimension,
                        priority=_priority_for(score),
                        title=f"Brecha en {DIMENSION_LABELS[dimension].lower()}",
                        explanation=" ".join(missing),
                    )
                )

            if score < 75:
                priority = _priority_for(score)
                candidate = DiagnosticRecommendation(
                    priority=priority,
                    title=MODULE_RECOMMENDATION_TITLES[module_code.value],
                    detail=action,
                    module_code=module_code,
                )
                existing = recommendations_by_module.get(module_code.value)
                priority_order = {"alta": 0, "media": 1, "baja": 2}
                if (
                    existing is None
                    or priority_order[candidate.priority]
                    < priority_order[existing.priority]
                ):
                    recommendations_by_module[module_code.value] = candidate

        general_score = round(mean(item.score for item in scores))
        record_quality = next(
            item
            for item in scores
            if item.dimension.value == "record_quality"
        )
        if record_quality.score < 50:
            recommendations_by_module[ModuleCode.ACADEMY.value] = (
                DiagnosticRecommendation(
                    priority="media",
                    title=MODULE_RECOMMENDATION_TITLES[ModuleCode.ACADEMY.value],
                    detail=(
                        "Capacitar al equipo en registro ecológico, evidencia "
                        "fotográfica y gestión de datos geoespaciales."
                    ),
                    module_code=ModuleCode.ACADEMY,
                )
            )
        recommendations = tuple(
            sorted(
                recommendations_by_module.values(),
                key=lambda item: {"alta": 0, "media": 1, "baja": 2}[item.priority],
            )
        )
        return DiagnosticAssessment(
            diagnostic_id=diagnostic_id,
            organization_id=organization_id,
            assessment_version=assessment_version,
            questionnaire_version=QUESTIONNAIRE_VERSION,
            rules_version=RULES_VERSION,
            general_level=_level_for(general_score),
            scores=tuple(scores),
            findings=tuple(findings),
            recommendations=recommendations,
        )

    def create_diagnostic(
        self,
        context: UserContext,
        *,
        title: str,
        metadata: dict[str, object],
        project_reference: str | None = None,
    ) -> EcologicalDiagnostic:
        require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_WRITE)
        normalized_title = title.strip()
        if not normalized_title:
            raise DiagnosticValidationError(
                "El diagnóstico necesita un nombre de proyecto o predio"
            )
        now = datetime.utcnow()
        diagnostic = EcologicalDiagnostic(
            id=str(uuid4()),
            organization_id=context.organization_id,
            user_id=context.user_id,
            title=normalized_title,
            diagnostic_type=DiagnosticType.BRIEF,
            status=DiagnosticStatus.DRAFT,
            questionnaire_version=QUESTIONNAIRE_VERSION,
            disclaimer_accepted_at=None,
            project_reference=project_reference,
            metadata=metadata,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        return self._repository.create(diagnostic)

    def save_progress(
        self,
        context: UserContext,
        diagnostic_id: str,
        responses: dict[str, object],
        *,
        metadata: dict[str, object] | None = None,
    ) -> EcologicalDiagnostic:
        require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_WRITE)
        bundle = self._repository.get_bundle(
            context.organization_id, diagnostic_id
        )
        if bundle is None:
            raise LookupError("Diagnóstico no encontrado en esta organización")
        if bundle.diagnostic.status == DiagnosticStatus.ARCHIVED:
            raise DiagnosticValidationError(
                "Un diagnóstico archivado no puede modificarse"
            )
        self._repository.save_responses(
            context.organization_id,
            diagnostic_id,
            QUESTIONNAIRE_VERSION,
            responses,
        )
        updated = replace(
            bundle.diagnostic,
            status=DiagnosticStatus.IN_PROGRESS,
            metadata=metadata or bundle.diagnostic.metadata,
            updated_at=datetime.utcnow(),
        )
        return self._repository.update(updated)

    def submit(
        self,
        context: UserContext,
        diagnostic_id: str,
        responses: dict[str, object],
        *,
        disclaimer_accepted: bool,
        metadata: dict[str, object] | None = None,
    ) -> tuple[EcologicalDiagnostic, DiagnosticAssessment]:
        require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_WRITE)
        if not disclaimer_accepted:
            raise DiagnosticValidationError(
                "Debes aceptar el alcance preliminar antes de generar resultados"
            )
        self.validate_responses(responses)
        bundle = self._repository.get_bundle(
            context.organization_id, diagnostic_id
        )
        if bundle is None:
            raise LookupError("Diagnóstico no encontrado en esta organización")

        now = datetime.utcnow()
        self._repository.save_responses(
            context.organization_id,
            diagnostic_id,
            QUESTIONNAIRE_VERSION,
            responses,
        )
        assessment = self.assess(
            diagnostic_id,
            context.organization_id,
            responses,
            assessment_version=len(bundle.assessments) + 1,
        )
        assessment = self._repository.save_assessment(assessment)
        updated = replace(
            bundle.diagnostic,
            status=DiagnosticStatus.AUTOMATICALLY_ASSESSED,
            disclaimer_accepted_at=now,
            metadata=metadata or bundle.diagnostic.metadata,
            submitted_at=now,
            completed_at=now,
            updated_at=now,
        )
        return self._repository.update(updated), assessment

    def get_bundle(
        self, context: UserContext, diagnostic_id: str
    ) -> DiagnosticBundle | None:
        require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_READ)
        return self._repository.get_bundle(
            context.organization_id, diagnostic_id
        )

    def list_for_context(
        self, context: UserContext
    ) -> tuple[EcologicalDiagnostic, ...]:
        require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_READ)
        return self._repository.list_for_organization(context.organization_id)

    def request_professional_review(
        self,
        context: UserContext,
        diagnostic_id: str,
        message: str = "",
    ) -> ProfessionalReviewRequest:
        require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_WRITE)
        bundle = self._repository.get_bundle(
            context.organization_id, diagnostic_id
        )
        if bundle is None:
            raise LookupError("Diagnóstico no encontrado en esta organización")
        if not bundle.assessments:
            raise DiagnosticValidationError(
                "Genera el resultado preliminar antes de solicitar una revisión"
            )
        request = ProfessionalReviewRequest(
            id=str(uuid4()),
            diagnostic_id=diagnostic_id,
            organization_id=context.organization_id,
            user_id=context.user_id,
            status=ReviewStatus.REQUESTED,
            message=message.strip(),
        )
        saved = self._repository.save_review_request(request)
        updated = replace(
            bundle.diagnostic,
            status=DiagnosticStatus.PROFESSIONAL_REVIEW_REQUESTED,
            updated_at=datetime.utcnow(),
        )
        self._repository.update(updated)
        return saved

    def list_review_queue(
        self, context: UserContext
    ) -> tuple[tuple[ProfessionalReviewRequest, DiagnosticBundle | None], ...]:
        require_permission(context, Permission.PLATFORM_ADMIN)
        requests = self._repository.list_review_requests()
        return tuple(
            (
                request,
                self._repository.get_bundle(
                    request.organization_id, request.diagnostic_id
                ),
            )
            for request in requests
        )

    def render_preliminary_report(
        self,
        diagnostic: EcologicalDiagnostic,
        assessment: DiagnosticAssessment,
        *,
        organization_name: str,
    ) -> bytes:
        logo_html = "<strong>BIOCORE</strong>"
        if BRAND.master_logo.is_file():
            encoded_logo = base64.b64encode(
                BRAND.master_logo.read_bytes()
            ).decode("ascii")
            logo_html = (
                '<img alt="BioCore" style="max-width:360px;max-height:120px" '
                f'src="data:image/png;base64,{encoded_logo}">'
            )
        score_rows = "".join(
            (
                "<tr>"
                f"<td>{escape(DIMENSION_LABELS[item.dimension])}</td>"
                f"<td>{item.score}/100</td>"
                f"<td>{escape(LEVEL_LABELS[item.level])}</td>"
                f"<td>{escape(item.confidence.title())}</td>"
                "</tr>"
            )
            for item in assessment.scores
        )
        finding_items = "".join(
            (
                f"<li><strong>{escape(item.title)}</strong>: "
                f"{escape(item.explanation)}</li>"
            )
            for item in assessment.findings
        )
        recommendation_items = "".join(
            (
                f"<li><strong>{escape(item.title)}</strong>: "
                f"{escape(item.detail)}</li>"
            )
            for item in assessment.recommendations
        )
        generated_on = assessment.created_at.strftime("%d/%m/%Y %H:%M")
        html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{escape(diagnostic.title)} | BioCore</title>
<style>
body{{font-family:Arial,sans-serif;color:#17362c;max-width:920px;margin:40px auto;line-height:1.55}}
h1,h2{{color:#12372a}} .notice{{border:2px solid #c99a2e;padding:16px;background:#fff8e6}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:10px;border:1px solid #d9e4dc;text-align:left}}
small{{color:#587068}}
</style>
</head>
<body>
<p>{logo_html}</p>
<h1>Diagnóstico Ecológico Digital BioCore</h1>
<p><strong>{escape(PRELIMINARY_REPORT_LABEL)}</strong></p>
<div class="notice">{escape(DIAGNOSTIC_DISCLAIMER)}</div>
<h2>Identificación</h2>
<p>
Organización: {escape(organization_name)}<br>
Proyecto o predio: {escape(diagnostic.title)}<br>
Fecha: {generated_on}<br>
Cuestionario: {escape(assessment.questionnaire_version)}<br>
Reglas: {escape(assessment.rules_version)}<br>
Versión del resultado: {assessment.assessment_version}
</p>
<h2>Resumen</h2>
<p>Nivel general: <strong>{escape(LEVEL_LABELS[assessment.general_level])}</strong>.</p>
<h2>Resultados por dimensión</h2>
<table>
<thead><tr><th>Dimensión</th><th>Puntuación</th><th>Nivel</th><th>Confianza</th></tr></thead>
<tbody>{score_rows}</tbody>
</table>
<h2>Brechas y hallazgos</h2>
<ul>{finding_items or "<li>No se generaron brechas automáticas.</li>"}</ul>
<h2>Recomendaciones preliminares</h2>
<ul>{recommendation_items or "<li>Solicitar revisión profesional.</li>"}</ul>
<h2>Próximos pasos</h2>
<p>Solicitar revisión profesional a BioCore antes de adoptar decisiones técnicas.</p>
<p><small>Este archivo conserva un resultado automático versionado y no ha sido
revisado profesionalmente.</small></p>
</body>
</html>"""
        return html.encode("utf-8")
