from html import escape
from textwrap import dedent

import streamlit as st

from biocore.components.public_styles import PUBLIC_STYLES
from biocore.config.brand import BRAND, asset_data_uri
from biocore.config.integrations import external_applications
from biocore.config.settings import Settings


def _html(value: str) -> str:
    """Keep Markdown from interpreting indented HTML fragments as code."""
    return "\n".join(line.lstrip() for line in value.splitlines())


PROJECT_STAGES = (
    ("01", "Proyecto", "Define el objetivo, el equipo y el alcance ecológico."),
    ("02", "Área de estudio", "Organiza el territorio, la cartografía y los sitios."),
    ("03", "Campaña de terreno", "Planifica fechas, responsables y actividades."),
    ("04", "Captura", "Reúne registros, fotografías y coordenadas."),
    ("05", "Validación", "Revisa calidad, completitud y trazabilidad."),
    ("06", "Análisis", "Interpreta datos y prepara productos geoespaciales."),
    ("07", "Informe", "Conecta conclusiones con su evidencia de origen."),
)


AUDIENCES = (
    "Consultoras ambientales",
    "Universidades e investigadores",
    "Empresas y gerencias ambientales",
    "Organismos públicos",
    "ONG y equipos de conservación",
    "Especialistas y equipos de terreno",
)


SERVICE_OUTCOMES = (
    (
        "Planificar con claridad",
        "Ordena el proyecto, el área de estudio, las campañas y las responsabilidades antes de salir a terreno.",
    ),
    (
        "Conservar evidencia útil",
        "Relaciona registros de flora, vegetación, hongos y líquenes con fotografías, fechas y ubicación.",
    ),
    (
        "Llegar al informe con trazabilidad",
        "Mantén conectados los datos observados, las validaciones, los análisis, los mapas y sus versiones.",
    ),
)


ECOSYSTEM_MODULES = (
    (
        "BioCore Field",
        "Captura de observaciones, fotografías y datos georreferenciados de terreno.",
    ),
    (
        "DarwinCheck",
        "Validación y revisión de consistencia de conjuntos de datos Darwin Core.",
    ),
    (
        "BioCore Intelligence",
        "Análisis ecológico y herramientas científicas especializadas.",
    ),
    (
        "BioCore Reports",
        "Informes y productos conectados con la evidencia y sus versiones.",
    ),
    (
        "BioCore Academy",
        "Formación científico-tecnológica para equipos y profesionales.",
    ),
)


def _project_stages() -> str:
    return "".join(
        f"""
        <li class="bc-stage">
            <span>{escape(number)}</span>
            <div>
                <h3>{escape(title)}</h3>
                <p>{escape(description)}</p>
            </div>
        </li>
        """
        for number, title, description in PROJECT_STAGES
    )


def _audience_list() -> str:
    return "".join(
        f'<li><span aria-hidden="true">✓</span>{escape(audience)}</li>'
        for audience in AUDIENCES
    )


def _service_outcomes() -> str:
    return "".join(
        f"""
        <article class="bc-outcome">
            <h3>{escape(title)}</h3>
            <p>{escape(description)}</p>
        </article>
        """
        for title, description in SERVICE_OUTCOMES
    )


def _module_tools(
    destinations: dict[str, tuple[str, str, bool]],
) -> str:
    module_logos = {
        "BioCore Field": BRAND.field_logo,
        "DarwinCheck": BRAND.darwincheck_logo,
        "BioCore Intelligence": BRAND.intelligence_logo,
        "BioCore Reports": BRAND.reports_logo,
        "BioCore Academy": BRAND.academy_logo,
    }
    tools = []
    for name, description in ECOSYSTEM_MODULES:
        url, action_label, external = destinations[name]
        logo_uri = asset_data_uri(module_logos[name])
        logo = (
            f'<img src="{escape(logo_uri)}" alt="Logo {escape(name)}">'
            if logo_uri
            else ""
        )
        target = (
            ' target="_blank" rel="noopener noreferrer"'
            if external
            else ""
        )
        tools.append(
            f"""
            <article class="bc-tool">
                {logo}
                <div>
                    <h3>{escape(name)}</h3>
                    <p>{escape(description)}</p>
                    <a href="{escape(url)}"{target}>{escape(action_label)} →</a>
                </div>
            </article>
            """
        )
    return "".join(tools)


