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
_RESULT_KEY = "biocore_initial_diagnostic_result_v3"
QUESTIONNAIRE_VERSION = "initial-2.1"
RULES_VERSION = "initial-readiness-2.1"

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
    "Varios componentes ambientales",
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
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stMain"] > div,
        [data-testid="stMainBlockContainer"],
        [data-testid="stMain"] .block-container {
            background: #f5f8f5 !important;
        }

        [data-testid="stMain"] .block-container {
            max-width: 920px;
        }

        [data-testid="stMain"] h1,
        [data-testid="stMain"] h2,
        [data-testid="stMain"] h3,
        [data-testid="stMain"] h4,
        [data-testid="stMain"] p,
        [data-testid="stMain"] small,
        [data-testid="stMain"] label,
        [data-testid="stMain"] label p,
        [data-testid="stMain"] span,
        [data-testid="stMain"] [data-testid="stCaptionContainer"],
        [data-testid="stMain"] [data-testid="stMarkdownContainer"] {
            color: #14211b !important;
        }

        [data-testid="stMain"] [data-testid="stAlert"] *,
        [data-testid="stMain"] [data-testid="stRadio"] *,
        [data-testid="stMain"] [data-testid="stCheckbox"] * {
            color: #24342c !important;
        }

        [data-testid="stMain"] [data-testid="stForm"] {
            padding: 1.25rem;
            border: 1px solid #dbe5de;
            border-radius: 18px;
            background: #fbfdfb;
        }

        /* Input, textarea, select, multiselect */
        [data-testid="stMain"] [data-testid="stTextInput"] input,
        [data-testid="stMain"] [data-testid="stTextArea"] textarea,
        [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
        [data-testid="stMain"] [data-baseweb="input"] > div,
        [data-testid="stMain"] [data-baseweb="textarea"] > div,
        [data-testid="stMain"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #14211b !important;
            -webkit-text-fill-color: #14211b !important;
            border: 1px solid #aebfb5 !important;
        }

        [data-testid="stMain"] [data-testid="stTextInput"] input::placeholder,
        [data-testid="stMain"] [data-testid="stTextArea"] textarea::placeholder {
            color: #6b7c73 !important;
            -webkit-text-fill-color: #6b7c73 !important;
            opacity: 1 !important;
        }

        [data-testid="stMain"] [data-testid="stSelectbox"] *,
        [data-testid="stMain"] [data-testid="stMultiSelect"] *,
        [data-testid="stMain"] [data-baseweb="select"] *,
        [data-testid="stMain"] [role="listbox"] *,
        [data-testid="stMain"] [role="option"] *,
        [data-testid="stMain"] [data-baseweb="popover"] * {
            color: #14211b !important;
            -webkit-text-fill-color: #14211b !important;
        }

        [data-testid="stMain"] [role="listbox"],
        [data-testid="stMain"] [role="option"],
        [data-testid="stMain"] [data-baseweb="popover"] {
            background: #ffffff !important;
        }

        [data-testid="stMain"] [data-baseweb="tag"] {
            background: #e9f5ec !important;
            color: #12372a !important;
            border: 1px solid #b7d2bf !important;
        }

        /* Radio blocks */
        [data-testid="stMain"] [data-testid="stRadio"] > div {
            gap: 8px !important;
        }

        [data-testid="stMain"] [data-testid="stRadio"] label {
            display: block !important;
            padding: 10px 14px !important;
            margin-bottom: 8px !important;
            border: 1px solid #dce6df !important;
            border-radius: 13px !important;
            background: #ffffff !important;
        }

        [data-testid="stMain"] [data-testid="stRadio"] label *,
        [data-testid="stMain"] [data-testid="stCheckbox"] label * {
            color: #24342c !important;
            -webkit-text-fill-color: #24342c !important;
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

        .bc-readiness-card h3 {
            margin: 0 0 10px;
            color: #12372a !important;
        }

        .bc-paid-card {
            padding: 22px;
            margin-top: 22px;
            border: 1px solid #d8c48f;
            border-radius: 18px;
            background: #fffaf0;
        }

        .bc-paid-card h3 {
            margin-top: 0;
            color: #12372a !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _professional_url(project_name: str, organization_name: str, contact_name: str) -> str:
    subject = "Solicitud de Diagnóstico Profesional BioCore"
    body = (
        "Hola BioCore,\n\n"
        "Realicé el Diagnóstico Inicial gratuito y quisiera solicitar información "
        "sobre el Diagnóstico Profesional BioCore.\n\n"
        f"Nombre: {contact_name}\n"
        f"Organización: {organization_name}\n"
        f"Proyecto: {project_name}\n\n"
        "Quedo atenta/o a los próximos pasos."
    )
    return f"mailto:{BRAND.sales_email}?subject={quote(subject)}&body={quote(body)}"


def _evaluate(responses: dict[str, object]) -> dict[str, Any]:
    information_scores = {
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

    information_level = str(responses["information_level"])
    project_stage = str(responses["project_stage"])
    main_need = str(responses["main_need"])
    timeline = str(responses["timeline"])
    component = str(responses["component"])

    score = information_scores[information_level] + stage_scores[project_stage] + (0 if component == "No lo sé todavía" else 1)

    if score <= 2:
        level_label = "Nivel inicial"
        headline = "Tu proyecto necesita definir mejor su punto de partida"
        summary = "Todavía faltan antecedentes básicos para decidir con seguridad qué estudio, revisión o servicio ambiental conviene realizar."
    elif score <= 5:
        level_label = "Nivel intermedio"
        headline = "Tu proyecto ya tiene antecedentes, pero requiere orden y revisión"
        summary = "Existe información útil, aunque conviene revisar su vigencia, cobertura y capacidad para responder al objetivo actual."
    else:
        level_label = "Preparado para revisión profesional"
        headline = "Tu proyecto parece listo para una revisión técnica"
        summary = "Cuentas con una base que BioCore puede evaluar profesionalmente para definir brechas, prioridades y el alcance del siguiente servicio."

    gaps: list[str] = []
    if information_level == INFORMATION_LEVELS[0]:
        gaps.append("Reunir o identificar los antecedentes disponibles antes de definir un estudio.")
    elif information_level == INFORMATION_LEVELS[1]:
        gaps.append("Revisar si los archivos existentes son suficientes, vigentes y utilizables.")
    elif information_level == INFORMATION_LEVELS[2]:
        gaps.append("Ordenar y clasificar la información para evitar duplicidades y vacíos.")
    else:
        gaps.append("Validar profesionalmente la cobertura y calidad de la información organizada.")

    if component == "No lo sé todavía":
        gaps.append("Definir qué componentes ambientales deberían incluirse en el alcance.")
    else:
        gaps.append("Confirmar si los componentes seleccionados requieren revisión documental o terreno.")

    if timeline == TIMELINES[0]:
        gaps.append("Priorizar una revisión temprana para evitar decisiones urgentes con información incompleta.")
    elif main_need == MAIN_NEEDS[1]:
        gaps.append("Determinar técnicamente si se necesita terreno y cuál debería ser su alcance.")
    elif main_need == MAIN_NEEDS[3]:
        gaps.append("Comprobar que los datos disponibles permiten elaborar mapas o informes confiables.")
    elif main_need == MAIN_NEEDS[4]:
        gaps.append("Definir indicadores, frecuencia y antecedentes base antes de iniciar el monitoreo.")
    else:
        gaps.append("Transformar la necesidad general en un alcance técnico, plazo y producto concreto.")

    return {
        "level_label": level_label,
        "headline": headline,
        "summary": summary,
        "score": score,
        "maximum_score": 7,
        "gaps": gaps[:3],
        "next_step": "Solicitar un Diagnóstico Profesional BioCore para revisar los antecedentes y determinar exactamente qué sirve, qué falta y cuál debería ser el siguiente paso.",
    }


def _report(project_name: str, organization_name: str, result: dict[str, Any]) -> bytes:
    items = "".join(f"<li>{escape(str(x))}</li>" for x in result["gaps"])
    html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Diagnóstico Inicial BioCore</title>
<style>
body{{font-family:Arial,sans-serif;color:#17362c;max-width:820px;margin:40px auto;line-height:1.6}}
h1,h2{{color:#12372a}} .box{{padding:18px;border:1px solid #d9e4dc;border-radius:14px}}
.notice{{padding:16px;background:#fffaf0;border:1px solid #d8c48f}}
</style>
</head>
<body>
<h1>Diagnóstico Inicial BioCore</h1>
<div class="notice">Este resultado es automático y orientativo. No identifica especies, no confirma presencia o ausencia, no evalúa impactos y no reemplaza una revisión profesional ni una campaña de terreno.</div>
<p>
<strong>Organización:</strong> {escape(organization_name or "No informada")}<br>
<strong>Proyecto:</strong> {escape(project_name)}<br>
<strong>Fecha:</strong> {datetime.utcnow().strftime("%d/%m/%Y")}
</p>
<div class="box">
<h2>{escape(str(result["level_label"]))}</h2>
<p><strong>{escape(str(result["headline"]))}</strong></p>
<p>{escape(str(result["summary"]))}</p>
</div>
<h2>Aspectos que conviene revisar</h2>
<ul>{items}</ul>
<h2>Siguiente paso recomendado</h2>
<p>{escape(str(result["next_step"]))}</p>
<p><small>Cuestionario {QUESTIONNAIRE_VERSION} · Reglas {RULES_VERSION}</small></p>
</body>
</html>"""
    return html.encode("utf-8")


def _payload(
    *,
    lead_id: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    organization_name: str,
    project_name: str,
    commune: str,
    region: str,
    responses: dict[str, object],
    result: dict[str, Any],
    contact_consent: bool,
) -> dict[str, object]:
    validate_public_lead_contact(
        contact_name=contact_name,
        contact_email=contact_email,
        project_name=project_name,
        contact_consent=contact_consent,
    )
    return {
        "id": lead_id,
        "source": "public_initial_diagnostic",
        "status": "new",
        "contact_name": contact_name.strip(),
        "contact_email": contact_email.strip().lower(),
        "contact_phone": contact_phone.strip(),
        "organization_name": organization_name.strip(),
        "project_name": project_name.strip(),
        "commune": commune.strip(),
        "region": region.strip(),
        "activity_type": str(responses["project_type"]),
        "surface_hectares": None,
        "objective": str(responses["main_need"]),
        "client_needs": [str(responses["main_need"])],
        "metadata": {
            "project_stage": responses["project_stage"],
            "information_level": responses["information_level"],
            "component": responses["component"],
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
    project_name = str(bundle["project_name"])
    organization_name = str(bundle.get("organization_name") or "")
    contact_name = str(bundle.get("contact_name") or "")
    report = bytes(bundle["report"])
    saved = bool(bundle.get("saved"))

    st.divider()
    st.success("Tu orientación inicial está lista.")
    st.markdown(
        f"""
        <section class="bc-readiness-card">
            <small>{escape(str(result["level_label"]))}</small>
            <h3>{escape(str(result["headline"]))}</h3>
            <p>{escape(str(result["summary"]))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.progress(int(result["score"]) / int(result["maximum_score"]), text="Preparación general para una revisión profesional")

    st.markdown("### Aspectos que conviene revisar")
    for gap in result["gaps"]:
        st.markdown(f"- {gap}")

    st.info(str(result["next_step"]))
    if saved:
        st.caption("BioCore recibió tus datos y podrá orientarte sobre el siguiente paso.")
    else:
        st.warning("El resultado se generó, pero el registro comercial no pudo guardarse. Puedes descargarlo y contactar directamente a BioCore.")

    st.download_button(
        "Descargar resumen inicial",
        data=report,
        file_name="diagnostico-inicial-" + project_name.strip().lower().replace(" ", "-") + ".html",
        mime="text/html",
        use_container_width=True,
    )

    st.markdown(
        """
        <section class="bc-paid-card">
            <h3>¿Necesitas saber exactamente qué sirve y qué falta?</h3>
            <p>
                El <strong>Diagnóstico Profesional BioCore</strong> incorpora revisión
                humana de archivos y antecedentes, identificación de brechas,
                recomendaciones priorizadas, informe profesional breve y reunión
                de explicación.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "Solicitar Diagnóstico Profesional BioCore",
        _professional_url(project_name, organization_name, contact_name),
        use_container_width=True,
    )


def render_public_ecological_diagnostic(record_lead: LeadRecorder | None = None) -> None:
    _apply_styles()
    st.markdown('<a href="?" style="text-decoration:none;font-weight:700;">← Volver a BioCore</a>', unsafe_allow_html=True)
    st.title("Diagnóstico Inicial BioCore")
    st.subheader("Descubre qué necesita tu proyecto y cuál debería ser el próximo paso")
    st.write("Responde seis preguntas simples. Recibirás una orientación automática sobre el nivel de preparación de tu proyecto.")
    st.info("Gratuito · aproximadamente 3 minutos · no requiere suscripción")
    st.warning("No identifica especies, no confirma presencia o ausencia, no evalúa impactos y no reemplaza una campaña de terreno ni una revisión profesional.", icon="⚠️")

    with st.form("public_initial_diagnostic_form_v3"):
        st.markdown("### Tus datos")
        left, right = st.columns(2)
        with left:
            contact_name = st.text_input("Nombre y apellido *")
            contact_email = st.text_input("Correo electrónico *")
            organization_name = st.text_input("Empresa u organización (opcional)")
            project_name = st.text_input("Proyecto, predio o iniciativa *")
        with right:
            contact_phone = st.text_input("Teléfono (opcional)")
            region = st.text_input("Región (opcional)")
            commune = st.text_input("Comuna (opcional)")

        st.markdown("### Seis preguntas rápidas")
        st.caption("Marca una alternativa por pregunta.")

        project_type = st.radio("1. ¿Qué tipo de proyecto o actividad tienes?", PROJECT_TYPES, index=None, key="initial_project_type_v3")
        project_stage = st.radio("2. ¿En qué etapa se encuentra?", PROJECT_STAGES, index=None, key="initial_project_stage_v3")
        information_level = st.radio("3. ¿Qué información ecológica previa tienes?", INFORMATION_LEVELS, index=None, key="initial_information_level_v3")
        main_need = st.radio("4. ¿Qué necesitas principalmente?", MAIN_NEEDS, index=None, key="initial_main_need_v3")
        component = st.radio("5. ¿Qué componentes podrían estar involucrados?", COMPONENT_OPTIONS, index=None, key="initial_component_v3")
        timeline = st.radio("6. ¿Cuándo necesitas avanzar?", TIMELINES, index=None, key="initial_timeline_v3")

        scope_accepted = st.checkbox("Comprendo que el resultado es una orientación inicial y no reemplaza una revisión profesional.")
        contact_consent = st.checkbox("Autorizo a BioCore a guardar estos antecedentes y contactarme sobre este diagnóstico.")
        submitted = st.form_submit_button("Ver mi orientación inicial", type="primary", use_container_width=True)

    if submitted:
        try:
            if not scope_accepted:
                raise PublicLeadValidationError("Debes aceptar el alcance del diagnóstico inicial.")

            missing = [label for value, label in (
                (project_type, "tipo de proyecto"),
                (project_stage, "etapa del proyecto"),
                (information_level, "información disponible"),
                (main_need, "necesidad principal"),
                (component, "componentes involucrados"),
                (timeline, "plazo"),
            ) if value is None]
            if missing:
                raise PublicLeadValidationError("Completa estas respuestas: " + ", ".join(missing) + ".")

            responses: dict[str, object] = {
                "project_type": project_type,
                "project_stage": project_stage,
                "information_level": information_level,
                "main_need": main_need,
                "component": component,
                "timeline": timeline,
            }
            result = _evaluate(responses)
            lead_id = str(uuid4())
            payload = _payload(
                lead_id=lead_id,
                contact_name=contact_name,
                contact_email=contact_email,
                contact_phone=contact_phone,
                organization_name=organization_name,
                project_name=project_name,
                commune=commune,
                region=region,
                responses=responses,
                result=result,
                contact_consent=contact_consent,
            )

            saved = False
            if record_lead is not None:
                try:
                    record_lead(payload)
                    saved = True
                except Exception:
                    saved = False

            report = _report(project_name.strip(), organization_name.strip(), result)
            st.session_state[_RESULT_KEY] = {
                "result": result,
                "project_name": project_name.strip(),
                "organization_name": organization_name.strip(),
                "contact_name": contact_name.strip(),
                "report": report,
                "saved": saved,
            }
        except PublicLeadValidationError as error:
            st.error(str(error))

    bundle = st.session_state.get(_RESULT_KEY)
    if isinstance(bundle, dict):
        _render_result(bundle)
