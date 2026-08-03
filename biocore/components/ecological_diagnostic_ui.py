from html import escape
from typing import Any

import streamlit as st

from biocore.components.module_access import current_platform_state
from biocore.components.page_header import render_page_header
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
    DiagnosticBundle,
    EcologicalDiagnostic,
    QuestionKind,
)
from biocore.security.authorization import require_permission
from biocore.security.roles import Permission
from biocore.services.ecological_diagnostics import (
    LEVEL_LABELS,
    DiagnosticValidationError,
    EcologicalDiagnosticService,
)


def _service() -> EcologicalDiagnosticService:
    service = st.session_state.get("biocore_ecological_diagnostic_service")
    if not isinstance(service, EcologicalDiagnosticService):
        st.error("El servicio de diagnóstico no está disponible en esta sesión.")
        st.stop()
    return service


def _answer_key(diagnostic_id: str | None, question_key: str) -> str:
    return f"ecological_{diagnostic_id or 'new'}_{question_key}"


def _questionnaire(
    existing: dict[str, Any],
    diagnostic_id: str | None,
) -> dict[str, object]:
    answers: dict[str, object] = {}
    active_section = ""
    for question in BRIEF_QUESTIONS:
        if question.section != active_section:
            active_section = question.section
            st.markdown(f"#### {escape(active_section)}")

        key = _answer_key(diagnostic_id, question.key)
        previous = existing.get(question.key)
        if question.kind == QuestionKind.BOOLEAN:
            index = 0 if previous is True else 1 if previous is False else None
            answers[question.key] = st.radio(
                question.prompt,
                options=(True, False),
                format_func=lambda value: "Sí" if value else "No",
                index=index,
                horizontal=True,
                key=key,
            )
        else:
            labels = {value: label for value, label in question.options}
            answers[question.key] = st.multiselect(
                question.prompt,
                options=list(labels),
                default=[
                    value
                    for value in (previous or [])
                    if value in labels
                ],
                format_func=lambda value, item_labels=labels: item_labels[value],
                key=key,
            )
    return answers


def _metadata_form(
    existing: dict[str, Any],
    organization_name: str,
    diagnostic_title: str,
) -> tuple[str, dict[str, object]]:
    st.markdown("### Organización y proyecto")
    st.text_input("Organización", value=organization_name, disabled=True)
    first, second = st.columns(2)
    with first:
        project_name = st.text_input(
            "Nombre del proyecto o predio *",
            value=diagnostic_title,
        )
        commune = st.text_input(
            "Comuna",
            value=str(existing.get("commune") or ""),
        )
        region = st.text_input(
            "Región",
            value=str(existing.get("region") or ""),
        )
        project_reference = st.text_input(
            "Referencia de proyecto BioCore (opcional)",
            value=str(existing.get("project_reference") or ""),
        )
        surface = st.number_input(
            "Superficie aproximada (hectáreas)",
            min_value=0.0,
            value=float(existing.get("surface_hectares") or 0),
            step=1.0,
        )
    with second:
        activity = st.text_input(
            "Tipo de actividad",
            value=str(existing.get("activity_type") or ""),
        )
        stage_options = (
            "Idea o prefactibilidad",
            "Diseño",
            "Operación",
            "Monitoreo",
            "Otro",
        )
        previous_stage = str(existing.get("project_stage") or stage_options[0])
        stage_index = (
            stage_options.index(previous_stage)
            if previous_stage in stage_options
            else 0
        )
        stage = st.selectbox(
            "Etapa del proyecto",
            stage_options,
            index=stage_index,
        )
        contact = st.text_input(
            "Persona de contacto",
            value=str(existing.get("contact_name") or ""),
        )
        objective = st.text_area(
            "Objetivo del diagnóstico",
            value=str(existing.get("objective") or ""),
        )

    client_needs = st.multiselect(
        "¿Qué necesita lograr con esta información?",
        CLIENT_NEED_OPTIONS,
        default=[
            item
            for item in existing.get("client_needs", [])
            if item in CLIENT_NEED_OPTIONS
        ],
    )
    metadata = {
        "commune": commune.strip(),
        "region": region.strip(),
        "project_reference": project_reference.strip(),
        "surface_hectares": surface,
        "activity_type": activity.strip(),
        "project_stage": stage,
        "contact_name": contact.strip(),
        "objective": objective.strip(),
        "client_needs": client_needs,
    }
    return project_name, metadata