def render_public_landing() -> None:
    settings = Settings.from_environment()
    login_url = settings.auth_login_url or "?auth=login"
    signup_url = (
        f"{settings.auth_login_url}"
        f"{'&' if '?' in settings.auth_login_url else '?'}mode=signup"
        if settings.auth_login_url
        else "?auth=login"
    )
    diagnostic_url = "?diagnostico=publico"
    demo_url = BRAND.demo_request_url(
        "Servicios profesionales y demostración de BioCore"
    )
    applications = external_applications(settings)
    module_destinations = {
        "BioCore Field": (
            applications["field"].url or login_url,
            "Abrir aplicación" if applications["field"].url else "Iniciar sesión",
            bool(applications["field"].url),
        ),
        "DarwinCheck": (
            applications["darwincheck"].url or login_url,
            (
                "Abrir aplicación"
                if applications["darwincheck"].url
                else "Iniciar sesión"
            ),
            bool(applications["darwincheck"].url),
        ),
        "BioCore Intelligence": (
            applications["intelligence"].url or login_url,
            (
                "Abrir aplicación"
                if applications["intelligence"].url
                else "Iniciar sesión"
            ),
            bool(applications["intelligence"].url),
        ),
        "BioCore Reports": (login_url, "Acceder al módulo", False),
        "BioCore Academy": (login_url, "Acceder al módulo", False),
    }
    logo_uri = asset_data_uri(BRAND.compact_logo)
    logo = (
        f'<img src="{escape(logo_uri)}" alt="{escape(BRAND.name)}">'
        if logo_uri
        else f"<strong>{escape(BRAND.name)}</strong>"
    )

    st.markdown(PUBLIC_STYLES, unsafe_allow_html=True)
    st.markdown(
        _html(
            dedent(
                f"""
        <main class="bc-public">
            <nav class="bc-navbar" aria-label="Navegación principal">
                <div class="bc-container bc-navbar-inner">
                    <a class="bc-brand" href="#inicio" aria-label="Ir al inicio de BioCore">{logo}</a>
                    <div class="bc-navlinks">
                        <a href="#solucion">Qué resuelve</a>
                        <a href="#proceso">Cómo funciona</a>
                        <a href="#para-quien">Para quién</a>
                        <a href="#herramientas">Herramientas</a>
                    </div>
                    <div class="bc-nav-actions">
                        <a class="bc-button bc-button-secondary" href="{escape(login_url)}">
                            Iniciar sesión
                        </a>
                        <a class="bc-button bc-button-primary" href="{escape(signup_url)}">
                            Crear proyecto
                        </a>
                    </div>
                </div>
            </nav>

            <section class="bc-hero" id="inicio">
                <div class="bc-container bc-hero-grid">
                    <div class="bc-hero-copy-block">
                        <span class="bc-eyebrow">Plataforma para proyectos ecológicos</span>
                        <h1>Gestiona proyectos de flora, hongos y líquenes en un solo lugar</h1>
                        <p class="bc-hero-copy">
                            BioCore combina acompañamiento profesional especializado y una
                            plataforma digital para organizar el trabajo de terreno, la
                            validación, el análisis y los informes.
                        </p>
                        <p class="bc-hero-specialty">
                            Especialistas en flora vascular, vegetación y cobertura vegetal,
                            hongos y líquenes.
                        </p>
                        <div class="bc-hero-actions">
                            <a class="bc-button bc-button-primary" href="{escape(signup_url)}">
                                Crear proyecto
                            </a>
                            <a class="bc-button bc-button-secondary" href="#servicios">
                                Ver servicios
                            </a>
                        </div>
                        <p class="bc-action-note">
                            Para crear un proyecto se solicitará iniciar sesión o crear una cuenta.
                        </p>
                    </div>
                    <aside class="bc-hero-summary" aria-label="Qué reúne BioCore">
                        <span class="bc-summary-label">Consultoría ecológica + plataforma digital</span>
                        <h2>Del objetivo del proyecto al informe final</h2>
                        <ul>
                            <li>Un espacio privado por organización.</li>
                            <li>Datos, fotografías y cartografía conectados.</li>
                            <li>Calidad y trazabilidad visibles.</li>
                            <li>Resultados explicados con sus límites.</li>
                        </ul>
                        <p>
                            La plataforma organiza la información. Las conclusiones profesionales
                            requieren revisión de especialistas cuando corresponda.
                        </p>
                    </aside>
                </div>
            </section>

            <section class="bc-scope" aria-label="Alcance ecológico de BioCore">
                <div class="bc-container bc-scope-inner">
                    <strong>Alcance principal</strong>
                    <span>Flora vascular</span>
                    <span>Vegetación y cobertura</span>
                    <span>Hongos</span>
                    <span>Líquenes</span>
                    <span>Datos georreferenciados</span>
                </div>
            </section>

            <section class="bc-section" id="solucion">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Qué problema resuelve</span>
                        <h2>Menos archivos dispersos. Más claridad para decidir y continuar.</h2>
                        <p>
                            BioCore conserva la historia ecológica del proyecto y muestra
                            qué información existe, qué falta y cuál es el siguiente paso.
                        </p>
                    </header>
                    <div class="bc-outcomes">{_service_outcomes()}</div>
                </div>
            </section>

            <section class="bc-section bc-section-soft" id="proceso">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Cómo funciona</span>
                        <h2>Siete etapas que siguen la forma real de trabajar</h2>
                        <p>
                            Comienza por el proyecto. Cada etapa conserva el contexto necesario
                            para comprender la siguiente.
                        </p>
                    </header>
                    <ol class="bc-project-flow">{_project_stages()}</ol>
                </div>
            </section>

            <section class="bc-section" id="para-quien">
                <div class="bc-container bc-audience-layout">
                    <div>
                        <span class="bc-eyebrow">Para quién está diseñado</span>
                        <h2>Para equipos que necesitan comprender y gestionar evidencia ecológica</h2>
                        <p>
                            No necesitas conocer la arquitectura del software. BioCore organiza
                            la experiencia alrededor del proyecto y de las decisiones de tu equipo.
                        </p>
                    </div>
                    <ul class="bc-audience-list">{_audience_list()}</ul>
                </div>
            </section>

            <section class="bc-section bc-section-dark" id="servicios">
                <div class="bc-container bc-service-layout">
                    <div>
                        <span class="bc-eyebrow">Servicios y acompañamiento</span>
                        <h2>Apoyo profesional cuando el proyecto necesita criterio especializado</h2>
                        <p>
                            BioCore puede acompañar la planificación, campañas de terreno,
                            revisión de calidad, preparación geoespacial, comparación de campañas
                            e informes ecológicos dentro de su alcance técnico actual.
                        </p>
                    </div>
                    <div class="bc-service-actions">
                        <a class="bc-button bc-button-gold" href="{escape(demo_url)}">
                            Consultar por un servicio
                        </a>
                        <small>
                            Se abrirá un correo prellenado al equipo BioCore. No realiza cobros
                            ni activa una suscripción.
                        </small>
                    </div>
                </div>
            </section>

            <section class="bc-section bc-section-soft" id="herramientas">
                <div class="bc-container">
                    <header class="bc-section-head bc-section-head-left">
                        <span class="bc-eyebrow">Herramientas que acompañan el trabajo</span>
                        <h2>Los módulos aparecen después del objetivo del proyecto</h2>
                        <p>
                            Cada herramienta resuelve una tarea específica. No necesitas elegir
                            un módulo antes de saber qué quieres lograr.
                        </p>
                    </header>
                    <div class="bc-tools">{_module_tools(module_destinations)}</div>
                </div>
            </section>

            <section class="bc-section" id="diagnostico">
                <div class="bc-container bc-diagnostic">
                    <div>
                        <span class="bc-eyebrow">¿No sabes por dónde comenzar?</span>
                        <h2>Realiza un diagnóstico ecológico gratuito</h2>
                        <p>
                            Revisa de forma preliminar la completitud, cobertura, calidad y
                            trazabilidad de información sobre flora, vegetación, hongos y líquenes.
                        </p>
                        <p class="bc-disclaimer">
                            El resultado es una orientación preliminar: no confirma especies,
                            no reemplaza una campaña de terreno ni constituye una revisión profesional.
                        </p>
                    </div>
                    <a class="bc-button bc-button-primary" href="{escape(diagnostic_url)}">
                        Realizar diagnóstico ecológico
                    </a>
                </div>
            </section>

            <section class="bc-section bc-section-soft" id="acceso">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Tu siguiente paso</span>
                        <h2>Entra a tus proyectos o comienza uno nuevo</h2>
                    </header>
                    <div class="bc-next-actions">
                        <article>
                            <h3>¿Ya trabajas con BioCore?</h3>
                            <p>Accede al espacio privado de tu organización y continúa donde quedaste.</p>
                            <a class="bc-button bc-button-secondary" href="{escape(login_url)}">
                                Iniciar sesión
                            </a>
                        </article>
                        <article>
                            <h3>¿Es tu primera vez?</h3>
                            <p>Crea una cuenta para iniciar un proyecto o solicita orientación del equipo.</p>
                            <div class="bc-inline-actions">
                                <a class="bc-button bc-button-primary" href="{escape(signup_url)}">
                                    Crear cuenta
                                </a>
                                <a class="bc-text-link" href="{escape(demo_url)}">
                                    Hablar con BioCore →
                                </a>
                            </div>
                        </article>
                    </div>
                </div>
            </section>

            <footer class="bc-footer">
                <div class="bc-container bc-footer-inner">
                    <div>{logo}</div>
                    <p>
                        Plataforma para proyectos ecológicos especializada en flora,
                        vegetación, hongos y líquenes.
                    </p>
                    <div class="bc-footer-links">
                        <a href="{escape(diagnostic_url)}">Diagnóstico ecológico</a>
                        <a href="{escape(demo_url)}">Contacto</a>
                        <a href="{escape(login_url)}">Acceso de clientes</a>
                    </div>
                </div>
                <div class="bc-container bc-footer-bottom">
                    © 2026 BioCore · {escape(BRAND.descriptor)}
                </div>
            </footer>
        </main>
                """
            )
        ),
        unsafe_allow_html=True,
    )
