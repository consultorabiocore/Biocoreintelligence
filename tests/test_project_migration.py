from pathlib import Path


def test_project_migration_defines_required_fields_history_and_soft_delete() -> None:
    migration = Path(
        "database/migrations/0007_project_management.sql"
    ).read_text(encoding="utf-8")
    for field in (
        "client_name",
        "project_type",
        "region",
        "commune",
        "modality",
        "description",
        "objective",
        "start_date",
        "archived_at",
        "created_by_user_id",
        "updated_by_user_id",
    ):
        assert field in migration
    assert "create table if not exists project_history" in migration
    assert "Deliberately no DELETE policy" in migration


def test_project_rls_has_tenant_select_and_role_restricted_writes() -> None:
    migration = Path(
        "database/migrations/0007_project_management.sql"
    ).read_text(encoding="utf-8")
    assert "has_organization_access(organization_id)" in migration
    assert "has_project_write_access(organization_id)" in migration
    assert "projects_authorized_insert" in migration
    assert "projects_authorized_update" in migration
    assert "projects_prevent_organization_change" in migration
    assert "'cliente_lector'::app_role" not in migration


def test_project_migration_has_a_non_destructive_rollback() -> None:
    rollback = Path(
        "database/rollbacks/0007_project_management_down.sql"
    ).read_text(encoding="utf-8")
    assert "drop table if exists project_history" in rollback
    assert "drop table if exists projects" not in rollback
