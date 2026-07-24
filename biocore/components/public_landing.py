from html import escape
from textwrap import dedent

import streamlit as st

from biocore.components.styles import PUBLIC_STYLES
from biocore.config.brand import BRAND, asset_data_uri


def _html(value: str) -> str:
    """Keep Markdown from interpreting indented HTML fragments as code."""
    return "\n".join(line.lstrip() for line in value.splitlines())


ECOSYSTEM_MODULES = (
    (
        "FIELD",
        "BioCore Field",
        "Captura y organización de datos directamente en terreno.",
    ),
    (
        "CHECK",
        "DarwinCheck",
        "Validación, auditoría y gobierno de calidad de datos ambientales.",
    ),
    (
        "INTELLIGENCE",
        "BioCore Intelligence",
        "Satélites, LiDAR, analítica, monitoreo y detección de cambios.",
    ),
    (
        "REPORTS",
        "BioCore Reports",
        "Informes, mapas y productos actualizados desde una fuente común.",
    ),
    (
        "ACADEMY",
        "BioCore Academy",
        "Cursos y formación científico-tecnológica para profesionales y empresas.",
    ),
)


SUBSCRIPTION_PLANS = (
    (
        "Plan BioCore Core",
        "La base para ordenar y conservar la gestión ambiental.",
        (
            "Portal privado del cliente",
            "Proyectos, áreas y campañas",
            "Repositorio de informes",
            "Dashboard e historial ambiental",
            "Diagnóstico Ecológico Digital breve",
            "Usuarios básicos",
        ),
        "Solicitar cotización",
    ),
    (
        "Plan BioCore Professional",
        "Operación integrada para equipos que gestionan más datos y campañas.",
        (
            "Todo lo incluido en Core",
            "BioCore Field y DarwinCheck",
            "Mapas interactivos",
            "Comparación de campañas",
            "Dashboards avanzados y automatizaciones",
            "Mayor almacenamiento",
        ),
        "Solicitar demostración",
    ),
    (
        "Plan BioCore Enterprise",
        "Inteligencia y personalización para operaciones ambientales complejas.",
        (
            "Todo lo incluido en Professional",
            "BioCore Intelligence",
            "Monitoreo satelital y LiDAR",
            "API e integraciones",
            "Múltiples equipos y soporte prioritario",
            "Personalización",
        ),
        "Hablar con BioCore",
    ),
)


def _module_cards() -> str:
    module_logos = {
        "BioCore Field": BRAND.field_logo,
        "DarwinCheck": BRAND.darwincheck_logo,
        "BioCore Intelligence": BRAND.intelligence_logo,
        "BioCore Reports": BRAND.reports_logo,
        "BioCore Academy": BRAND.academy_logo,
    }

    def card_media(icon: str, name: str) -> str:
        logo_path = module_logos.get(name)
        logo_uri = asset_data_uri(logo_path) if logo_path else ""
        if logo_uri:
            return (
                f'<img class="bc-module-logo" src="{escape(logo_uri)}" '
                f'alt="Logo {escape(name)}">'
            )
        return (
            f'<span class="bc-module-icon" aria-hidden="true">'
            f"{escape(icon)}</span>"
        )

    return "\n".join(
        f"""
        <article class="bc-module-card">
            {card_media(icon, name)}
            <h3>{escape(name)}</h3>
            <p>{escape(description)}</p>
            <a class="bc-text-link" href="#suscripcion">Conocer más →</a>
        </article>
        """
        for icon, name, description in ECOSYSTEM_MODULES
    )


def _ecosystem_strip() -> str:
    module_logos = (
        ("BioCore Field", BRAND.field_logo),
        ("DarwinCheck", BRAND.darwincheck_logo),
        ("BioCore Intelligence", BRAND.intelligence_logo),
        ("BioCore Reports", BRAND.reports_logo),
        ("BioCore Academy", BRAND.academy_logo),
    )
    items = []
    for name, logo_path in module_logos:
        logo_uri = asset_data_uri(logo_path)
        if not logo_uri:
            continue
        items.append(
            f"""
            <span class="bc-ecosystem-brand">
                <img src="{escape(logo_uri)}" alt="Logo {escape(name)}">
                <small>{escape(name)}</small>
            </span>
            """
        )
    return "".join(items)


