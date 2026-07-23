import base64
from html import escape
from pathlib import Path

import streamlit as st

from biocore.components.styles import PUBLIC_STYLES
from biocore.config.brand import BRAND


ECOSYSTEM_MODULES = (
    (
        "⌖",
        "BioCore Field",
        "Captura y organización de datos de terreno con continuidad desde la campaña.",
    ),
    (
        "✓",
        "DarwinCheck",
        "Validación y gobierno de calidad para datos ambientales trazables.",
    ),
    (
        "◫",
        "BioCore Intelligence",
        "Analítica, satélites, LiDAR, drones y monitoreo especializado.",
    ),
    (
        "▤",
        "BioCore Reports",
        "Informes, mapas y productos conectados directamente con los datos.",
    ),
    (
        "◇",
        "BioCore Academy",
        "Cursos, capacitación y recursos para fortalecer equipos profesionales.",
    ),
)


SUBSCRIPTION_PLANS = (
    (
        "Plan BioCore Core",
        "La base para ordenar y conservar la gestión ambiental.",
        (
            "Proyectos y áreas de estudio",
            "Campañas e historial ambiental",
            "Portal privado del cliente",
            "Informes y dashboard básico",
        ),
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
        ),
    ),
)


def _asset_data_uri(path: Path) -> str:
    if not path.is_file():
        return ""
    suffix = path.suffix.lower()
    media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _module_cards() -> str:
    module_logos = {
        "BioCore Field": BRAND.field_logo,
        "BioCore Reports": BRAND.reports_logo,
        "BioCore Academy": BRAND.academy_logo,
    }

    def card_media(icon: str, name: str) -> str:
        logo_path = module_logos.get(name)
        logo_uri = _asset_data_uri(logo_path) if logo_path else ""
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


def _plan_cards(demo_url: str) -> str:
    cards = []
    for index, (name, copy, features) in enumerate(SUBSCRIPTION_PLANS):
        featured = " bc-plan-featured" if index == 1 else ""
        badge = '<span class="bc-plan-badge">Más elegido</span>' if index == 1 else ""
        items = "".join(f"<li>{escape(feature)}</li>" for feature in features)
        cards.append(
            f"""
            <article class="bc-plan{featured}">
                {badge}
                <small>Suscripción BioCore</small>
                <h3>{escape(name)}</h3>
                <p class="bc-plan-copy">{escape(copy)}</p>
                <ul class="bc-list">{items}</ul>
                <a class="bc-button bc-button-secondary" href="{escape(demo_url)}">
                    Solicitar cotización
                </a>
            </article>
            """
        )
    return "\n".join(cards)


def render_public_landing() -> None:
    logo_uri = _asset_data_uri(BRAND.master_logo)
    demo_url = BRAND.demo_request_url()
    login_url = "?auth=login"
    logo = (
        f'<img src="{escape(logo_uri)}" alt="{escape(BRAND.name)}">'
        if logo_uri
        else f"<strong>{escape(BRAND.name)}</strong>"
    )

    st.markdown(PUBLIC_STYLES, unsafe_allow_html=True)
    st.markdown(
        f"""
        <main class="bc-public">
            <nav class="bc-navbar" aria-label="Navegación principal">
                <div class="bc-container bc-navbar-inner">
                    <a class="bc-brand" href="#inicio">{logo}</a>
                    <div class="bc-navlinks">
                        <a href="#inicio">Inicio</a>
                        <a href="#plataforma">Plataforma</a>
                        <a href="#soluciones">Soluciones</a>
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
                        <div class="bc-hero-actions">
                            <a class="bc-button bc-button-primary" href="{escape(demo_url)}">
                                Solicitar demostración
                            </a>
                            <a class="bc-button bc-button-gold" href="#plataforma">
                                Conocer la plataforma
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
                                        <small>Campañas</small><strong>12</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Informes</small><strong>8</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Riqueza de especies</small><strong>147</strong>
                                    </div>
                                    <div class="bc-demo-metric">
                                        <small>Alertas en revisión</small><strong>3</strong>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
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
                        <article class="bc-benefit-card"><h3>Historial centralizado</h3><p>Conserva campañas, evidencia e informes en un solo lugar.</p></article>
                        <article class="bc-benefit-card"><h3>Comparación temporal</h3><p>Contrasta campañas y temporadas con el mismo contexto.</p></article>
                        <article class="bc-benefit-card"><h3>Acceso privado</h3><p>Organizaciones y roles mantienen la información separada.</p></article>
                        <article class="bc-benefit-card"><h3>Mapas interactivos</h3><p>Explora áreas, capas y resultados geoespaciales conectados.</p></article>
                        <article class="bc-benefit-card"><h3>Informes versionados</h3><p>Recupera productos y su relación con los datos de origen.</p></article>
                        <article class="bc-benefit-card"><h3>Automatización</h3><p>Reduce tareas repetitivas y concentra tiempo en el análisis.</p></article>
                        <article class="bc-benefit-card"><h3>Trazabilidad</h3><p>Sigue el recorrido de la captura al producto final.</p></article>
                        <article class="bc-benefit-card"><h3>Continuidad</h3><p>El conocimiento permanece disponible después de la entrega.</p></article>
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
                    <div class="bc-plans">{_plan_cards(demo_url)}</div>
                    <div class="bc-addons" aria-label="Complementos disponibles">
                        <span class="bc-addon">LiDAR</span>
                        <span class="bc-addon">Monitoreo satelital</span>
                        <span class="bc-addon">Almacenamiento ampliado</span>
                        <span class="bc-addon">Usuarios adicionales</span>
                        <span class="bc-addon">API</span>
                        <span class="bc-addon">Capacitaciones</span>
                        <span class="bc-addon">Procesamiento especializado</span>
                    </div>
                </div>
            </section>

            <section class="bc-section" id="recursos">
                <div class="bc-container bc-continuity">
                    <div>
                        <span class="bc-eyebrow">Proyectos más plataforma</span>
                        <h2>El valor del proyecto continúa después de la entrega</h2>
                        <p>
                            Los proyectos ambientales pueden incluir acceso a BioCore durante
                            su ejecución. Después de la entrega, el cliente puede conservar
                            su historial, dashboards e informes mediante una suscripción de
                            continuidad.
                        </p>
                        <a class="bc-button bc-button-secondary" href="{escape(demo_url)}">
                            Hablar con BioCore
                        </a>
                    </div>
                    <div class="bc-continuity-flow">
                        <div class="bc-continuity-step">01 · Proyecto ganado</div>
                        <div class="bc-continuity-step">02 · Plataforma activa</div>
                        <div class="bc-continuity-step">03 · Campañas organizadas</div>
                        <div class="bc-continuity-step">04 · Informes publicados</div>
                        <div class="bc-continuity-step">05 · Monitoreo</div>
                        <div class="bc-continuity-step">06 · Renovación</div>
                    </div>
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
        """,
        unsafe_allow_html=True,
    )
