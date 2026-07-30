-- Roll back only the additive changes introduced by 0008.
-- Existing projects and the base table from 0004 are intentionally preserved.

drop policy if exists project_history_authorized_insert on project_history;
drop policy if exists project_history_member_select on project_history;
drop policy if exists projects_authorized_update on projects;
drop policy if exists projects_authorized_insert on projects;

drop function if exists has_project_write_access(uuid);
drop trigger if exists projects_prevent_organization_change on projects;
drop function if exists prevent_project_organization_change();
drop trigger if exists projects_set_updated_at on projects;
drop function if exists set_project_updated_at();
drop table if exists project_history;

drop index if exists projects_org_name_idx;
drop index if exists projects_org_status_updated_idx;

alter table projects
    drop constraint if exists projects_archived_state_check,
    drop constraint if exists projects_modality_check,
    drop constraint if exists projects_status_check,
    alter column code drop not null,
    drop column if exists updated_by_user_id,
    drop column if exists created_by_user_id,
    drop column if exists archived_at,
    drop column if exists start_date,
    drop column if exists objective,
    drop column if exists description,
    drop column if exists modality,
    drop column if exists commune,
    drop column if exists region,
    drop column if exists project_type,
    drop column if exists client_name;