def _plan_cards() -> str:
    cards = []
    for index, (name, copy, features, action_label) in enumerate(SUBSCRIPTION_PLANS):
        featured = " bc-plan-featured" if index == 1 else ""
        badge = '<span class="bc-plan-badge">Recomendado</span>' if index == 1 else ""
        items = "".join(f"<li>{escape(feature)}</li>" for feature in features)
        action_url = BRAND.demo_request_url(f"{action_label}: {name}")
        cards.append(
            f"""
            <article class="bc-plan{featured}">
                {badge}
                <small>Suscripción BioCore</small>
                <h3>{escape(name)}</h3>
                <p class="bc-plan-copy">{escape(copy)}</p>
                <ul class="bc-list">{items}</ul>
                <a class="bc-button bc-button-secondary" href="{escape(action_url)}">
                    {escape(action_label)}
                </a>
            </article>
            """
        )
    return "\n".join(cards)


def render_public_landing() -> None:
    logo_uri = asset_data_uri(BRAND.master_logo)
    demo_url = BRAND.demo_request_url()
    login_url = "?auth=login"
    diagnostic_url = "?auth=login"
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
                    <a class="bc-brand" href="#inicio">{logo}</a>
                    <div class="bc-navlinks">
                        <a href="#plataforma">Plataforma</a>
                        <a href="#soluciones">Soluciones</a>
                        <a href="#proyectos">Proyectos ambientales</a>
                        <a href="#suscripcion">Suscripción</a>
                        <a href="#recursos">Recursos</a>
                    </div>
                    <div class="bc-nav-actions">
                        <a class="bc-button bc-button-primary" href="{escape(demo_url)}">
                            Solicitar demostración
                        </a>
                        <a class="bc-button bc-button-secondary" href="{login_url}">
                            Iniciar sesión
                        </a>
                    </div>
                </div>
            </nav>

            <section class="bc-hero" id="inicio">
                <div class="bc-container bc-hero-grid">
                    <div>
                        <span class="bc-eyebrow">{escape(BRAND.descriptor)}</span>
                        <h1>Transformamos datos ambientales en decisiones inteligentes</h1>
                        <p class="bc-hero-copy">
                            Gestiona proyectos, campañas, mapas, informes y monitoreo
                            ambiental desde una plataforma científica integrada.
                        </p>
                        <p class="bc-hero-note">
                            Cada campaña aumenta el conocimiento histórico de tu territorio.
                        </p>
                        <div class="bc-hero-actions">
                            <a class="bc-button bc-button-primary" href="{escape(demo_url)}">
                                Solicitar demostración
                            </a>
                            <a class="bc-button bc-button-gold" href="#suscripcion">
                                Ver planes BioCore
                            </a>
                        </div>
                        <div class="bc-trust-row">
                            <span>Acceso privado por organización</span>
                            <span>Trazabilidad de extremo a extremo</span>
                            <span>Continuidad después del proyecto</span>
                        </div>
                    </div>

                    <div class="bc-demo-shell" aria-label="Dashboard demostrativo BioCore">
                        <div class="bc-demo-window">
                            <div class="bc-demo-topbar">
                                <span>Dashboard ambiental integrado</span>
                                <span class="bc-demo-badge">Datos demostrativos</span>
                            </div>
                            <div class="bc-demo-body">
                                <div class="bc-demo-map">
                                    <div class="bc-map-zone"></div>
                                    <div class="bc-map-legend">
                                        Área de estudio · Ejemplo<br>
                                        Comparación estacional activa
                                    </div>
                                </div>
                                <div class="bc-demo-panel">
                                    <div class="bc-demo-metric">
                                        <small>Proyectos activos</small><strong>4</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Campañas</small><strong>12</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Informes</small><strong>28</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Especies registradas</small><strong>184</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Alertas ambientales</small><strong>2</strong>
                                    </div>
                                    <div class="bc-demo-comparison">
                                        <span>Otoño</span><i></i><strong>vs.</strong><i></i><span>Verano</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="bc-container bc-hero-ecosystem">
                    <strong>Una plataforma · cinco capacidades especializadas</strong>
                    <div class="bc-ecosystem-brands">{_ecosystem_strip()}</div>
                </div>
            </section>

            <section class="bc-section" id="plataforma">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Del dato aislado al conocimiento acumulativo</span>
                        <h2>Una plataforma para conservar la historia ambiental de cada proyecto</h2>
                        <p>
                            BioCore conecta el trabajo de terreno, la validación, el análisis
                            y los productos finales en una experiencia coherente para equipos
                            técnicos y clientes.
                        </p>
                    </header>
                    <div class="bc-split">
                        <article class="bc-panel">
                            <h3>Cuando la información queda dispersa</h3>
                            <ul class="bc-list">
                                <li>Archivos y versiones difíciles de recuperar.</li>
                                <li>Campañas sin continuidad entre temporadas.</li>
                                <li>Procesamiento geoespacial manual y repetitivo.</li>
                                <li>Datos que no vuelven a utilizarse.</li>
                                <li>Poca trazabilidad entre evidencia e informe.</li>
                            </ul>
                        </article>
                        <article class="bc-panel bc-solution-panel">
                            <h3>BioCore organiza el ciclo completo</h3>
                            <ul class="bc-list">
                                <li>Una historia ambiental centralizada por organización.</li>
                                <li>Campañas, mapas e informes conectados.</li>
                                <li>Calidad y validación visibles para el equipo.</li>
                                <li>Comparaciones que reutilizan el conocimiento previo.</li>
                                <li>Acceso continuo y seguro para cada cliente.</li>
                            </ul>
                        </article>
                    </div>
                </div>
            </section>

            <section class="bc-section bc-section-soft" id="soluciones">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Ecosistema BioCore</span>
                        <h2>Capacidades especializadas, una sola plataforma</h2>
                        <p>
                            Los módulos amplían BioCore sin fragmentar cuentas, proyectos
                            ni suscripciones.
                        </p>
                    </header>
                    <div class="bc-card-grid">{_module_cards()}</div>
                </div>
            </section>

            <section class="bc-section bc-section-dark">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Cómo funciona</span>
                        <h2>Un flujo continuo desde el proyecto hasta el monitoreo</h2>
                        <p>Cada etapa conserva su contexto y alimenta la siguiente.</p>
                    </header>
                    <div class="bc-flow">
                        <div class="bc-flow-step">Proyecto</div>
                        <div class="bc-flow-step">Área de estudio</div>
                        <div class="bc-flow-step">Campaña</div>
                        <div class="bc-flow-step">Captura</div>
                        <div class="bc-flow-step">Validación</div>
                        <div class="bc-flow-step">Análisis</div>
                        <div class="bc-flow-step">Dashboard</div>
                        <div class="bc-flow-step">Informe</div>
                        <div class="bc-flow-step">Monitoreo</div>
                    </div>
                </div>
            </section>

            <section class="bc-section">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Beneficios para el cliente</span>
                        <h2>Menos tareas manuales. Más continuidad y trazabilidad.</h2>
                    </header>
                    <div class="bc-benefits-grid">
                        <article class="bc-benefit-card"><h3>Información centralizada</h3><p>Conserva datos, evidencias e informes ambientales en un solo lugar.</p></article>
                        <article class="bc-benefit-card"><h3>Historial de campañas</h3><p>Recupera el contexto técnico de cada temporada y salida a terreno.</p></article>
                        <article class="bc-benefit-card"><h3>Mapas e informes conectados</h3><p>Relaciona productos geoespaciales con sus datos de origen.</p></article>
                        <article class="bc-benefit-card"><h3>Comparación temporal</h3><p>Contrasta campañas y estaciones usando una fuente común.</p></article>
                        <article class="bc-benefit-card"><h3>Menos tareas manuales</h3><p>Reduce procesos repetitivos y concentra tiempo en el análisis.</p></article>
                        <article class="bc-benefit-card"><h3>Acceso privado</h3><p>Entrega al cliente un espacio seguro, separado por organización.</p></article>
                        <article class="bc-benefit-card"><h3>Trazabilidad</h3><p>Sigue el recorrido de la captura al producto final.</p></article>
                        <article class="bc-benefit-card"><h3>Continuidad</h3><p>El conocimiento permanece disponible después de la entrega.</p></article>
                    </div>
                </div>
            </section>

            <section class="bc-section bc-section-dark" id="diagnostico">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Nuevo servicio digital</span>
                        <h2>Diagnóstico Ecológico Digital BioCore</h2>
                        <p>
                            Evaluación preliminar de información sobre flora,
                            vegetación, hongos y líquenes.
                        </p>
                    </header>
                    <div class="bc-split">
                        <article class="bc-panel">
                            <h3>Conoce el estado de tus antecedentes</h3>
                            <p>
                                Identifica cobertura documental, espacial, temporal
                                y taxonómica; calidad, trazabilidad y preparación
                                para mapas o comparación de campañas.
                            </p>
                            <a class="bc-button bc-button-gold" href="{diagnostic_url}">
                                Realizar diagnóstico ecológico
                            </a>
                        </article>
                        <article class="bc-panel bc-solution-panel">
                            <h3>Resultado explicable y versionado</h3>
                            <p>
                                Recibe brechas y recomendaciones relacionadas
                                únicamente con servicios ecológicos actuales de
                                BioCore, con opción de solicitar revisión profesional.
                            </p>
                            <small>
                                Orientación preliminar. No reemplaza una campaña de
                                terreno, una línea de base ni una revisión profesional.
                            </small>
                        </article>
                    </div>
                </div>
            </section>

            <section class="bc-section bc-section-soft" id="suscripcion">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Suscripción a la plataforma BioCore</span>
                        <h2>Un plan principal, módulos que crecen con tu operación</h2>
                        <p>
                            Cada organización contrata BioCore como plataforma general.
                            Los módulos especializados pueden activarse como complementos.
                        </p>
                    </header>
                    <div class="bc-plans">{_plan_cards()}</div>
                    <div class="bc-addons" aria-label="Complementos disponibles">
                        <span class="bc-addon">LiDAR</span>
                        <span class="bc-addon">Monitoreo satelital</span>
                        <span class="bc-addon">Almacenamiento adicional</span>
                        <span class="bc-addon">Usuarios adicionales</span>
                        <span class="bc-addon">Acceso API</span>
                        <span class="bc-addon">Capacitación</span>
                        <span class="bc-addon">Procesamiento geoespacial especializado</span>
                    </div>
                </div>
            </section>

            <section class="bc-section" id="proyectos">
                <div class="bc-container bc-continuity">
                    <div>
                        <span class="bc-eyebrow">Proyectos más plataforma</span>
                        <h2>Un proyecto ambiental que continúa generando valor</h2>
                        <p>
                            Cuando BioCore ejecuta una línea de base, monitoreo u otro servicio,
                            el cliente puede recibir acceso privado a la plataforma durante el
                            proyecto. Sus campañas, mapas, informes y evidencias quedan
                            organizados para futuras consultas y comparaciones.
                        </p>
                        <a class="bc-button bc-button-secondary" href="{escape(demo_url)}">
                            Hablar con BioCore
                        </a>
                    </div>
                    <div class="bc-continuity-flow">
                        <div class="bc-continuity-step">01 · Proyecto adjudicado</div>
                        <div class="bc-continuity-step">02 · Acceso a BioCore</div>
                        <div class="bc-continuity-step">03 · Campañas organizadas</div>
                        <div class="bc-continuity-step">04 · Informe publicado</div>
                        <div class="bc-continuity-step">05 · Monitoreo posterior</div>
                        <div class="bc-continuity-step">06 · Suscripción de continuidad</div>
                    </div>
                </div>
            </section>

            <section class="bc-section bc-section-soft" id="recursos">
                <div class="bc-container">
                    <header class="bc-section-head">
                        <span class="bc-eyebrow">Continuidad de la información</span>
                        <h2>Conserva el conocimiento construido por tu organización</h2>
                        <p>
                            Al finalizar un acceso incluido por proyecto, BioCore mantiene
                            los datos bajo la política acordada y ofrece una ruta de
                            continuidad sin pagos automáticos.
                        </p>
                    </header>
                </div>
            </section>

            <section class="bc-final">
                <div class="bc-container">
                    <h2>Convierte cada campaña ambiental en conocimiento acumulativo</h2>
                    <p>
                        Descubre cómo BioCore puede ordenar la operación ambiental,
                        conservar su historia y ampliar sus capacidades de análisis.
                    </p>
                    <div class="bc-final-actions">
                        <a class="bc-button bc-button-gold" href="{escape(demo_url)}">
                            Solicitar una demostración
                        </a>
                        <a class="bc-button bc-button-secondary" href="{diagnostic_url}">
                            Realizar diagnóstico ecológico
                        </a>
                        <a class="bc-button bc-button-secondary" href="{login_url}">
                            Iniciar sesión
                        </a>
                    </div>
                </div>
            </section>

            <footer class="bc-footer">
                <div class="bc-container">
                    <div class="bc-footer-grid">
                        <div>
                            {logo}
                            <p>{escape(BRAND.slogan)}.</p>
                        </div>
                        <div>
                            <h4>Soluciones</h4>
                            <div class="bc-footer-links">
                                <a href="#soluciones">Ecosistema BioCore</a>
                                <a href="#suscripcion">Planes</a>
                                <a href="{escape(demo_url)}">Contacto comercial</a>
                            </div>
                        </div>
                        <div>
                            <h4>Recursos</h4>
                            <div class="bc-footer-links">
                                <a href="#plataforma">Plataforma</a>
                                <a href="#recursos">Continuidad</a>
                                <a href="{login_url}">Acceso de clientes</a>
                            </div>
                        </div>
                        <div>
                            <h4>Legal</h4>
                            <div class="bc-footer-links">
                                <a href="#privacidad">Privacidad</a>
                                <a href="#terminos">Términos</a>
                                <a href="{login_url}">Iniciar sesión</a>
                            </div>
                        </div>
                    </div>
                    <div class="bc-footer-bottom">
                        © 2026 BioCore · {escape(BRAND.descriptor)}
                    </div>
                </div>
            </footer>
        </main>
                """
            )
        ),
        unsafe_allow_html=True,
    )
