-- BioCore configurable plans, add-ons and billing boundary.
-- Additive migration: no prices and no payment provider are configured here.
-- Apply after 0002_subscriptions_and_entitlements.sql and 0004.

alter type subscription_status add value if not exists 'pending_activation';
alter type subscription_status add value if not exists 'grace_period';

create table if not exists subscription_plans (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    display_name text not null,
    description text,
    active boolean not null default true,
    user_limit integer not null check (user_limit > 0),
    project_limit integer not null check (project_limit > 0),
    storage_limit_gb numeric(12, 2) not null check (storage_limit_gb >= 0),
    support_level text not null default 'estándar',
    configuration jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists plan_modules (
    plan_id uuid not null references subscription_plans(id) on delete cascade,
    module_code module_code not null,
    enabled boolean not null default true,
    limits jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    primary key (plan_id, module_code)
);

insert into subscription_plans (
    slug, display_name, description, user_limit, project_limit,
    storage_limit_gb, support_level
)
values
    (
        'core', 'BioCore Core',
        'Portal privado, proyectos, campañas, informes e historial ambiental.',
        5, 3, 10, 'estándar'
    ),
    (
        'professional', 'BioCore Professional',
        'Operación de terreno, calidad de datos y productos avanzados.',
        20, 15, 100, 'prioritario'
    ),
    (
        'enterprise', 'BioCore Enterprise',
        'Inteligencia, monitoreo, integraciones y permisos avanzados.',
        100, 100, 1000, 'dedicado'
    )
on conflict (slug) do update
set display_name = excluded.display_name,
    description = excluded.description,
    active = true,
    updated_at = now();

insert into plan_modules (plan_id, module_code)
select plan.id, configured.module_code::module_code
from subscription_plans plan
cross join lateral (
    values
        ('core', 'platform_core'),
        ('core', 'reports'),
        ('core', 'ecological_diagnostic'),
        ('professional', 'platform_core'),
        ('professional', 'field'),
        ('professional', 'darwincheck'),
        ('professional', 'reports'),
        ('professional', 'ecological_diagnostic'),
        ('enterprise', 'platform_core'),
        ('enterprise', 'field'),
        ('enterprise', 'darwincheck'),
        ('enterprise', 'intelligence'),
        ('enterprise', 'satellite'),
        ('enterprise', 'lidar'),
        ('enterprise', 'reports'),
        ('enterprise', 'academy'),
        ('enterprise', 'api_access'),
        ('enterprise', 'ecological_diagnostic')
) as configured(plan_slug, module_code)
where plan.slug = configured.plan_slug
on conflict (plan_id, module_code) do update
set enabled = true;

alter table organization_subscriptions
    add column if not exists plan_id uuid references subscription_plans(id),
    add column if not exists suspended_at timestamptz,
    add column if not exists suspension_reason text,
    add column if not exists cancelled_at timestamptz,
    add column if not exists data_retention_until date;

update organization_subscriptions subscription
set plan_id = plan.id
from subscription_plans plan
where subscription.plan_id is null
  and plan.slug = subscription.plan::text;

create table if not exists subscription_addons (
    id uuid primary key default gen_random_uuid(),
    subscription_id uuid not null
        references organization_subscriptions(id) on delete cascade,
    addon_code text not null,
    status text not null default 'active',
    starts_on date not null default current_date,
    ends_on date,
    configuration jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (subscription_id, addon_code),
    check (
        addon_code in (
            'lidar',
            'satellite_monitoring',
            'extra_storage',
            'extra_users',
            'api_access',
            'advanced_reports',
            'academy_training',
            'specialized_processing'
        )
    ),
    check (status in ('pending_activation', 'active', 'suspended', 'cancelled', 'expired')),
    check (ends_on is null or ends_on >= starts_on)
);

create table if not exists billing_events (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete restrict,
    subscription_id uuid references organization_subscriptions(id) on delete set null,
    event_code text not null,
    provider text,
    external_reference text,
    amount numeric(14, 2),
    currency text,
    payload jsonb not null default '{}'::jsonb,
    occurred_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    unique (provider, external_reference)
);

alter table project_access_grants
    add column if not exists project_id uuid,
    add column if not exists status text not null default 'active',
    add column if not exists access_origin text not null default 'project_contract';

do $$
begin
    alter table project_access_grants
        add constraint project_access_grants_project_fk
        foreign key (project_id, organization_id)
        references projects(id, organization_id)
        on delete cascade;
exception
    when duplicate_object then null;
end $$;

do $$
begin
    alter table project_access_grants
        add constraint project_access_grants_status_check
        check (status in ('pending', 'active', 'suspended', 'expired', 'cancelled'));
exception
    when duplicate_object then null;
end $$;

alter table subscription_plans enable row level security;
alter table plan_modules enable row level security;
alter table subscription_addons enable row level security;
alter table billing_events enable row level security;

drop policy if exists subscription_plans_authenticated_select on subscription_plans;
create policy subscription_plans_authenticated_select on subscription_plans
    for select using (active);

drop policy if exists plan_modules_authenticated_select on plan_modules;
create policy plan_modules_authenticated_select on plan_modules
    for select using (
        exists (
            select 1
            from subscription_plans plan
            where plan.id = plan_modules.plan_id
              and plan.active
        )
    );

drop policy if exists subscription_addons_member_select on subscription_addons;
create policy subscription_addons_member_select on subscription_addons
    for select using (
        exists (
            select 1
            from organization_subscriptions subscription
            where subscription.id = subscription_addons.subscription_id
              and has_organization_access(subscription.organization_id)
        )
    );

drop policy if exists billing_events_member_select on billing_events;
create policy billing_events_member_select on billing_events
    for select using (has_organization_access(organization_id));

-- No client write policies are granted. Billing remains a boundary interface
-- until a commercial design and payment provider are approved.
