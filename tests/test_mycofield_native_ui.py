from pathlib import Path


def test_mycofield_page_is_native_and_project_scoped() -> None:
    source = Path("platform_pages/field.py").read_text(encoding="utf-8")

    assert 'st.session_state.get("biocore_mycofield_service")' in source
    assert 'st.session_state.get("biocore_project_service")' in source
    assert "service.create(" in source
    assert "service.list_observations(" in source
    assert "st.map(" in source
    assert "st.download_button(" in source
    assert "render_module_integration" not in source
    assert "streamlit.app" not in source
    assert "Plan Pro" not in source
    assert "identificación confirmada" in source


def test_mycofield_migration_has_tenant_rls_and_private_storage() -> None:
    source = Path("database/migrations/0011_native_mycofield.sql").read_text(
        encoding="utf-8"
    )

    assert "organization_id uuid not null" in source
    assert "foreign key (project_id, organization_id)" in source
    assert "alter table mycofield_observations enable row level security" in source
    assert "has_organization_access(organization_id)" in source
    assert "has_project_write_access(organization_id)" in source
    assert "privacy <> 'private'" in source
    assert "'mycofield-evidence'" in source
    assert "public = false" in source
