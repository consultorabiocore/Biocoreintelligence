from pathlib import Path


def test_intelligence_page_runs_inside_biocore() -> None:
    source = Path("platform_pages/intelligence.py").read_text(encoding="utf-8")

    assert 'st.session_state.get("biocore_intelligence_service")' in source
    assert 'st.session_state.get("biocore_project_service")' in source
    assert "service.run(" in source
    assert "service.list_runs(" in source
    assert "Sentinel-2" in source
    assert "Copernicus" in source
    assert "st.download_button(" in source
    assert "Dibujar en el mapa" in source
    assert "Informe ejecutivo" in source
    assert "Informe técnico completo" in source
    assert '["Vigilar", "Informes", "Historial", "Guía"]' in source
    assert "build_intelligence_pdf" in source
    assert "render_module_integration" not in source
    assert "streamlit.app" not in source
    assert "cumplimiento" in source


def test_intelligence_page_never_presents_synthetic_monitoring() -> None:
    source = Path("platform_pages/intelligence.py").read_text(encoding="utf-8")

    assert "preview_demo" not in source
    assert "MODO DEMOSTRACIÓN" not in source
    assert "datos sintéticos" not in source
    assert "No necesitas activar una prueba de Google Cloud" in source


def test_intelligence_migration_is_tenant_scoped_and_immutable() -> None:
    source = Path("database/migrations/0012_native_intelligence.sql").read_text(
        encoding="utf-8"
    )

    assert "organization_id uuid not null" in source
    assert "foreign key (project_id, organization_id)" in source
    assert "alter table intelligence_monitoring_runs enable row level security" in source
    assert "has_organization_access(organization_id)" in source
    assert "has_project_write_access(organization_id)" in source
    assert "create policy intelligence_runs_authorized_insert" in source
    assert "for update" not in source.casefold()
    assert "for delete" not in source.casefold()


def test_intelligence_source_is_current_and_not_a_second_embedded_app() -> None:
    documentation = Path("docs/intelligence_integration.md").read_text(
        encoding="utf-8"
    )

    assert "consultorabiocore/Biocoreintelligenceaparte" in documentation
    assert "153fe467a204d77207c8b1fa3ed0883374ae9525" in documentation
    assert "no se incrusta mediante `iframe`" in documentation
    assert "no redirige a otro Streamlit" in documentation
