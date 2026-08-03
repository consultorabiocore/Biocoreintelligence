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
    {
        "internal_name": "BioCore MycoField",
        "display_name": "BioCore MycoField",
        "eyebrow": "Hongos en terreno",
        "description": (
            "Aplicación especializada para registrar hongos durante campañas de "
            "terreno, incluso cuando el trabajo ocurre lejos del escritorio."
        ),
        "features": (
            "Fotografías, coordenadas y fecha vinculadas a cada registro.",
            "Formularios consistentes para ordenar campañas micológicas.",
            "Trazabilidad desde la observación hasta su revisión posterior.",
        ),
        "note": (
            "Especializado en campañas micológicas; la identificación taxonómica "
            "definitiva requiere revisión experta cuando corresponda."
        ),
        "spotlight": True,
    },
    {
        "internal_name": "DarwinCheck",
        "display_name": "DarwinCheck",
        "eyebrow": "Planillas DwC-SMA",
        "description": (
            "Revisa planillas de biodiversidad solicitadas por la SMA bajo el "
            "formato Darwin Core adaptado para Chile (DwC-SMA)."
        ),
        "features": (
            "Detecta campos incompletos, formatos incompatibles e inconsistencias.",
            "Ayuda a revisar datos de flora, vegetación, hongos y líquenes.",
            "Entrega hallazgos explicables antes de preparar el reporte.",
        ),
        "note": (
            "Apoya el control de calidad; no certifica cumplimiento ni presenta "
            "información ante la SMA."
        ),
        "reference_url": (
            "https://portal.sma.gob.cl/index.php/portal-regulados/"
            "instructivos-y-guias/reporte-datos-biodiversidad/"
        ),
        "spotlight": True,
    },
    {
        "internal_name": "BioCore Intelligence",
        "display_name": "BioCore Intelligence",
        "eyebrow": "Vigilancia multisatelital",
        "description": (
            "Monitorea áreas de proyecto con imágenes de múltiples satélites y "
            "convierte series temporales en alertas e informes comprensibles."
        ),
        "features": (
            "Históricos descargables de NDVI, EVI y cobertura vegetal.",
            "Gráficos de cambio, temperatura superficial e indicadores de humedad.",
            "Reportes automáticos y avisos móviles para revisar cambios a tiempo.",
        ),
        "note": (
            "La frecuencia y disponibilidad dependen de las fuentes y condiciones "
            "de observación. Las alertas no predicen sanciones ni reemplazan una "
            "evaluación profesional."
        ),
        "spotlight": True,
    },
    {
        "internal_name": "BioCore Reports",
        "display_name": "BioCore Reports",
        "eyebrow": "Informes con memoria",
        "description": (
            "Reúne informes, mapas y versiones históricas conectadas con la "
            "evidencia que les dio origen."
        ),
        "features": (
            "Descarga de informes y productos históricos.",
            "Versiones y trazabilidad visibles para el equipo y el cliente.",
        ),
        "note": "Los productos disponibles dependen del proyecto y sus fuentes.",
        "spotlight": False,
    },
    {
        "internal_name": "BioCore Academy",
        "display_name": "BioCore Academy",
        "eyebrow": "Capacidad para el equipo",
        "description": (
            "Formación aplicada para interpretar datos ecológicos, usar las "
            "herramientas BioCore y trabajar con criterios consistentes."
        ),
        "features": (
            "Aprendizaje científico-tecnológico orientado al trabajo real.",
            "Recursos para profesionales, empresas y equipos de terreno.",
        ),
        "note": "La formación acompaña la tecnología y reduce dependencia operativa.",
        "spotlight": False,
    },
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
        "BioCore MycoField": BRAND.field_logo,
        "DarwinCheck": BRAND.darwincheck_logo,
        "BioCore Intelligence": BRAND.intelligence_logo,
        "BioCore Reports": BRAND.reports_logo,
        "BioCore Academy": BRAND.academy_logo,
    }
    tools = []
    for module in ECOSYSTEM_MODULES:
        internal_name = str(module["internal_name"])
        display_name = str(module["display_name"])
        url, action_label, external = destinations[internal_name]
        logo_uri = asset_data_uri(module_logos[internal_name])
        logo = (
            f'<img src="{escape(logo_uri)}" alt="Logo {escape(display_name)}">'
            if logo_uri
            else ""
        )
        target = (
            ' target="_blank" rel="noopener noreferrer"'
            if external
            else ""
        )
        features = "".join(
            f"<li>{escape(str(feature))}</li>"
            for feature in module["features"]
        )
        reference_url = module.get("reference_url")
        reference = (
            f'<a class="bc-tool-reference" href="{escape(str(reference_url))}" '
            'target="_blank" rel="noopener noreferrer">'
            "Conocer el formato oficial DwC-SMA ↗</a>"
            if reference_url
            else ""
        )
        card_class = (
            "bc-tool bc-tool-spotlight"
            if module["spotlight"]
            else "bc-tool"
        )
        tools.append(
            f"""
            <article class="{card_class}">
                {logo}
                <div>
                    <span class="bc-tool-eyebrow">{escape(str(module['eyebrow']))}</span>
                    <h3>{escape(display_name)}</h3>
                    <p>{escape(str(module['description']))}</p>
                    <ul class="bc-tool-features">{features}</ul>
                    <p class="bc-tool-note">{escape(str(module['note']))}</p>
                    <div class="bc-tool-actions">
                        <a class="bc-tool-open" href="{escape(url)}"{target}>{escape(action_label)} →</a>
                        {reference}
                    </div>
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
        "BioCore MycoField": (
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
                        <span class="bc-eyebrow">Ecosistema tecnológico propio para proyectos ecológicos</span>
                        <h1>Conecta el terreno, la calidad de datos y la vigilancia satelital</h1>
                        <p class="bc-hero-copy">
                            BioCore reúne aplicaciones propias para registrar hongos en terreno,
                            revisar planillas de biodiversidad bajo el estándar DwC-SMA y vigilar
                            proyectos con imágenes multisatelitales. Todo se conecta con análisis,
                            trazabilidad e informes en una experiencia moderna creada para
                            proyectos de flora, hongos y líquenes.
                        </p>
                        <p class="bc-hero-specialty">
                            No son herramientas aisladas: cada aplicación acompaña una etapa real
                            del proyecto y muestra qué ocurrió, qué falta y cuál es el próximo paso.
                        </p>
                        <div class="bc-hero-actions">
                            <a class="bc-button bc-button-primary" href="{escape(signup_url)}">
                                Crear proyecto
                            </a>
                            <a class="bc-button bc-button-secondary" href="#herramientas">
                                Descubrir nuestras aplicaciones
                            </a>
                        </div>
                        <p class="bc-action-note">
                            Para crear un proyecto se solicitará iniciar sesión o crear una cuenta.
                        </p>
                    </div>
                    <aside class="bc-hero-summary" aria-label="Diferencial tecnológico de BioCore">
                        <span class="bc-summary-label">El diferencial BioCore</span>
                        <h2>Aplicaciones propias. Un proyecto conectado.</h2>
                        <ul>
                            <li>MycoField: registros fúngicos georreferenciados desde terreno.</li>
                            <li>DarwinCheck: revisión de planillas de biodiversidad DwC-SMA.</li>
                            <li>Intelligence: vigilancia multisatelital e índices ecológicos históricos.</li>
                            <li>Reports y Academy: informes y formación conectados con el proyecto.</li>
                        </ul>
                        <p>
                            Un ecosistema especializado desarrollado por BioCore para reunir
                            capacidades que las plataformas ambientales generalistas suelen
                            mantener separadas.
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
                        <span class="bc-eyebrow">Lo que diferencia a BioCore</span>
                        <h2>Herramientas propias para problemas ecológicos concretos</h2>
                        <p>
                            Desde registrar un hongo en terreno y revisar una planilla DwC-SMA
                            hasta vigilar cambios con múltiples satélites: BioCore reúne capacidades
                            especializadas que normalmente quedan separadas en distintas soluciones.
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
