from pathlib import Path


def test_ecological_evidence_migration_is_tenant_scoped_and_non_destructive() -> None:
    migration = Path(
        "database/migrations/0013_ecological_evidence.sql"
    ).read_text(encoding="utf-8")

    assert "create table if not exists ecological_evidence (" in migration
    assert "study_area_id uuid" in migration
    assert "references projects(id, organization_id)" in migration
    assert "create table if not exists ecological_evidence_media" in migration
    assert "create table if not exists ecological_evidence_history" in migration
    assert "alter table ecological_evidence enable row level security" in migration
    assert "has_organization_access(organization_id)" in migration
    assert "has_project_write_access(organization_id)" in migration
    assert "Deliberately no DELETE policy" in migration
    assert "'ecological-evidence'" in migration
    assert "false," in migration
    assert "ecological_evidence_objects_member_select" in migration
    assert "ecological_evidence_external_unique" in migration


def test_ecological_evidence_rollback_preserves_private_objects() -> None:
    rollback = Path(
        "database/rollbacks/0013_ecological_evidence_down.sql"
    ).read_text(encoding="utf-8")

    assert "drop table if exists ecological_evidence_history" in rollback
    assert "drop table if exists ecological_evidence_media" in rollback
    assert "drop table if exists ecological_evidence" in rollback
    assert "drop bucket" not in rollback.casefold()
