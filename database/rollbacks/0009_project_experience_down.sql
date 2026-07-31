-- Non-destructive rollback for 0009.
-- Data columns are intentionally preserved. Only the optional index and checks
-- are removed so production information is never discarded.

drop index if exists projects_org_next_activity_idx;

alter table projects
    drop constraint if exists projects_progress_percent_check,
    drop constraint if exists projects_experience_text_check;
