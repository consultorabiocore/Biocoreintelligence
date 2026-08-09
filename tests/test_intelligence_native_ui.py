from pathlib import Path


def test_intelligence_page_runs_inside_biocore() -> None:
    source = Path("platform_pages/intelligence.py").read_text(encoding="utf-8")

    assert 'st.session_state.get("biocore_intelligence_service")' in source
    assert 'st.session_state.get("biocore_project_service")' in source
    assert "service.run(" in source
    assert "service.list_runs(" in source
    assert "Sentinel-2" in source
    assert "MODIS" in source
    assert "ERA5-Land" in source
    assert "st.download_button(" in source
    assert "render_module_integration" not in source
    assert "streamlit.app" not in source
    assert "cumplimiento" in source


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
