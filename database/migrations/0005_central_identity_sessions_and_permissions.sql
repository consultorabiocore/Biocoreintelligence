-- BioCore central identity foundation.
-- Additive migration: it does not remove legacy users, credentials or logins.
-- Apply after 0001_identity_and_tenancy.sql.

alter type app_role add value if not exists 'cliente_editor';

alter table app_users
    add column if not exists status text not null default 'active',
    add column if not exists email_verified boolean not null default false,
    add column if not exists last_login_at timestamptz,
    add column if not exists preferences jsonb not null default '{}'::jsonb,
    add column if not exists mfa_enabled boolean not null default false,
    add column if not exists terms_accepted_at timestamptz;

do $$
begin
    alter table app_users
        add constraint app_users_status_check
        check (status in ('pending_verification', 'active', 'suspended', 'disabled'));
exception
    when duplicate_object then null;
end $$;

create table if not exists auth_identities (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references app_users(id) on delete cascade,
    provider text not null,
    provider_subject text not null,
    email_at_provider text,
    created_at timestamptz not null default now(),
    last_used_at timestamptz,
    unique (provider, provider_subject)
);

create index if not exists auth_identities_user_idx
    on auth_identities (user_id);

-- Preserve existing Google/OIDC subjects while moving toward multiple providers.
insert into auth_identities (user_id, provider, provider_subject, email_at_provider)
select id, 'legacy_oidc', external_subject, email
from app_users
on conflict (provider, provider_subject) do nothing;

insert into auth_identities (user_id, provider, provider_subject, email_at_provider)
select id, 'google', external_subject, email
from app_users
on conflict (provider, provider_subject) do nothing;

