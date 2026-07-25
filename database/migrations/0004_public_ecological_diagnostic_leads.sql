-- BioCore public ecological diagnostic lead capture.
-- This table is intentionally independent from organizations, memberships and
-- subscriptions so a visitor can complete the diagnostic before becoming a client.

create table if not exists public_ecological_diagnostic_leads (
    id uuid primary key default gen_random_uuid(),
    source text not null default 'public_ecological_diagnostic',
    status text not null default 'new'
        check (status in ('new', 'contacted', 'qualified', 'converted', 'closed')),
    contact_name text not null,
    contact_email text not null,
    contact_phone text not null default '',
    organization_name text not null default '',
    project_name text not null,
    commune text not null default '',
    region text not null default '',
    activity_type text not null default '',
    surface_hectares numeric,
    objective text not null default '',
    client_needs jsonb not null default '[]'::jsonb,
    metadata jsonb not null default '{}'::jsonb,
    responses jsonb not null,
    result jsonb not null,
    questionnaire_version text not null,
    rules_version text not null,
    contact_consent boolean not null check (contact_consent),
    consented_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists public_diagnostic_leads_created_idx
    on public_ecological_diagnostic_leads (created_at desc);

create index if not exists public_diagnostic_leads_status_idx
    on public_ecological_diagnostic_leads (status, created_at desc);

create index if not exists public_diagnostic_leads_email_idx
    on public_ecological_diagnostic_leads (lower(contact_email));

alter table public_ecological_diagnostic_leads enable row level security;

-- Visitors never receive direct table access. Inserts are executed server-side
-- with the service-role key after consent and validation. The service role
-- bypasses RLS; authenticated client accounts also receive no access to leads.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        revoke all on public_ecological_diagnostic_leads from anon;
    end if;
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        revoke all on public_ecological_diagnostic_leads from authenticated;
    end if;
end $$;
