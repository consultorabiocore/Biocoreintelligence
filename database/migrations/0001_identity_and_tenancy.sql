-- BioCore Phase 1: identity, roles and tenant isolation.
-- Apply with the database owner role. Application clients must not own tables.

create extension if not exists pgcrypto;

do $$
begin
    create type app_role as enum (
        'superadmin',
        'administradora_biocore',
        'especialista_biocore',
        'cliente_administrador',
        'cliente_lector'
    );
exception
    when duplicate_object then null;
end $$;

create table if not exists organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    slug text not null unique,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists app_users (
    id uuid primary key default gen_random_uuid(),
    external_subject text not null unique,
    email text,
    display_name text,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists app_users_email_lower_unique
    on app_users (lower(email))
    where email is not null;

create table if not exists memberships (
    user_id uuid not null references app_users(id) on delete cascade,
    organization_id uuid not null references organizations(id) on delete cascade,
    role app_role not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    primary key (user_id, organization_id, role)
);

create index if not exists memberships_organization_idx
    on memberships (organization_id, user_id)
    where active;

create or replace function current_oidc_subject()
returns text
language sql
stable
as $$
    select nullif(current_setting('request.jwt.claim.sub', true), '')
$$;

create or replace function has_organization_access(target_organization_id uuid)
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
    )
$$;

revoke all on function has_organization_access(uuid) from public;
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'authenticated') then
        grant execute on function has_organization_access(uuid) to authenticated;
    end if;
end $$;

alter table organizations enable row level security;
alter table app_users enable row level security;
alter table memberships enable row level security;

drop policy if exists organizations_member_select on organizations;
create policy organizations_member_select on organizations
    for select
    using (has_organization_access(id));

drop policy if exists memberships_member_select on memberships;
create policy memberships_member_select on memberships
    for select
    using (has_organization_access(organization_id));

drop policy if exists users_self_select on app_users;
create policy users_self_select on app_users
    for select
    using (external_subject = current_oidc_subject());

-- Writes are intentionally absent from client RLS policies. They must go
-- through a server-side administration service that checks explicit permission.
