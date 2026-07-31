-- BioCore project experience fields.
-- Additive and idempotent. Apply after 0008_project_management.sql.

alter table projects
    add column if not exists current_stage text not null default 'Inicio',
    add column if not exists progress_percent smallint not null default 0,
    add column if not exists responsible_name text not null default 'Por asignar',
    add column if not exists next_activity text not null default 'Por definir',
    add column if not exists next_activity_date date;

-- Preserve existing business data while giving legacy records understandable
-- workflow values. These are operational placeholders, not demo content.
update projects
set current_stage = case status
        when 'planning' then 'Planificación'
        when 'active' then 'Ejecución'
        when 'paused' then 'En pausa'
        when 'completed' then 'Cierre'
        when 'archived' then 'Archivado'
        else 'Inicio'
    end
where current_stage = 'Inicio';

do $$
begin
    alter table projects
        add constraint projects_progress_percent_check
        check (progress_percent between 0 and 100);
exception
    when duplicate_object then null;
end $$;

do $$
begin
    alter table projects
        add constraint projects_experience_text_check
        check (
            btrim(current_stage) <> ''
            and btrim(responsible_name) <> ''
            and btrim(next_activity) <> ''
        );
exception
    when duplicate_object then null;
end $$;

create index if not exists projects_org_next_activity_idx
    on projects (organization_id, next_activity_date)
    where status <> 'archived';

-- Existing organization RLS policies on projects cover these columns.
-- There is deliberately no DELETE policy: archiving remains the only flow.
