from datetime import datetime
from html import escape
from typing import Any, Callable, cast
from uuid import uuid4

import streamlit as st

from biocore.config.brand import BRAND
from biocore.config.ecological_diagnostic import (
    BRIEF_QUESTIONS,
    CLIENT_NEED_OPTIONS,
    DIAGNOSTIC_DESCRIPTION,
    DIAGNOSTIC_DISCLAIMER,
    DIAGNOSTIC_NAME,
    DIAGNOSTIC_SUBTITLE,
    DIMENSION_LABELS,
    PRELIMINARY_REPORT_LABEL,
    QUESTIONNAIRE_VERSION,
)
from biocore.domain.ecological_diagnostics import (
    DiagnosticAssessment,
    DiagnosticStatus,
    DiagnosticType,
    EcologicalDiagnostic,
    QuestionKind,
)
from biocore.repositories.ecological_diagnostics import EcologicalDiagnosticRepository
from biocore.services.ecological_diagnostics import (
    LEVEL_LABELS,
    DiagnosticValidationError,
    EcologicalDiagnosticService,
)
from biocore.services.public_diagnostic_leads import (
    PublicLeadValidationError,
    build_public_lead_payload,
)


LeadRecorder = Callable[[dict[str, object]], str]
_RESULT_KEY = "biocore_public_diagnostic_result"


