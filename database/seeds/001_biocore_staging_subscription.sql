-- Optional staging seed for the existing BioCore organization.
-- Run only after migrations 0001 through 0008.

insert into organization_subscriptions (
    organization_id,
    plan_id,
    plan,
    status,
    starts_on,
    renews_on,
    user_limit,
    project_limit,
    storage_limit_gb,
    support_level
)
select
    organization.id,
    configured_plan.id,
    'enterprise'::subscription_plan,
    'active'::subscription_status,
    current_date,
    current_date + interval '1 year',
    10,
    10,
    50,
    'prioritario'
from organizations organization
join subscription_plans configured_plan
    on configured_plan.slug = 'enterprise'
where organization.slug = 'biocore'
on conflict (organization_id) do update
set
    plan_id = excluded.plan_id,
    plan = excluded.plan,
    status = excluded.status,
    renews_on = excluded.renews_on,
    user_limit = excluded.user_limit,
    project_limit = excluded.project_limit,
    storage_limit_gb = excluded.storage_limit_gb,
    support_level = excluded.support_level,
    updated_at = now();

insert into subscription_usage (
    subscription_id,
    users_used,
    projects_used,
    storage_used_gb,
    measured_on
)
select id, 1, 0, 0, current_date
from organization_subscriptions
where organization_id = (
    select id from organizations where slug = 'biocore'
)
on conflict (subscription_id) do nothing;