create table if not exists roles (
    code text primary key,
    display_name text not null,
    system_role boolean not null default true,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists permissions (
    code text primary key,
    description text not null,
    created_at timestamptz not null default now()
);

create table if not exists role_permissions (
    role_code text not null references roles(code) on delete cascade,
    permission_code text not null references permissions(code) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (role_code, permission_code)
);

insert into roles (code, display_name)
values
    ('superadmin', 'Superadministración'),
    ('administradora_biocore', 'Administración BioCore'),
    ('especialista_biocore', 'Especialista BioCore'),
    ('cliente_administrador', 'Administración de cliente'),
    ('cliente_editor', 'Edición de cliente'),
    ('cliente_lector', 'Lectura de cliente')
on conflict (code) do update
set display_name = excluded.display_name,
    active = true;

insert into permissions (code, description)
values
    ('platform:admin', 'Administrar la plataforma BioCore'),
    ('organizations:read', 'Consultar organizaciones autorizadas'),
    ('organizations:manage', 'Administrar la organización activa'),
    ('users:invite', 'Invitar usuarios a la organización'),
    ('users:manage', 'Administrar membresías y roles'),
    ('projects:read', 'Consultar proyectos autorizados'),
    ('projects:write', 'Crear o modificar proyectos'),
    ('projects:grant_access', 'Administrar accesos a proyectos'),
    ('campaigns:read', 'Consultar campañas'),
    ('campaigns:write', 'Crear o modificar campañas'),
    ('maps:read', 'Consultar mapas'),
    ('field:read', 'Consultar BioCore Field'),
    ('field:write', 'Registrar o modificar datos de terreno'),
    ('darwincheck:read', 'Consultar DarwinCheck'),
    ('darwincheck:write', 'Ejecutar y guardar validaciones'),
    ('intelligence:read', 'Consultar BioCore Intelligence'),
    ('intelligence:write', 'Ejecutar análisis de Intelligence'),
    ('reports:read', 'Consultar informes'),
    ('reports:publish', 'Publicar informes'),
    ('academy:read', 'Consultar BioCore Academy'),
    ('subscriptions:read', 'Consultar la suscripción'),
    ('subscriptions:manage', 'Administrar planes y habilitaciones'),
    ('ecological_diagnostic:read', 'Consultar diagnósticos ecológicos'),
    ('ecological_diagnostic:write', 'Crear o modificar diagnósticos ecológicos'),
    ('downloads:sensitive', 'Descargar información sensible')
on conflict (code) do update
set description = excluded.description;

-- Platform administrators receive every current permission.
insert into role_permissions (role_code, permission_code)
select admin_roles.role_code, permissions.code
from (
    values ('superadmin'), ('administradora_biocore')
) as admin_roles(role_code)
cross join permissions
on conflict do nothing;

insert into role_permissions (role_code, permission_code)
values
    ('especialista_biocore', 'organizations:read'),
    ('especialista_biocore', 'projects:read'),
    ('especialista_biocore', 'projects:write'),
    ('especialista_biocore', 'campaigns:read'),
    ('especialista_biocore', 'campaigns:write'),
    ('especialista_biocore', 'maps:read'),
    ('especialista_biocore', 'field:read'),
    ('especialista_biocore', 'field:write'),
    ('especialista_biocore', 'darwincheck:read'),
    ('especialista_biocore', 'darwincheck:write'),
    ('especialista_biocore', 'intelligence:read'),
    ('especialista_biocore', 'intelligence:write'),
    ('especialista_biocore', 'reports:read'),
    ('especialista_biocore', 'reports:publish'),
    ('especialista_biocore', 'academy:read'),
    ('especialista_biocore', 'subscriptions:read'),
    ('especialista_biocore', 'ecological_diagnostic:read'),
    ('especialista_biocore', 'ecological_diagnostic:write'),
    ('cliente_administrador', 'organizations:read'),
    ('cliente_administrador', 'organizations:manage'),
    ('cliente_administrador', 'users:invite'),
    ('cliente_administrador', 'users:manage'),
    ('cliente_administrador', 'projects:read'),
    ('cliente_administrador', 'projects:write'),
    ('cliente_administrador', 'projects:grant_access'),
    ('cliente_administrador', 'campaigns:read'),
    ('cliente_administrador', 'campaigns:write'),
    ('cliente_administrador', 'maps:read'),
    ('cliente_administrador', 'field:read'),
    ('cliente_administrador', 'field:write'),
    ('cliente_administrador', 'darwincheck:read'),
    ('cliente_administrador', 'darwincheck:write'),
    ('cliente_administrador', 'intelligence:read'),
    ('cliente_administrador', 'reports:read'),
    ('cliente_administrador', 'academy:read'),
    ('cliente_administrador', 'subscriptions:read'),
    ('cliente_administrador', 'ecological_diagnostic:read'),
    ('cliente_administrador', 'ecological_diagnostic:write'),
    ('cliente_editor', 'projects:read'),
    ('cliente_editor', 'projects:write'),
    ('cliente_editor', 'campaigns:read'),
    ('cliente_editor', 'campaigns:write'),
    ('cliente_editor', 'maps:read'),
    ('cliente_editor', 'field:read'),
    ('cliente_editor', 'field:write'),
    ('cliente_editor', 'darwincheck:read'),
    ('cliente_editor', 'darwincheck:write'),
    ('cliente_editor', 'intelligence:read'),
    ('cliente_editor', 'reports:read'),
    ('cliente_editor', 'academy:read'),
    ('cliente_editor', 'subscriptions:read'),
    ('cliente_editor', 'ecological_diagnostic:read'),
    ('cliente_editor', 'ecological_diagnostic:write'),
    ('cliente_lector', 'projects:read'),
    ('cliente_lector', 'campaigns:read'),
    ('cliente_lector', 'maps:read'),
    ('cliente_lector', 'field:read'),
    ('cliente_lector', 'darwincheck:read'),
    ('cliente_lector', 'intelligence:read'),
    ('cliente_lector', 'reports:read'),
    ('cliente_lector', 'academy:read'),
    ('cliente_lector', 'subscriptions:read'),
    ('cliente_lector', 'ecological_diagnostic:read')
on conflict do nothing;

create table if not exists projects (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    code text,
    name text not null,
    status text not null default 'active',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (id, organization_id)
);

create unique index if not exists projects_code_org_unique
    on projects (organization_id, lower(code))
    where code is not null;

create table if not exists project_access (
    user_id uuid not null references app_users(id) on delete cascade,
    organization_id uuid not null references organizations(id) on delete cascade,
    project_id uuid not null,
    access_level text not null default 'read',
    starts_at timestamptz not null default now(),
    ends_at timestamptz,
    active boolean not null default true,
    granted_by_user_id uuid references app_users(id) on delete set null,
    created_at timestamptz not null default now(),
    primary key (user_id, project_id),
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check (access_level in ('read', 'edit', 'manage')),
    check (ends_at is null or ends_at > starts_at)
);

create index if not exists project_access_org_user_idx
    on project_access (organization_id, user_id, active);

create table if not exists auth_sessions (
    id uuid primary key default gen_random_uuid(),
    token_hash text not null unique,
    user_id uuid not null references app_users(id) on delete cascade,
    organization_id uuid not null references organizations(id) on delete cascade,
    parent_session_id uuid references auth_sessions(id) on delete cascade,
    audience text not null default 'platform',
    auth_method text not null,
    started_at timestamptz not null default now(),
    expires_at timestamptz not null,
    last_seen_at timestamptz not null default now(),
    revoked_at timestamptz,
    revoked_reason text,
    ip_hash text,
    user_agent_hash text,
    check (expires_at > started_at)
);

create index if not exists auth_sessions_user_active_idx
    on auth_sessions (user_id, organization_id, expires_at)
    where revoked_at is null;

create table if not exists module_launch_codes (
    id uuid primary key default gen_random_uuid(),
    code_hash text not null unique,
    session_id uuid not null references auth_sessions(id) on delete cascade,
    user_id uuid not null references app_users(id) on delete cascade,
    organization_id uuid not null references organizations(id) on delete cascade,
    module_code module_code not null,
    project_id uuid,
    return_to text not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    used_at timestamptz,
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check (expires_at > created_at)
);

create index if not exists module_launch_codes_active_idx
    on module_launch_codes (code_hash, expires_at)
    where used_at is null;

create table if not exists invitations (
    id uuid primary key default gen_random_uuid(),
    token_hash text not null unique,
    organization_id uuid not null references organizations(id) on delete cascade,
    email text not null,
    role app_role not null,
    project_ids uuid[] not null default array[]::uuid[],
    invited_by_user_id uuid not null references app_users(id) on delete restrict,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    accepted_at timestamptz,
    accepted_by_user_id uuid references app_users(id) on delete set null,
    revoked_at timestamptz,
    resend_count integer not null default 0,
    check (expires_at > created_at)
);

create index if not exists invitations_org_email_idx
    on invitations (organization_id, lower(email), expires_at);

create table if not exists audit_log (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid references organizations(id) on delete restrict,
    user_id uuid references app_users(id) on delete set null,
    session_id uuid references auth_sessions(id) on delete set null,
    event_code text not null,
    resource_type text,
    resource_id text,
    outcome text not null default 'success',
    metadata jsonb not null default '{}'::jsonb,
    occurred_at timestamptz not null default now(),
    check (outcome in ('success', 'denied', 'failure'))
);

create index if not exists audit_log_org_time_idx
    on audit_log (organization_id, occurred_at desc);

-- Atomic single-use exchange. Only the trusted Auth/API service should call it.
drop function if exists consume_module_launch_code(text);

create or replace function consume_module_launch_code(
    target_code_hash text,
    target_module_code module_code
)
returns setof module_launch_codes
language sql
security definer
set search_path = public
as $$
    update module_launch_codes
    set used_at = now()
    where id = (
        select id
        from module_launch_codes
        where code_hash = target_code_hash
          and module_code = target_module_code
          and used_at is null
          and expires_at > now()
        for update skip locked
        limit 1
    )
    returning *
$$;

revoke all on function consume_module_launch_code(text, module_code) from public;

drop function if exists consume_invitation(text, uuid);

create or replace function consume_invitation(
    target_token_hash text,
    target_user_id uuid,
    target_verified_email text
)
returns setof invitations
language sql
security definer
set search_path = public
as $$
    update invitations
    set accepted_at = now(),
        accepted_by_user_id = target_user_id
    where id = (
        select id
        from invitations
        where token_hash = target_token_hash
          and lower(email) = lower(target_verified_email)
          and accepted_at is null
          and revoked_at is null
          and expires_at > now()
        for update skip locked
        limit 1
    )
    returning *
$$;

revoke all on function consume_invitation(text, uuid, text) from public;

create or replace function revoke_session_tree(
    target_session_id uuid,
    target_reason text
)
returns integer
language sql
security definer
set search_path = public
as $$
    with recursive session_tree as (
        select id
        from auth_sessions
        where id = target_session_id
        union all
        select child.id
        from auth_sessions child
        join session_tree parent on child.parent_session_id = parent.id
    ),
    revoked as (
        update auth_sessions
        set revoked_at = now(),
            revoked_reason = target_reason
        where id in (select id from session_tree)
          and revoked_at is null
        returning id
    )
    select count(*)::integer from revoked
$$;

revoke all on function revoke_session_tree(uuid, text) from public;

alter table auth_identities enable row level security;
alter table roles enable row level security;
alter table permissions enable row level security;
alter table role_permissions enable row level security;
alter table projects enable row level security;
alter table project_access enable row level security;
alter table auth_sessions enable row level security;
alter table module_launch_codes enable row level security;
alter table invitations enable row level security;
alter table audit_log enable row level security;

drop policy if exists projects_member_select on projects;
create policy projects_member_select on projects
    for select using (has_organization_access(organization_id));

drop policy if exists project_access_member_select on project_access;
create policy project_access_member_select on project_access
    for select using (has_organization_access(organization_id));

drop policy if exists invitations_member_select on invitations;
create policy invitations_member_select on invitations
    for select using (has_organization_access(organization_id));

drop policy if exists audit_log_member_select on audit_log;
create policy audit_log_member_select on audit_log
    for select using (has_organization_access(organization_id));

-- Sessions, launch codes and identity-provider mappings intentionally have no
-- client policies. They are accessible only through the trusted Auth/API.
