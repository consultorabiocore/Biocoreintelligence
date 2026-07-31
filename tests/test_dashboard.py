from pathlib import Path

from biocore.domain.dashboard import DashboardSnapshot
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


def test_public_landing_marks_demo_data_explicitly() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    assert "Datos demostrativos" in landing
    assert "Realizar diagnóstico ecológico" in landing
    assert "184" in landing


def test_public_and_private_homepages_show_the_module_brand_system() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    dashboard = Path("biocore/components/dashboard.py").read_text(
        encoding="utf-8"
    )

    assert "_ecosystem_strip()" in landing
    assert "Ver planes BioCore" in landing
    assert "bc-dashboard-module-logo" in dashboard
    assert "Solicitar activación de BioCore" in dashboard


def test_public_landing_uses_compact_logo_and_real_module_destinations() -> None:
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    assert "asset_data_uri(BRAND.compact_logo)" in landing
    assert "external_applications(settings)" in landing
    assert "Abrir aplicación" in landing
    assert "Acceder al módulo" in landing
    assert 'diagnostic_url = "?diagnostico=publico"' in landing
    assert "No realiza cobros ni activa una suscripción" in landing


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
