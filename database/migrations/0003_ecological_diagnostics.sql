-- BioCore Phase 3: versioned ecological diagnostic MVP.
-- Scope: flora, vegetation, fungi and lichens only.

alter type module_code add value if not exists 'ecological_diagnostic';
alter type module_code add value if not exists 'ecological_diagnostic_detailed';

do $$
begin
    create type ecological_diagnostic_type as enum ('brief', 'detailed');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type ecological_diagnostic_status as enum (
        'draft',
        'in_progress',
        'submitted',
        'automatically_assessed',
        'professional_review_requested',
        'under_review',
        'reviewed',
        'converted_to_project',
        'archived'
    );
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type ecological_review_status as enum (
        'requested',
        'contacted',
        'under_review',
        'completed',
        'cancelled'
    );
exception
    when duplicate_object then null;
end $$;

create table if not exists ecological_diagnostics (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null
        references organizations(id) on delete cascade,
    user_id uuid not null references app_users(id) on delete restrict,
    project_reference text,
    title text not null,
    diagnostic_type ecological_diagnostic_type not null default 'brief',
    status ecological_diagnostic_status not null default 'draft',
    questionnaire_version text not null,
    disclaimer_accepted_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    submitted_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (id, organization_id)
);

create index if not exists ecological_diagnostics_organization_idx
    on ecological_diagnostics (organization_id, updated_at desc);

create index if not exists ecological_diagnostics_status_idx
    on ecological_diagnostics (status, submitted_at desc);

create table if not exists ecological_diagnostic_responses (
    diagnostic_id uuid not null,
    organization_id uuid not null,
    question_key text not null,
    response_value jsonb not null,
    questionnaire_version text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (diagnostic_id, question_key),
    foreign key (diagnostic_id, organization_id)
        references ecological_diagnostics(id, organization_id)
        on delete cascade
);

create table if not exists ecological_diagnostic_assessments (
    id uuid primary key default gen_random_uuid(),
    diagnostic_id uuid not null,
    organization_id uuid not null,
    assessment_version integer not null check (assessment_version > 0),
    questionnaire_version text not null,
    rules_version text not null,
    result jsonb not null,
    report_label text not null,
    created_at timestamptz not null default now(),
    unique (diagnostic_id, assessment_version),
    foreign key (diagnostic_id, organization_id)
        references ecological_diagnostics(id, organization_id)
        on delete cascade
);

create table if not exists ecological_diagnostic_review_requests (
    id uuid primary key default gen_random_uuid(),
    diagnostic_id uuid not null,
    organization_id uuid not null,
    user_id uuid not null references app_users(id) on delete restrict,
    status ecological_review_status not null default 'requested',
    message text not null default '',
    requested_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (diagnostic_id, organization_id)
        references ecological_diagnostics(id, organization_id)
        on delete cascade
);

create index if not exists ecological_diagnostic_review_queue_idx
    on ecological_diagnostic_review_requests (status, requested_at desc);

alter table ecological_diagnostics enable row level security;
alter table ecological_diagnostic_responses enable row level security;
alter table ecological_diagnostic_assessments enable row level security;
alter table ecological_diagnostic_review_requests enable row level security;

drop policy if exists ecological_diagnostics_member_select
    on ecological_diagnostics;
create policy ecological_diagnostics_member_select
    on ecological_diagnostics
    for select
    using (has_organization_access(organization_id));

drop policy if exists ecological_diagnostic_responses_member_select
    on ecological_diagnostic_responses;
create policy ecological_diagnostic_responses_member_select
    on ecological_diagnostic_responses
    for select
    using (has_organization_access(organization_id));

drop policy if exists ecological_diagnostic_assessments_member_select
    on ecological_diagnostic_assessments;
create policy ecological_diagnostic_assessments_member_select
    on ecological_diagnostic_assessments
    for select
    using (has_organization_access(organization_id));

drop policy if exists ecological_diagnostic_reviews_member_select
    on ecological_diagnostic_review_requests;
create policy ecological_diagnostic_reviews_member_select
    on ecological_diagnostic_review_requests
    for select
    using (has_organization_access(organization_id));

-- Application users receive read-only RLS access. All writes are performed by
-- a trusted server service after role and organization checks.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        grant select on ecological_diagnostics to authenticated;
        grant select on ecological_diagnostic_responses to authenticated;
        grant select on ecological_diagnostic_assessments to authenticated;
        grant select on ecological_diagnostic_review_requests to authenticated;
    end if;
end $$;
