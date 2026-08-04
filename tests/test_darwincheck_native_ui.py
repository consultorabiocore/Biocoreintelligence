from pathlib import Path


def test_darwincheck_page_is_native_and_keeps_external_fallback_secondary() -> None:
    source = Path("platform_pages/darwincheck.py").read_text(encoding="utf-8")
    assert "biocore_darwincheck_service" in source
    assert "service.analyze_upload" in source
    assert "service.list_runs" in source
    assert "biocore_selected_project_id" in source
    assert "Acceso temporal a la versión independiente" in source
    assert "render_module_integration(\"darwincheck\")" not in source


def test_darwincheck_ui_explains_rules_uncertainty_and_next_step() -> None:
    source = Path("platform_pages/darwincheck.py").read_text(encoding="utf-8")
    for phrase in (
        "Datos utilizados",
        "Regla taxonómica",
        "Regla geográfica",
        "Incertidumbre",
        "Siguiente paso recomendado",
        "no certifica cumplimiento",
    ):
        assert phrase in source


def test_native_darwincheck_migration_is_tenant_scoped_and_immutable() -> None:
    migration = Path(
        "database/migrations/0010_native_darwincheck.sql"
    ).read_text(encoding="utf-8")
    assert "create table if not exists darwincheck_runs" in migration
    assert "foreign key (project_id, organization_id)" in migration
    assert "has_organization_access(organization_id)" in migration
    assert "has_project_write_access(organization_id)" in migration
    assert "no UPDATE" in migration
    assert "no DELETE" in migration
