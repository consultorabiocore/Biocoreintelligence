from datetime import datetime
from html import escape
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

import streamlit as st

from biocore.config.brand import BRAND
from biocore.services.public_diagnostic_leads import (
    PublicLeadValidationError,
    validate_public_lead_contact,
)

LeadRecorder = Callable[[dict[str, object]], str]
_RESULT_KEY = "biocore_public_initial_diagnostic_result"
QUESTIONNAIRE_VERSION = "initial-1.0"
RULES_VERSION = "initial-readiness-1.0"

PROJECT_TYPES = (
    "Predio agrícola, forestal o rural",
    "Proyecto inmobiliario o de infraestructura",
    "Energía, minería o industria",
    "Conservación, restauración o investigación",
    "Empresa con información ambiental acumulada",
    "Otro tipo de proyecto",
)
PROJECT_STAGES = (
    "Solo es una idea o estoy explorando",
    "Está en planificación",
    "Ya está en ejecución",
    "Necesita seguimiento o monitoreo",
)
INFORMATION_LEVELS = (
    "No tengo información ecológica previa",
    "Tengo algunos archivos, fotografías o informes",
    "Tengo información, pero está dispersa o desordenada",
    "Tengo información organizada y relativamente actualizada",
)
MAIN_NEEDS = (
    "Saber si mis antecedentes son suficientes",
    "Evaluar si necesito una campaña de terreno",
    "Ordenar información ambiental existente",
    "Preparar mapas o un informe",
    "Definir un plan de seguimiento o monitoreo",
    "Solicitar orientación o una cotización",
    "Todavía no sé qué necesito",
)
COMPONENT_OPTIONS = (
    "Flora y vegetación",
    "Fauna",
    "Hongos y líquenes",
    "Ecosistemas acuáticos",
    "Otros componentes ambientales",
    "No lo sé todavía",
)
TIMELINES = (
    "Lo antes posible",
    "Durante el próximo mes",
    "En los próximos meses",
    "Solo estoy explorando",
)


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h1,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h2,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h3,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] h4,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] p,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] label,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] label p,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stCaptionContainer"],
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stMarkdownContainer"] {
            color: #14211b !important;
        }
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stAlert"] *,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stCheckbox"] label p {
            color: #24342c !important;
        }
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="input"] > div,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            border-color: #aebfb5 !important;
            color: #14211b !important;
        }
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] input,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="select"] span,
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-baseweb="select"] div {
            color: #14211b !important;
            -webkit-text-fill-color: #14211b !important;
        }
        body [data-testid="stMain"] [data-testid="stMainBlockContainer"] [data-testid="stForm"] {
            padding: 1.25rem;
            border: 1px solid #dbe5de;
            border-radius: 18px;
            background: #fbfdfb;
        }
        .bc-readiness-card {
            padding: 22px;
            margin: 12px 0 18px;
            border: 1px solid #d8e5dc;
            border-radius: 18px;
            background: #ffffff;
            box-shadow: 0 10px 28px rgba(18,55,42,.06);
        }
        .bc-readiness-card small {
            display: block;
            margin-bottom: 6px;
            color: #2f7d4a !important;
            font-weight: 800;
            letter-spacing: .06em;
            text-transform: uppercase;
        }
        .bc-readiness-card h3 { margin: 0 0 10px; color: #12372a !important; }
        .bc-paid-card {
            padding: 22px;
            margin-top: 22px;
            border: 1px solid #d8c48f;
            border-radius: 18px;
            background: #fffaf0;
        }
        .bc-paid-card h3 { margin-top: 0; color: #12372a !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _professional_url(project: str, organization: str, name: str) -> str:
    subject = "Solicitud de Diagnóstico Profesional BioCore"
    body = (
        "Hola BioCore,\n\n"
        "Realicé el Diagnóstico Inicial gratuito y quisiera solicitar información "
        "sobre el Diagnóstico Profesional BioCore.\n\n"
        f"Nombre: {name}\nOrganización: {organization}\nProyecto: {project}\n"
    )
    return f"mailto:{BRAND.sales_email}?subject={quote(subject)}&body={quote(body)}"


def _evaluate(responses: dict[str, object]) -> dict[str, Any]:
    info_scores = {
        INFORMATION_LEVELS[0]: 0,
        INFORMATION_LEVELS[1]: 1,
        INFORMATION_LEVELS[2]: 2,
        INFORMATION_LEVELS[3]: 4,
    }
    stage_scores = {
        PROJECT_STAGES[0]: 0,
        PROJECT_STAGES[1]: 1,
        PROJECT_STAGES[2]: 2,
        PROJECT_STAGES[3]: 2,
    }
    information = str(responses["information_level"])
    stage = str(responses["project_stage"])
    need = str(responses["main_need"])
    timeline = str(responses["timeline"])
    components = [str(v) for v in responses["components"]]
    score = info_scores[information] + stage_scores[stage]
    score += 0 if "No lo sé todavía" in components else 1

    if score <= 2:
        level = "Nivel inicial"
        headline = "Tu proyecto necesita definir mejor su punto de partida"
        summary = (
            "Todavía faltan antecedentes básicos para decidir con seguridad qué "
            "estudio, revisión o servicio ambiental conviene realizar."
        )
    elif score <= 5:
        level = "Nivel intermedio"
        headline = "Tu proyecto tiene antecedentes, pero requiere orden y revisión"
        summary = (
            "Existe información útil, aunque conviene revisar su vigencia, cobertura "
            "y capacidad para responder al objetivo actual."
        )
    else:
        level = "Preparado para revisión profesional"
        headline = "Tu proyecto parece listo para una revisión técnica"
        summary = (
            "Cuentas con una base que BioCore puede revisar para definir brechas, "
            "prioridades y el alcance del siguiente servicio."
        )

    gaps: list[str] = []
    if information == INFORMATION_LEVELS[0]:
        gaps.append("Identificar qué antecedentes existen antes de definir un estudio.")
    elif information == INFORMATION_LEVELS[1]:
        gaps.append("Revisar si los archivos existentes son vigentes y utilizables.")
    elif information == INFORMATION_LEVELS[2]:
        gaps.append("Ordenar la información para detectar duplicidades y vacíos.")
    else:
        gaps.append("Validar profesionalmente la cobertura y calidad de la información.")

    if "No lo sé todavía" in components:
        gaps.append("Definir qué componentes ambientales deben incluirse en el alcance.")
    else:
        gaps.append("Confirmar si los componentes seleccionados requieren terreno.")

    if timeline == TIMELINES[0]:
        gaps.append("Priorizar una revisión temprana para evitar decisiones urgentes.")
    elif need == MAIN_NEEDS[1]:
        gaps.append("Determinar si una campaña de terreno es necesaria y cuál sería su alcance.")
    elif need == MAIN_NEEDS[3]:
        gaps.append("Comprobar que los datos permiten elaborar mapas o productos confiables.")
    elif need == MAIN_NEEDS[4]:
        gaps.append("Definir indicadores y frecuencia antes de iniciar el monitoreo.")
    else:
        gaps.append("Traducir la necesidad general en un alcance técnico concreto.")

    return {
        "level_label": level,
        "headline": headline,
        "summary": summary,
        "score": score,
        "maximum_score": 7,
        "gaps": gaps[:3],
        "next_step": (
            "Solicitar un Diagnóstico Profesional BioCore para que una profesional "
            "revise los antecedentes y determine qué sirve, qué falta y cuál debería "
            "ser el siguiente paso."
        ),
    }


def _report(project: str, organization: str, responses: dict[str, object], result: dict[str, Any]) -> bytes:
    gaps = "".join(f"<li>{escape(str(v))}</li>" for v in result["gaps"])
    components = ", ".join(str(v) for v in responses["components"])
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Diagnóstico Inicial BioCore</title><style>
body{{font-family:Arial,sans-serif;color:#17362c;max-width:820px;margin:40px auto;line-height:1.6}}
h1,h2{{color:#12372a}}.notice{{padding:16px;border:1px solid #d8c48f;background:#fffaf0}}
.card{{padding:18px;border:1px solid #d9e4dc;border-radius:14px;background:#fbfdfb}}
</style></head><body><h1>Diagnóstico Inicial BioCore</h1>
<div class="notice">Resultado automático gratuito. No identifica especies, no confirma
presencia o ausencia, no evalúa impactos y no reemplaza una revisión profesional.</div>
<h2>Identificación</h2><p>Organización: {escape(organization or 'No informada')}<br>
Proyecto: {escape(project)}<br>Fecha: {datetime.utcnow().strftime('%d/%m/%Y')}</p>
<div class="card"><h2>{escape(str(result['level_label']))}</h2>
<p><strong>{escape(str(result['headline']))}</strong></p><p>{escape(str(result['summary']))}</p></div>
<h2>Respuestas</h2><p>Tipo: {escape(str(responses['project_type']))}<br>
Etapa: {escape(str(responses['project_stage']))}<br>
Información: {escape(str(responses['information_level']))}<br>
Necesidad: {escape(str(responses['main_need']))}<br>
Componentes: {escape(components)}<br>Plazo: {escape(str(responses['timeline']))}</p>
<h2>Aspectos a revisar</h2><ul>{gaps}</ul><h2>Siguiente paso</h2>
<p>{escape(str(result['next_step']))}</p></body></html>"""
    return html.encode("utf-8")


def _payload(
    lead_id: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    organization: str,
    project: str,
    commune: str,
    region: str,
    responses: dict[str, object],
    result: dict[str, Any],
    consent: bool,
) -> dict[str, object]:
    validate_public_lead_contact(
        contact_name=contact_name,
        contact_email=contact_email,
        project_name=project,
        contact_consent=consent,
    )
    return {
        "id": lead_id,
        "source": "public_initial_diagnostic",
        "status": "new",
        "contact_name": contact_name.strip(),
        "contact_email": contact_email.strip().lower(),
        "contact_phone": contact_phone.strip(),
        "organization_name": organization.strip(),
        "project_name": project.strip(),
        "commune": commune.strip(),
        "region": region.strip(),
        "activity_type": str(responses["project_type"]),
        "surface_hectares": None,
        "objective": str(responses["main_need"]),
        "client_needs": [str(responses["main_need"])],
        "metadata": {
            "project_stage": responses["project_stage"],
            "information_level": responses["information_level"],
            "components": responses["components"],
            "timeline": responses["timeline"],
        },
        "responses": responses,
        "result": result,
        "questionnaire_version": QUESTIONNAIRE_VERSION,
        "rules_version": RULES_VERSION,
        "contact_consent": True,
        "consented_at": datetime.utcnow().isoformat(),
    }


def _render_result(bundle: dict[str, Any]) -> None:
    result = dict(bundle["result"])
    st.divider()
    st.success("Tu orientación inicial está lista.")
    st.markdown(
        f"""<section class="bc-readiness-card"><small>{escape(str(result['level_label']))}</small>
<h3>{escape(str(result['headline']))}</h3><p>{escape(str(result['summary']))}</p></section>""",
        unsafe_allow_html=True,
    )
    st.progress(
        int(result["score"]) / int(result["maximum_score"]),
        text="Preparación general para una revisión profesional",
    )
    st.markdown("### Aspectos que conviene revisar")
    for gap in result["gaps"]:
        st.markdown(f"- {gap}")
    st.info(str(result["next_step"]))
    if bundle["saved"]:
        st.caption("BioCore recibió tus datos y podrá orientarte sobre el siguiente paso.")
    else:
        st.warning("El resumen se generó, pero los datos no pudieron guardarse.")
    st.download_button(
        "Descargar resumen inicial",
        data=bytes(bundle["report"]),
        file_name="diagnostico-inicial-biocore.html",
        mime="text/html",
        use_container_width=True,
    )
    st.markdown(
        """<section class="bc-paid-card"><h3>¿Necesitas saber exactamente qué sirve y qué falta?</h3>
<p>El <strong>Diagnóstico Profesional BioCore</strong> incluye revisión humana de archivos,
identificación de brechas, recomendaciones priorizadas, informe profesional breve y reunión de explicación.</p>
<p>No incluye campaña de terreno, identificación taxonómica nueva, evaluación de impactos ni
pronunciamiento normativo. Esos servicios se cotizan por separado cuando corresponda.</p></section>""",
        unsafe_allow_html=True,
    )
    st.link_button(
        "Solicitar Diagnóstico Profesional BioCore",
        _professional_url(bundle["project"], bundle["organization"], bundle["contact_name"]),
        type="primary",
        use_container_width=True,
    )
    st.caption("Servicio pagado sujeto a cotización.")


def render_public_ecological_diagnostic(record_lead: LeadRecorder | None = None) -> None:
    _apply_styles()
    st.markdown('<a href="?" style="text-decoration:none;font-weight:700;">← Volver a BioCore</a>', unsafe_allow_html=True)
    st.title("Diagnóstico Inicial BioCore")
    st.subheader("Descubre qué necesita tu proyecto y cuál debería ser el próximo paso")
    st.write(
        "Responde seis preguntas simples. Recibirás una orientación automática sobre "
        "el nivel de preparación de tu proyecto y si conviene solicitar una revisión profesional."
    )
    st.info("Gratuito · aproximadamente 3 minutos · no requiere suscripción")
    st.warning(
        "No identifica especies, no confirma presencia o ausencia, no evalúa impactos y no reemplaza trabajo profesional.",
        icon="⚠️",
    )

    with st.form("public_initial_diagnostic_form"):
        st.markdown("### Tu proyecto")
        left, right = st.columns(2)
        with left:
            contact_name = st.text_input("Nombre y apellido *")
            contact_email = st.text_input("Correo electrónico *")
            organization = st.text_input("Empresa u organización (opcional)")
            project = st.text_input("Proyecto, predio o iniciativa *")
        with right:
            contact_phone = st.text_input("Teléfono (opcional)")
            region = st.text_input("Región (opcional)")
            commune = st.text_input("Comuna (opcional)")

        st.markdown("### Seis preguntas rápidas")
        project_type = st.selectbox("1. ¿Qué tipo de proyecto o actividad tienes?", PROJECT_TYPES, index=None)
        project_stage = st.selectbox("2. ¿En qué etapa se encuentra?", PROJECT_STAGES, index=None)
        information_level = st.selectbox("3. ¿Qué información ecológica previa tienes?", INFORMATION_LEVELS, index=None)
        main_need = st.selectbox("4. ¿Qué necesitas principalmente?", MAIN_NEEDS, index=None)
        components = st.multiselect("5. ¿Qué componentes podrían estar involucrados?", COMPONENT_OPTIONS)
        timeline = st.selectbox("6. ¿Cuándo necesitas avanzar?", TIMELINES, index=None)

        scope = st.checkbox("Comprendo que es una orientación inicial y no reemplaza una revisión profesional.")
        consent = st.checkbox("Autorizo a BioCore a guardar estos antecedentes y contactarme.")
        submitted = st.form_submit_button("Ver mi orientación inicial", type="primary", use_container_width=True)

    if submitted:
        try:
            if not scope:
                raise PublicLeadValidationError("Debes aceptar el alcance del diagnóstico inicial.")
            values = (project_type, project_stage, information_level, main_need, timeline)
            if any(value is None for value in values):
                raise PublicLeadValidationError("Completa las seis preguntas para continuar.")
            if not components:
                raise PublicLeadValidationError("Selecciona un componente o “No lo sé todavía”.")
            responses: dict[str, object] = {
                "project_type": project_type,
                "project_stage": project_stage,
                "information_level": information_level,
                "main_need": main_need,
                "components": components,
                "timeline": timeline,
            }
            result = _evaluate(responses)
            payload = _payload(
                str(uuid4()), contact_name, contact_email, contact_phone,
                organization, project, commune, region, responses, result, consent
            )
            saved = False
            if record_lead is not None:
                try:
                    record_lead(payload)
                    saved = True
                except Exception:
                    saved = False
            st.session_state[_RESULT_KEY] = {
                "result": result,
                "project": project.strip(),
                "organization": organization.strip(),
                "contact_name": contact_name.strip(),
                "report": _report(project.strip(), organization.strip(), responses, result),
                "saved": saved,
            }
        except PublicLeadValidationError as error:
            st.error(str(error))

    bundle = st.session_state.get(_RESULT_KEY)
    if isinstance(bundle, dict):
        _render_result(bundle)
