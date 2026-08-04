-- Native DarwinCheck project audit history.
-- Additive and idempotent. Apply after 0009_project_experience.sql.

create table if not exists darwincheck_runs (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    project_id uuid not null,
    created_by_user_id uuid not null references app_users(id) on delete restrict,
    source_filename text not null,
    source_sha256 text not null,
    reference_name text not null,
    reference_version text not null,
    summary jsonb not null default '{}'::jsonb,
    findings jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check (btrim(source_filename) <> ''),
    check (source_sha256 ~ '^[0-9a-f]{64}$'),
    check (jsonb_typeof(summary) = 'object'),
    check (jsonb_typeof(findings) = 'array')
);

create index if not exists darwincheck_runs_project_time_idx
    on darwincheck_runs (organization_id, project_id, created_at desc);

create index if not exists darwincheck_runs_source_hash_idx
    on darwincheck_runs (organization_id, source_sha256);

alter table darwincheck_runs enable row level security;

drop policy if exists darwincheck_runs_member_select on darwincheck_runs;
create policy darwincheck_runs_member_select on darwincheck_runs
    for select
    using (has_organization_access(organization_id));

drop policy if exists darwincheck_runs_authorized_insert on darwincheck_runs;
create policy darwincheck_runs_authorized_insert on darwincheck_runs
    for insert
    with check (has_project_write_access(organization_id));

-- Runs are immutable scientific traces. There are deliberately no UPDATE or
-- DELETE policies. Project archiving preserves its audits; project deletion is
-- not available through the BioCore application.
