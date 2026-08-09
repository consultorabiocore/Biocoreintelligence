-- Native BioCore MycoField observations and private photographic evidence.
-- Additive and idempotent. Apply after 0010_native_darwincheck.sql.

create table if not exists mycofield_observations (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    project_id uuid not null,
    created_by_user_id uuid not null references app_users(id) on delete restrict,
    sample_code text not null,
    observed_on date not null,
    latitude double precision not null,
    longitude double precision not null,
    map_latitude double precision,
    map_longitude double precision,
    privacy text not null default 'private',
    tentative_name text not null default 'Por determinar',
    substrate text not null,
    habitat text not null,
    method text not null,
    effort text not null,
    observable_traits jsonb not null default '[]'::jsonb,
    notes text not null default '',
    photos jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check (btrim(sample_code) <> ''),
    check (latitude between -90 and 90),
    check (longitude between -180 and 180),
    check (map_latitude is null or map_latitude between -90 and 90),
    check (map_longitude is null or map_longitude between -180 and 180),
    check (privacy in ('private', 'blurred', 'organization')),
    check (
        (privacy = 'private' and map_latitude is null and map_longitude is null)
        or (privacy <> 'private' and map_latitude is not null and map_longitude is not null)
    ),
    check (jsonb_typeof(observable_traits) = 'array'),
    check (jsonb_typeof(photos) = 'array')
);

create unique index if not exists mycofield_sample_code_project_unique
    on mycofield_observations (organization_id, project_id, lower(sample_code));

create index if not exists mycofield_project_date_idx
    on mycofield_observations
    (organization_id, project_id, observed_on desc, created_at desc);

create or replace function set_mycofield_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end
$$;

drop trigger if exists mycofield_set_updated_at on mycofield_observations;
create trigger mycofield_set_updated_at
before update on mycofield_observations
for each row execute function set_mycofield_updated_at();

alter table mycofield_observations enable row level security;

drop policy if exists mycofield_visible_select on mycofield_observations;
create policy mycofield_visible_select on mycofield_observations
    for select
    using (
        has_organization_access(organization_id)
        and (
            privacy <> 'private'
            or created_by_user_id in (
                select id
                from app_users
                where external_subject = current_oidc_subject()
            )
        )
    );

drop policy if exists mycofield_authorized_insert on mycofield_observations;
create policy mycofield_authorized_insert on mycofield_observations
    for insert
    with check (
        has_project_write_access(organization_id)
        and created_by_user_id in (
            select id
            from app_users
            where external_subject = current_oidc_subject()
        )
    );

-- Evidence is kept private. The trusted BioCore service creates short-lived
-- signed URLs only after checking organization, project and record privacy.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'mycofield-evidence',
    'mycofield-evidence',
    false,
    10485760,
    array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;
