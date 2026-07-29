-- BioCore project management.
-- Additive and idempotent. Apply after 0004 and before enabling the UI.

alter table projects
    add column if not exists client_name text,
    add column if not exists project_type text,
    add column if not exists region text,
    add column if not exists commune text,
    add column if not exists modality text not null default 'mixed',
    add column if not exists description text,
    add column if not exists objective text,
    add column if not exists start_date date,
    add column if not exists archived_at timestamptz,
    add column if not exists created_by_user_id uuid
        references app_users(id) on delete restrict,
    add column if not exists updated_by_user_id uuid
        references app_users(id) on delete restrict;

-- Existing rows receive non-demonstrative technical defaults so the migration
-- remains safe. Their real content must be completed through the project form.
update projects
set code = 'BC-' || upper(left(replace(id::text, '-', ''), 10))
where code is null or btrim(code) = '';

update projects
set client_name = coalesce(nullif(client_name, ''), 'Por completar'),
    project_type = coalesce(nullif(project_type, ''), 'Por completar'),
    region = coalesce(nullif(region, ''), 'Por completar'),
    commune = coalesce(nullif(commune, ''), 'Por completar'),
    description = coalesce(nullif(description, ''), 'Por completar'),
    objective = coalesce(nullif(objective, ''), 'Por completar')
where client_name is null
   or project_type is null
   or region is null
   or commune is null
   or description is null
   or objective is null;

update projects
set metadata = jsonb_set(
        coalesce(metadata, '{}'::jsonb),
        '{legacy_status}',
        to_jsonb(status),
        true
    ),
    status = 'active'
where status not in ('planning', 'active', 'paused', 'completed', 'archived');

update projects
set archived_at = coalesce(archived_at, updated_at, now())
where status = 'archived';

update projects
set archived_at = null
where status <> 'archived' and archived_at is not null;

alter table projects
    alter column code set not null,
    alter column client_name set not null,
    alter column project_type set not null,
    alter column region set not null,
    alter column commune set not null,
    alter column description set not null,
    alter column objective set not null;

do $$
begin
    alter table projects
        add constraint projects_status_check
        check (status in ('planning', 'active', 'paused', 'completed', 'archived'));
exception
    when duplicate_object then null;
end $$;

do $$
begin
    alter table projects
        add constraint projects_modality_check
        check (modality in ('online', 'field', 'mixed'));
exception
    when duplicate_object then null;
end $$;

do $$
begin
    alter table projects
        add constraint projects_archived_state_check
        check (
            (status = 'archived' and archived_at is not null)
            or (status <> 'archived' and archived_at is null)
        );
exception
    when duplicate_object then null;
end $$;

create index if not exists projects_org_status_updated_idx
    on projects (organization_id, status, updated_at desc);

create index if not exists projects_org_name_idx
    on projects (organization_id, lower(name));

create table if not exists project_history (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null,
    organization_id uuid not null,
    actor_user_id uuid not null references app_users(id) on delete restrict,
    event_type text not null,
    changes jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check (
        event_type in ('created', 'updated', 'status_changed', 'archived')
    )
);

create index if not exists project_history_project_time_idx
    on project_history (organization_id, project_id, created_at desc);

create or replace function set_project_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end
$$;

drop trigger if exists projects_set_updated_at on projects;
create trigger projects_set_updated_at
before update on projects
for each row execute function set_project_updated_at();

create or replace function prevent_project_organization_change()
returns trigger
language plpgsql
as $$
begin
    if new.organization_id <> old.organization_id then
        raise exception 'A project cannot be moved between organizations';
    end if;
    return new;
end
$$;

drop trigger if exists projects_prevent_organization_change on projects;
create trigger projects_prevent_organization_change
before update of organization_id on projects
for each row execute function prevent_project_organization_change();

create or replace function has_project_write_access(
    target_organization_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
    select exists (
        select 1
        from memberships m
        join app_users u on u.id = m.user_id
        where u.external_subject = current_oidc_subject()
          and u.active
          and m.active
          and (
              m.organization_id = target_organization_id
              or m.role = 'superadmin'::app_role
          )
          and m.role in (
              'superadmin'::app_role,
              'administradora_biocore'::app_role,
              'especialista_biocore'::app_role,
              'cliente_administrador'::app_role,
              'cliente_editor'::app_role
          )
    )
$$;

revoke all on function has_project_write_access(uuid) from public;
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        grant execute on function has_project_write_access(uuid) to authenticated;
    end if;
end $$;

alter table project_history enable row level security;

drop policy if exists projects_member_select on projects;
create policy projects_member_select on projects
    for select
    using (has_organization_access(organization_id));

drop policy if exists projects_authorized_insert on projects;
create policy projects_authorized_insert on projects
    for insert
    with check (has_project_write_access(organization_id));

drop policy if exists projects_authorized_update on projects;
create policy projects_authorized_update on projects
    for update
    using (has_project_write_access(organization_id))
    with check (has_project_write_access(organization_id));

-- Deliberately no DELETE policy: archiving is the only supported removal flow.

drop policy if exists project_history_member_select on project_history;
create policy project_history_member_select on project_history
    for select
    using (has_organization_access(organization_id));

drop policy if exists project_history_authorized_insert on project_history;
create policy project_history_authorized_insert on project_history
    for insert
    with check (has_project_write_access(organization_id));
