from pathlib import Path
from datetime import datetime

from biocore.domain.dashboard import DashboardSnapshot
from biocore.domain.projects import Project, ProjectModality, ProjectStatus
from biocore.domain.subscriptions import SubscriptionSnapshot
from biocore.services.dashboard import DashboardService


def test_dashboard_uses_structured_empty_states_without_fake_private_data() -> None:
    subscription = SubscriptionSnapshot.unconfigured("org-a", "Organización A")
    dashboard = DashboardService().build(subscription)
    assert dashboard == DashboardSnapshot()
    assert dashboard.activities == ()
    assert dashboard.recent_projects == ()
    assert dashboard.upcoming_campaign_items == ()
    assert dashboard.recent_reports == ()


def test_public_and_private_routing_remain_separated() -> None:
    entrypoint = Path("biocore_app.py").read_text(encoding="utf-8")
    public_route = entrypoint.index('getattr(st.user, "is_logged_in", False)')
    public_render = entrypoint.index(
        "render_public_landing_with_diagnostic_cta()", public_route
    )
    private_shell = entrypoint.index("render_private_shell(", public_render)
    navigation = entrypoint.index("st.navigation(navigation).run()", private_shell)
    assert public_route < public_render < private_shell < navigation


def test_legacy_cloud_entrypoint_delegates_to_professional_platform() -> None:
    entrypoint = Path("app.py").read_text(encoding="utf-8")
    delegate = entrypoint.index("runpy.run_path(")
    platform_path = entrypoint.index('"biocore_app.py"', delegate)
    stop = entrypoint.index("st.stop()", delegate)
    legacy_config = entrypoint.index(
        'st.set_page_config(page_title="Biocore Intelligence"', stop
    )
    assert delegate < platform_path < stop < legacy_config


def test_public_landing_states_scope_without_a_fake_dashboard() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    assert "Consultoría ambiental especializada en flora, hongos y líquenes" in landing
    assert "Aplicaciones propias. Un proyecto conectado." in landing
    assert "Para quién está diseñado" in landing
    assert "Realizar diagnóstico ecológico" in landing
    assert "Datos demostrativos" not in landing
    assert "bc-demo-shell" not in landing


def test_public_and_private_homepages_orient_people_before_modules() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    dashboard = Path("biocore/components/dashboard.py").read_text(
        encoding="utf-8"
    )

    assert "Siete etapas que siguen la forma real de trabajar" in landing
    assert "Herramientas propias para problemas ecológicos concretos" in landing
    assert "Dashboard demostrativo" not in landing
    assert "Tus proyectos ecológicos" in dashboard
    assert "Siguiente acción recomendada" in dashboard
    assert 'st.subheader("Mis proyectos")' in dashboard
    assert "bc-dashboard-module-logo" in dashboard


def test_dashboard_exposes_real_project_context_and_next_action() -> None:
    subscription = SubscriptionSnapshot.unconfigured("org-a", "Organización A")
    now = datetime(2026, 7, 31, 10, 30)
    project = Project(
        id="project-1",
        organization_id="org-a",
        name="Bosque costero",
        code="BIO-001",
        client_name="Cliente A",
        project_type="Caracterización ecológica",
        region="Los Lagos",
        commune="Puerto Montt",
        modality=ProjectModality.MIXED,
        description="Descripción",
        objective="Objetivo",
        status=ProjectStatus.ACTIVE,
        start_date=None,
        current_stage="Campaña de terreno",
        progress_percent=35,
        responsible_name="Especialista BioCore",
        next_activity="Validar fotografías",
        next_activity_date=None,
        created_by_user_id="user-1",
        updated_by_user_id="user-1",
        created_at=now,
        updated_at=now,
    )

    dashboard = DashboardService().build(subscription, projects=(project,))

    assert dashboard.projects_loaded is True
    assert dashboard.active_projects == 1
    assert dashboard.recent_projects[0].name == "Bosque costero"
    assert dashboard.recent_projects[0].current_stage == "Campaña de terreno"
    assert dashboard.recent_projects[0].next_activity == "Validar fotografías"


def test_public_landing_uses_compact_logo_and_real_module_destinations() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    assert "asset_data_uri(BRAND.compact_logo)" in landing
    assert "external_applications(settings)" in landing
    assert "Abrir aplicación" in landing
    assert "Acceder al módulo" in landing
    assert 'diagnostic_url = "?diagnostico=publico"' in landing
    assert "No realiza cobros" in landing
    assert "ni activa una suscripción" in landing


def test_public_darwincheck_entry_uses_the_native_protected_page() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    darwincheck_destination = landing.split('"DarwinCheck": (', 1)[1].split(
        '"BioCore Intelligence":', 1
    )[0]
    entrypoint = Path("biocore_app.py").read_text(encoding="utf-8")

    assert "darwincheck_login_url" in darwincheck_destination
    assert 'applications["darwincheck"]' not in darwincheck_destination
    assert "Abrir en BioCore" in darwincheck_destination
    assert '"darwincheck": "DarwinCheck"' in entrypoint
    assert 'st.session_state["biocore_post_login_page"]' in entrypoint
    assert "requested_default_page in available_page_titles" in entrypoint


def test_public_landing_explains_each_specialized_product_value() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )

    for value_statement in (
        "BioCore MycoField",
        "Hongos en terreno",
        "planillas de biodiversidad solicitadas por la SMA",
        "DwC-SMA",
        "no certifica cumplimiento",
        "Vigilancia multisatelital",
        "NDVI, EVI y cobertura vegetal",
        "temperatura superficial e indicadores de humedad",
        "Reportes automáticos y avisos móviles",
        "no predicen sanciones",
        "Informes con memoria",
        "Capacidad para el equipo",
    ):
        assert value_statement in landing

    assert "evitar multas" not in landing.lower()


def test_public_hero_leads_with_concrete_biocore_differentiators() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )

    for hero_statement in (
        "Consultoría ambiental + tecnología propia",
        "acompañamiento profesional especializado y aplicaciones",
        "organizar el trabajo de terreno, la validación, el monitoreo",
        "Desde la planificación hasta el informe final",
        "Descubrir nuestras aplicaciones",
        "Aplicaciones propias. Un proyecto conectado.",
        "plataformas ambientales generalistas",
    ):
        assert hero_statement in landing

    assert "nadie más" not in landing.lower()


def test_private_module_cards_open_the_protected_module_pages() -> None:
    dashboard = Path("biocore/components/dashboard.py").read_text(
        encoding="utf-8"
    )
    for path in (
        'ModuleCode.FIELD: "/field"',
        'ModuleCode.DARWINCHECK: "/darwincheck"',
        'ModuleCode.INTELLIGENCE: "/intelligence"',
        'ModuleCode.REPORTS: "/biocore_reports"',
        'ModuleCode.ACADEMY: "/academy"',
    ):
        assert path in dashboard
    assert "Abrir módulo →" in dashboard