def _render_dimension(assessment: DiagnosticAssessment) -> None:
    for index in range(0, len(assessment.scores), 2):
        columns = st.columns(2, gap="medium")
        for column, item in zip(columns, assessment.scores[index : index + 2]):
            with column:
                st.markdown(
                    f"""
                    <section class="bc-private-card">
                        <small>{escape(LEVEL_LABELS[item.level])}</small>
                        <h3>{escape(DIMENSION_LABELS[item.dimension])}</h3>
                        <p>Confianza del resultado: <strong>{escape(item.confidence)}</strong></p>
                    </section>
                    """,
                    unsafe_allow_html=True,
                )
                st.progress(item.score / 100, text=f"{item.score} de 100")
                with st.expander("Ver explicación"):
                    st.markdown(f"**Por qué es relevante:** {item.relevance}")
                    if item.found:
                        st.markdown("**Antecedentes encontrados**")
                        for text in item.found:
                            st.markdown(f"- {text}")
                    if item.missing:
                        st.markdown("**Antecedentes faltantes o parciales**")
                        for text in item.missing:
                            st.markdown(f"- {text}")
                    st.markdown(f"**Acción sugerida:** {item.recommended_action}")


def _render_results(
    service: EcologicalDiagnosticService,
    bundle: DiagnosticBundle,
    assessment: DiagnosticAssessment,
    organization_name: str,
    *,
    can_request_review: bool,
) -> None:
    st.divider()
    st.warning(DIAGNOSTIC_DISCLAIMER, icon="⚠️")
    st.caption(PRELIMINARY_REPORT_LABEL)
    st.markdown("## Resultado preliminar")
    st.metric(
        "Nivel general de información disponible",
        LEVEL_LABELS[assessment.general_level],
    )
    st.caption(
        "Este nivel describe la información disponible, no una conclusión "
        "técnica definitiva."
    )
    _render_dimension(assessment)

    st.markdown("### Brechas principales")
    if assessment.findings:
        for finding in assessment.findings:
            st.markdown(
                f"**Prioridad {finding.priority} · {finding.title}**  \n"
                f"{finding.explanation}"
            )
    else:
        st.info("No se generaron brechas automáticas con las respuestas disponibles.")

    st.markdown("### Recomendaciones y servicios BioCore")
    if assessment.recommendations:
        for recommendation in assessment.recommendations:
            st.markdown(
                f"""
                <section class="bc-private-card">
                    <small>Prioridad {escape(recommendation.priority)}</small>
                    <h3>{escape(recommendation.title)}</h3>
                    <p>{escape(recommendation.detail)}</p>
                </section>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "La información parece preparada para una revisión profesional. "
            "BioCore debe confirmar el alcance."
        )

    report = service.render_preliminary_report(
        bundle.diagnostic,
        assessment,
        organization_name=organization_name,
    )
    st.download_button(
        "Descargar informe preliminar",
        data=report,
        file_name=(
            f"diagnostico-ecologico-{bundle.diagnostic.id[:8]}-"
            f"v{assessment.assessment_version}.html"
        ),
        mime="text/html",
        use_container_width=True,
    )

    st.markdown("### Revisión profesional")
    st.write(
        "Una persona especialista de BioCore puede revisar los antecedentes, "
        "confirmar el alcance y proponer próximos pasos."
    )
    review_message = st.text_area(
        "Mensaje para BioCore",
        key=f"review_message_{bundle.diagnostic.id}",
    )
    if not can_request_review:
        st.info(
            "Tu rol permite consultar el resultado, pero no solicitar una revisión."
        )
    elif bundle.review_requests:
        st.success("La revisión profesional ya fue solicitada.")
    elif st.button(
        "Solicitar revisión profesional",
        type="primary",
        use_container_width=True,
        key=f"request_review_{bundle.diagnostic.id}",
    ):
        service.request_professional_review(
            current_platform_state()[0],
            bundle.diagnostic.id,
            review_message,
        )
        st.success("Solicitud registrada en la bandeja interna de BioCore.")
        st.rerun()

    sales_columns = st.columns(2)
    sales_columns[0].link_button(
        "Solicitar cotización",
        BRAND.demo_request_url("Cotización de servicio ecológico BioCore"),
        use_container_width=True,
    )
    sales_columns[1].link_button(
        "Agendar reunión",
        BRAND.demo_request_url("Reunión sobre diagnóstico ecológico"),
        use_container_width=True,
    )
    product_columns = st.columns(2)
    product_columns[0].link_button(
        "Conocer BioCore MycoField",
        BRAND.demo_request_url("Información sobre BioCore MycoField"),
        use_container_width=True,
    )
    product_columns[1].link_button(
        "Conocer DarwinCheck",
        BRAND.demo_request_url("Información sobre DarwinCheck"),
        use_container_width=True,
    )
    st.button(
        "Convertir en proyecto",
        disabled=True,
        help=(
            "Se habilitará después de la revisión profesional y cuando el "
            "repositorio de proyectos esté conectado."
        ),
        use_container_width=True,
    )


def render_ecological_diagnostic_page() -> None:
    context, subscription = current_platform_state()
    require_permission(context, Permission.ECOLOGICAL_DIAGNOSTIC_READ)
    service = _service()
    render_page_header(
        "Orientación ecológica preliminar",
        DIAGNOSTIC_NAME,
        DIAGNOSTIC_SUBTITLE,
    )
    st.write(DIAGNOSTIC_DESCRIPTION)
    st.warning(DIAGNOSTIC_DISCLAIMER, icon="⚠️")
    st.caption(
        f"Diagnóstico breve · {len(BRIEF_QUESTIONS)} preguntas · "
        f"Cuestionario {QUESTIONNAIRE_VERSION} · Sin pagos"
    )

    try:
        history = service.list_for_context(context)
    except Exception:
        st.error(
            "El almacenamiento del diagnóstico todavía no está disponible. "
            "Aplica la migración 0003_ecological_diagnostics.sql."
        )
        st.stop()

    with st.expander("Diagnósticos guardados", expanded=False):
        if not history:
            st.caption("Todavía no hay diagnósticos en esta organización.")
        else:
            options = {item.id: item for item in history}
            selected_id = st.selectbox(
                "Selecciona un diagnóstico",
                list(options),
                format_func=lambda item_id: (
                    f"{options[item_id].title} · "
                    f"{options[item_id].status.value.replace('_', ' ')}"
                ),
            )
            load_column, new_column = st.columns(2)
            if load_column.button(
                "Cargar diagnóstico",
                use_container_width=True,
            ):
                st.session_state["ecological_diagnostic_id"] = selected_id
                st.rerun()
            if new_column.button(
                "Comenzar uno nuevo",
                use_container_width=True,
            ):
                st.session_state.pop("ecological_diagnostic_id", None)
                st.session_state.pop("ecological_diagnostic_assessment", None)
                st.rerun()

    diagnostic_id = st.session_state.get("ecological_diagnostic_id")
    bundle = (
        service.get_bundle(context, diagnostic_id)
        if diagnostic_id
        else None
    )
    can_write = context.has_permission(
        Permission.ECOLOGICAL_DIAGNOSTIC_WRITE
    )
    if not can_write:
        st.info(
            "Tu rol tiene acceso de lectura. Una persona administradora de la "
            "organización puede crear o modificar diagnósticos."
        )
        if bundle and bundle.assessments:
            _render_results(
                service,
                bundle,
                bundle.assessments[-1],
                subscription.organization_name,
                can_request_review=False,
            )
        return

    existing_answers = bundle.responses if bundle else {}
    metadata = bundle.diagnostic.metadata if bundle else {}
    diagnostic_title = bundle.diagnostic.title if bundle else ""

    with st.form("ecological_diagnostic_form"):
        project_name, updated_metadata = _metadata_form(
            metadata,
            subscription.organization_name,
            diagnostic_title,
        )
        st.markdown("### Cuestionario breve")
        st.caption(
            "Responde según los antecedentes disponibles. Una respuesta negativa "
            "identifica una brecha de información, no una conclusión técnica."
        )
        responses = _questionnaire(existing_answers, diagnostic_id)
        st.divider()
        st.warning(DIAGNOSTIC_DISCLAIMER, icon="⚠️")
        accepted = st.checkbox(
            "Comprendo y acepto el alcance preliminar del diagnóstico."
        )
        save_button = st.form_submit_button(
            "Guardar avance",
            use_container_width=True,
        )
        submit_button = st.form_submit_button(
            "Generar resultado preliminar",
            type="primary",
            use_container_width=True,
        )

    if save_button or submit_button:
        try:
            if bundle is None:
                diagnostic = service.create_diagnostic(
                    context,
                    title=project_name,
                    metadata=updated_metadata,
                    project_reference=(
                        str(updated_metadata.get("project_reference") or "")
                        or None
                    ),
                )
                diagnostic_id = diagnostic.id
                st.session_state["ecological_diagnostic_id"] = diagnostic_id
            if save_button:
                service.save_progress(
                    context,
                    diagnostic_id,
                    responses,
                    metadata=updated_metadata,
                )
                st.success("Avance guardado para esta organización.")
                st.rerun()
            if submit_button:
                _, assessment = service.submit(
                    context,
                    diagnostic_id,
                    responses,
                    disclaimer_accepted=accepted,
                    metadata=updated_metadata,
                )
                st.session_state["ecological_diagnostic_assessment"] = assessment
                st.success("Resultado preliminar generado y versionado.")
                st.rerun()
        except DiagnosticValidationError as error:
            st.error(str(error))
        except Exception:
            st.error(
                "No fue posible guardar el diagnóstico. Revisa la migración "
                "y vuelve a intentarlo."
            )

    if diagnostic_id:
        refreshed = service.get_bundle(context, diagnostic_id)
        if refreshed and refreshed.assessments:
            _render_results(
                service,
                refreshed,
                refreshed.assessments[-1],
                subscription.organization_name,
                can_request_review=True,
            )


def render_diagnostic_inbox() -> None:
    context, _ = current_platform_state()
    require_permission(context, Permission.PLATFORM_ADMIN)
    service = _service()
    render_page_header(
        "Gestión interna BioCore",
        "Bandeja de diagnósticos ecológicos",
        (
            "Solicitudes de revisión profesional y oportunidades vinculadas "
            "con diagnósticos preliminares."
        ),
    )
    try:
        queue = service.list_review_queue(context)
    except Exception:
        st.error(
            "La bandeja todavía no está disponible. Revisa la migración del "
            "diagnóstico ecológico."
        )
        return

    st.metric("Solicitudes registradas", len(queue))
    if not queue:
        st.info("No hay solicitudes de revisión profesional.")
        return

    for request, bundle in queue:
        if bundle is None:
            continue
        diagnostic = bundle.diagnostic
        region = str(diagnostic.metadata.get("region") or "Sin región informada")
        surface = diagnostic.metadata.get("surface_hectares")
        components = bundle.responses.get("components_of_interest", [])
        with st.expander(
            f"{diagnostic.title} · {request.requested_at.strftime('%d/%m/%Y')}",
            expanded=False,
        ):
            st.write(f"Organización: `{diagnostic.organization_id}`")
            st.write(f"Región: {region}")
            st.write(
                "Superficie: "
                + (f"{surface} ha" if surface else "No informada")
            )
            st.write(
                "Componentes: "
                + (", ".join(str(item) for item in components) or "No informados")
            )
            st.write(f"Estado de contacto: {request.status.value}")
            st.write("Oportunidad comercial: revisión profesional solicitada")
            st.write(
                "Conversión a proyecto: "
                + (
                    "Registrada"
                    if diagnostic.status.value == "converted_to_project"
                    else "Pendiente"
                )
            )
            st.write(f"Mensaje: {request.message or 'Sin mensaje adicional'}")
            if bundle.assessments:
                st.write(
                    "Nivel general: "
                    + LEVEL_LABELS[bundle.assessments[-1].general_level]
                )