def _apply_public_diagnostic_styles() -> None:
    """Keep the public form readable inside the light BioCore private shell."""
    st.markdown(
        """
        <style>
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h1,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h2,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h3,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h4,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] p,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] small,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] label,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] label p,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"],
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] {
            color: #14211b !important;
        }

        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stAlert"] *,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [role="radiogroup"] label p,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stCheckbox"] label p {
            color: #24342c !important;
        }

        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="input"] > div,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="textarea"] > div,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            border-color: #aebfb5 !important;
            color: #14211b !important;
        }

        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] input,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] textarea,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="select"] span,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="select"] div {
            color: #14211b !important;
            -webkit-text-fill-color: #14211b !important;
        }

        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] input::placeholder,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] textarea::placeholder {
            color: #6b7c73 !important;
            -webkit-text-fill-color: #6b7c73 !important;
            opacity: 1 !important;
        }

        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stForm"] {
            padding: 1.25rem;
            border: 1px solid #dbe5de;
            border-radius: 18px;
            background: #fbfdfb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _assessment_service() -> EcologicalDiagnosticService:
    # The deterministic assessment method does not access the repository. The
    # private module continues using its normal Supabase-backed repository.
    repository = cast(EcologicalDiagnosticRepository, None)
    return EcologicalDiagnosticService(repository)


def _answer_key(question_key: str) -> str:
    return f"public_ecological_{question_key}"


def _questionnaire() -> dict[str, object]:
    answers: dict[str, object] = {}
    active_section = ""
    for question in BRIEF_QUESTIONS:
        if question.section != active_section:
            active_section = question.section
            st.markdown(f"#### {escape(active_section)}")
        key = _answer_key(question.key)
        if question.kind == QuestionKind.BOOLEAN:
            answers[question.key] = st.radio(
                question.prompt,
                options=(True, False),
                format_func=lambda value: "Sí" if value else "No",
                index=None,
                horizontal=True,
                key=key,
            )
        else:
            labels = {value: label for value, label in question.options}
            answers[question.key] = st.multiselect(
                question.prompt,
                options=list(labels),
                format_func=lambda value, item_labels=labels: item_labels[value],
                key=key,
            )
    return answers


def _render_scores(assessment: DiagnosticAssessment) -> None:
    for index in range(0, len(assessment.scores), 2):
        columns = st.columns(2, gap="medium")
        for column, item in zip(columns, assessment.scores[index : index + 2]):
            with column:
                st.markdown(
                    f"""
                    <section style="border:1px solid #d9e4dc;border-radius:16px;
                    padding:16px;margin-bottom:12px;background:#ffffff;">
                        <small>{escape(LEVEL_LABELS[item.level])}</small>
                        <h3>{escape(DIMENSION_LABELS[item.dimension])}</h3>
                        <p>Confianza: <strong>{escape(item.confidence)}</strong></p>
                    </section>
                    """,
                    unsafe_allow_html=True,
                )
                st.progress(item.score / 100, text=f"{item.score} de 100")
                with st.expander("Ver explicación"):
                    st.markdown(f"**Por qué es relevante:** {item.relevance}")
                    if item.missing:
                        st.markdown("**Antecedentes faltantes o parciales**")
                        for text in item.missing:
                            st.markdown(f"- {text}")
                    st.markdown(f"**Acción sugerida:** {item.recommended_action}")


def _temporary_diagnostic(
    lead_id: str,
    project_name: str,
    metadata: dict[str, object],
) -> EcologicalDiagnostic:
    now = datetime.utcnow()
    return EcologicalDiagnostic(
        id=lead_id,
        organization_id="public-prospect",
        user_id="public-prospect",
        title=project_name,
        diagnostic_type=DiagnosticType.BRIEF,
        status=DiagnosticStatus.AUTOMATICALLY_ASSESSED,
        questionnaire_version=QUESTIONNAIRE_VERSION,
        disclaimer_accepted_at=now,
        metadata=metadata,
        started_at=now,
        submitted_at=now,
        completed_at=now,
        created_at=now,
        updated_at=now,
    )


def _render_result(result: dict[str, Any]) -> None:
    assessment = cast(DiagnosticAssessment, result["assessment"])
    project_name = str(result["project_name"])
    organization_name = str(result.get("organization_name") or "Prospecto BioCore")
    report = cast(bytes, result["report"])
    saved = bool(result.get("saved"))

    st.divider()
    st.success("Tu resultado preliminar está listo.")
    if saved:
        st.caption(
            "BioCore recibió tus antecedentes y podrá contactarte usando los datos autorizados."
        )
    else:
        st.warning(
            "El resultado se generó, pero el registro comercial no pudo guardarse. "
            "Puedes descargarlo y contactar directamente a BioCore."
        )
    st.warning(DIAGNOSTIC_DISCLAIMER, icon="⚠️")
    st.caption(PRELIMINARY_REPORT_LABEL)
    st.metric(
        "Nivel general de información disponible",
        LEVEL_LABELS[assessment.general_level],
    )
    _render_scores(assessment)

    st.markdown("### Brechas principales")
    for finding in assessment.findings[:6]:
        st.markdown(
            f"**Prioridad {finding.priority} · {finding.title}**  \n"
            f"{finding.explanation}"
        )
    if not assessment.findings:
        st.info("No se generaron brechas automáticas con las respuestas entregadas.")

    st.markdown("### Recomendaciones BioCore")
    for recommendation in assessment.recommendations:
        st.markdown(
            f"**{recommendation.title}**  \n{recommendation.detail}"
        )

    st.download_button(
        "Descargar informe preliminar",
        data=report,
        file_name=f"diagnostico-ecologico-{project_name.strip().lower().replace(' ', '-')}.html",
        mime="text/html",
        use_container_width=True,
    )
    columns = st.columns(2)
    columns[0].link_button(
        "Solicitar cotización",
        BRAND.demo_request_url(
            f"Cotización después de diagnóstico ecológico: {project_name}"
        ),
        use_container_width=True,
    )
    columns[1].link_button(
        "Agendar conversación",
        BRAND.demo_request_url(
            f"Reunión después de diagnóstico ecológico: {organization_name}"
        ),
        use_container_width=True,
    )


def render_public_ecological_diagnostic(
    record_lead: LeadRecorder | None = None,
) -> None:
    _apply_public_diagnostic_styles()
    st.markdown(
        '<a href="?" style="text-decoration:none;font-weight:700;">← Volver a BioCore</a>',
        unsafe_allow_html=True,
    )
    st.title(DIAGNOSTIC_NAME)
    st.subheader(DIAGNOSTIC_SUBTITLE)
    st.write(DIAGNOSTIC_DESCRIPTION)
    st.info(
        "Este diagnóstico es gratuito, no requiere cuenta ni suscripción y entrega "
        "una orientación automática inmediata."
    )
    st.warning(DIAGNOSTIC_DISCLAIMER, icon="⚠️")
    st.caption(
        f"Diagnóstico breve · {len(BRIEF_QUESTIONS)} preguntas · "
        f"Cuestionario {QUESTIONNAIRE_VERSION}"
    )

    with st.form("public_ecological_diagnostic_form"):
        st.markdown("### Datos de contacto")
        contact_left, contact_right = st.columns(2)
        with contact_left:
            contact_name = st.text_input("Nombre y apellido *")
            contact_email = st.text_input("Correo electrónico *")
            contact_phone = st.text_input("Teléfono (opcional)")
        with contact_right:
            organization_name = st.text_input("Empresa u organización (opcional)")
            project_name = st.text_input("Proyecto, predio o iniciativa *")
            activity_type = st.text_input("Tipo de actividad")

        st.markdown("### Ubicación y objetivo")
        location_left, location_right = st.columns(2)
        with location_left:
            commune = st.text_input("Comuna")
            region = st.text_input("Región")
            surface_hectares = st.number_input(
                "Superficie aproximada (hectáreas)",
                min_value=0.0,
                value=0.0,
                step=1.0,
            )
        with location_right:
            objective = st.text_area("¿Qué necesitas evaluar o resolver?")
            client_needs = st.multiselect(
                "¿Qué necesitas lograr con esta información?",
                CLIENT_NEED_OPTIONS,
            )

        st.markdown("### Cuestionario ecológico breve")
        responses = _questionnaire()
        st.divider()
        st.warning(DIAGNOSTIC_DISCLAIMER, icon="⚠️")
        scope_accepted = st.checkbox(
            "Comprendo que el resultado es preliminar y no reemplaza una revisión profesional."
        )
        contact_consent = st.checkbox(
            "Autorizo a BioCore a guardar estos antecedentes y contactarme sobre este diagnóstico."
        )
        submitted = st.form_submit_button(
            "Generar diagnóstico gratuito",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        metadata: dict[str, object] = {
            "commune": commune.strip(),
            "region": region.strip(),
            "surface_hectares": surface_hectares,
            "activity_type": activity_type.strip(),
            "objective": objective.strip(),
            "client_needs": client_needs,
        }
        try:
            if not scope_accepted:
                raise PublicLeadValidationError(
                    "Debes aceptar el alcance preliminar antes de generar el resultado."
                )
            lead_id = str(uuid4())
            service = _assessment_service()
            assessment = service.assess(
                lead_id,
                "public-prospect",
                responses,
                assessment_version=1,
            )
            payload = build_public_lead_payload(
                lead_id=lead_id,
                contact_name=contact_name,
                contact_email=contact_email,
                contact_phone=contact_phone,
                organization_name=organization_name,
                project_name=project_name,
                metadata=metadata,
                responses=responses,
                assessment=assessment,
                contact_consent=contact_consent,
            )
            saved = False
            if record_lead is not None:
                try:
                    record_lead(payload)
                    saved = True
                except Exception:
                    saved = False
            diagnostic = _temporary_diagnostic(lead_id, project_name.strip(), metadata)
            report = service.render_preliminary_report(
                diagnostic,
                assessment,
                organization_name=organization_name.strip() or contact_name.strip(),
            )
            st.session_state[_RESULT_KEY] = {
                "assessment": assessment,
                "project_name": project_name.strip(),
                "organization_name": organization_name.strip(),
                "report": report,
                "saved": saved,
            }
        except (PublicLeadValidationError, DiagnosticValidationError) as error:
            st.error(str(error))

    result = st.session_state.get(_RESULT_KEY)
    if isinstance(result, dict):
        _render_result(result)
