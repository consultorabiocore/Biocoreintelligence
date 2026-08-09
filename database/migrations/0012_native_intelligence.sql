-- Native BioCore Intelligence monitoring history.
-- Additive and idempotent. Apply after 0011_native_mycofield.sql.

create table if not exists intelligence_monitoring_runs (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    project_id uuid not null,
    created_by_user_id uuid not null references app_users(id) on delete restrict,
    geometry jsonb not null,
    baseline_year integer not null,
    current_period text not null,
    baseline_period text not null,
    metrics jsonb not null default '[]'::jsonb,
    findings jsonb not null default '[]'::jsonb,
    provider_version text not null,
    evidence jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check (baseline_year between 2017 and 2100),
    check (geometry ->> 'type' = 'Polygon'),
    check (jsonb_typeof(metrics) = 'array'),
    check (jsonb_typeof(findings) = 'array'),
    check (jsonb_typeof(evidence) = 'object')
);

create index if not exists intelligence_runs_project_time_idx
    on intelligence_monitoring_runs
    (organization_id, project_id, created_at desc);

alter table intelligence_monitoring_runs enable row level security;

drop policy if exists intelligence_runs_member_select on intelligence_monitoring_runs;
create policy intelligence_runs_member_select on intelligence_monitoring_runs
    for select
    using (has_organization_access(organization_id));

drop policy if exists intelligence_runs_authorized_insert on intelligence_monitoring_runs;
create policy intelligence_runs_authorized_insert on intelligence_monitoring_runs
    for insert
    with check (has_project_write_access(organization_id));

-- Monitoring runs are immutable evidence. Corrections create a new run instead
-- of silently changing the source geometry, metrics or applied rule version.
