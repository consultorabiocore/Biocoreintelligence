-- BioCore Phase 2: organization subscriptions, module entitlements and usage.
-- Apply after 0001_identity_and_tenancy.sql with the database owner role.

do $$
begin
    create type subscription_plan as enum (
        'core',
        'professional',
        'enterprise'
    );
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type subscription_status as enum (
        'trial',
        'active',
        'past_due',
        'suspended',
        'cancelled',
        'expired'
    );
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type module_code as enum (
        'platform_core',
        'field',
        'darwincheck',
        'intelligence',
        'satellite',
        'lidar',
        'reports',
        'academy',
        'api_access',
        'ecological_diagnostic',
        'ecological_diagnostic_detailed'
    );
exception
    when duplicate_object then null;
end $$;

create table if not exists organization_subscriptions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null unique
        references organizations(id) on delete cascade,
    plan subscription_plan not null,
    status subscription_status not null default 'trial',
    starts_on date not null default current_date,
    renews_on date,
    user_limit integer not null default 5 check (user_limit > 0),
    project_limit integer not null default 3 check (project_limit > 0),
    storage_limit_gb numeric(12, 2) not null default 10
        check (storage_limit_gb >= 0),
    support_level text not null default 'estándar',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (renews_on is null or renews_on >= starts_on)
);

create table if not exists module_entitlements (
    subscription_id uuid not null
        references organization_subscriptions(id) on delete cascade,
    module_code module_code not null,
    enabled boolean not null default true,
    source text not null default 'plan',
    starts_on date,
    ends_on date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (subscription_id, module_code),
    check (ends_on is null or starts_on is null or ends_on >= starts_on)
);

create table if not exists subscription_usage (
    subscription_id uuid primary key
        references organization_subscriptions(id) on delete cascade,
    users_used integer not null default 0 check (users_used >= 0),
    projects_used integer not null default 0 check (projects_used >= 0),
    storage_used_gb numeric(12, 2) not null default 0
        check (storage_used_gb >= 0),
    measured_on date not null default current_date,
    updated_at timestamptz not null default now()
);

create table if not exists project_access_grants (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null
        references organizations(id) on delete cascade,
    project_reference text not null,
    starts_on date not null,
    ends_on date not null,
    modules module_code[] not null default array[]::module_code[],
    included_users integer not null default 1 check (included_users > 0),
    renewable boolean not null default true,
    converted_to_subscription boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (organization_id, project_reference),
    check (ends_on >= starts_on)
);

create index if not exists module_entitlements_subscription_idx
    on module_entitlements (subscription_id, enabled);

create index if not exists project_access_grants_organization_idx
    on project_access_grants (organization_id, starts_on, ends_on);

alter table organization_subscriptions enable row level security;
alter table module_entitlements enable row level security;
alter table subscription_usage enable row level security;
alter table project_access_grants enable row level security;

drop policy if exists organization_subscriptions_member_select
    on organization_subscriptions;
create policy organization_subscriptions_member_select
    on organization_subscriptions
    for select
    using (has_organization_access(organization_id));

drop policy if exists module_entitlements_member_select on module_entitlements;
create policy module_entitlements_member_select
    on module_entitlements
    for select
    using (
        exists (
            select 1
            from organization_subscriptions subscription
            where subscription.id = module_entitlements.subscription_id
              and has_organization_access(subscription.organization_id)
        )
    );

drop policy if exists subscription_usage_member_select on subscription_usage;
create policy subscription_usage_member_select
    on subscription_usage
    for select
    using (
        exists (
            select 1
            from organization_subscriptions subscription
            where subscription.id = subscription_usage.subscription_id
              and has_organization_access(subscription.organization_id)
        )
    );

drop policy if exists project_access_grants_member_select
    on project_access_grants;
create policy project_access_grants_member_select
    on project_access_grants
    for select
    using (has_organization_access(organization_id));

-- No insert, update or delete policy is granted to application clients.
-- Subscription writes must pass through a trusted administration service.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        grant select on organization_subscriptions to authenticated;
        grant select on module_entitlements to authenticated;
        grant select on subscription_usage to authenticated;
        grant select on project_access_grants to authenticated;
    end if;
end $$;
