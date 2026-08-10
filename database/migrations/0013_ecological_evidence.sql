-- Project-scoped ecological evidence, media, review state and audit history.
-- Additive and idempotent. Apply after 0012_native_intelligence.sql.

create table if not exists ecological_evidence (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    project_id uuid not null,
    study_area_id uuid,
    created_by_user_id uuid not null references app_users(id) on delete restrict,
    observation_date date not null,
    observation_time time,
    latitude double precision,
    longitude double precision,
    location_accuracy_m double precision,
    taxon_proposed text,
    scientific_name text,
    common_name text,
    taxonomic_group text not null default 'other',
    identification_status text not null default 'unidentified',
    evidence_type text not null default 'observation',
    observation_method text not null,
    notes text not null default '',
    source_type text not null default 'biocore',
    source_name text not null default 'BioCore',
    source_url text,
    external_id text,
    license text not null,
    author_name text not null,
    professional_review_status text not null default 'not_requested',
    review_notes text not null default '',
    reviewed_by_user_id uuid references app_users(id) on delete restrict,
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    archived_at timestamptz,
    unique (id, organization_id),
    foreign key (project_id, organization_id)
        references projects(id, organization_id) on delete cascade,
    check ((latitude is null) = (longitude is null)),
    check (latitude is null or latitude between -90 and 90),
    check (longitude is null or longitude between -180 and 180),
    check (location_accuracy_m is null or location_accuracy_m >= 0),
    check (taxonomic_group in ('flora', 'funga', 'lichens', 'fauna', 'other')),
    check (
        identification_status in (
            'unidentified', 'proposed', 'review_required', 'reviewed',
            'professionally_validated', 'uncertain'
        )
    ),
    check (evidence_type in ('observation', 'photograph', 'specimen', 'document', 'other')),
    check (source_type in ('biocore', 'inaturalist', 'external')),
    check (
        professional_review_status in (
            'not_requested', 'requested', 'under_review', 'approved',
            'corrected', 'uncertain'
        )
    ),
    check (btrim(observation_method) <> ''),
    check (btrim(author_name) <> ''),
    check (btrim(license) <> ''),
    check (
        reviewed_at is null
        or (reviewed_by_user_id is not null and btrim(review_notes) <> '')
    )
);

create index if not exists ecological_evidence_project_date_idx
    on ecological_evidence
    (organization_id, project_id, observation_date desc, created_at desc);

create index if not exists ecological_evidence_taxon_idx
    on ecological_evidence
    (organization_id, project_id, taxonomic_group, identification_status);

create unique index if not exists ecological_evidence_external_unique
    on ecological_evidence (organization_id, source_type, external_id)
    where external_id is not null and archived_at is null;

create table if not exists ecological_evidence_media (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    evidence_id uuid not null,
    storage_path text,
    filename text not null,
    content_type text,
    size_bytes bigint,
    author_name text not null,
    license text not null,
    source_type text not null default 'biocore',
    source_url text,
    sha256 text,
    is_primary boolean not null default false,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    archived_at timestamptz,
    foreign key (evidence_id, organization_id)
        references ecological_evidence(id, organization_id) on delete cascade,
    check (source_type in ('biocore', 'inaturalist', 'external')),
    check (size_bytes is null or size_bytes >= 0),
    check (btrim(filename) <> ''),
    check (btrim(author_name) <> ''),
    check (btrim(license) <> ''),
    check (
        (source_type = 'biocore' and storage_path is not null)
        or (source_type <> 'biocore' and source_url is not null)
    ),
    check (jsonb_typeof(metadata) = 'object')
);

create unique index if not exists ecological_evidence_media_storage_unique
    on ecological_evidence_media (storage_path)
    where storage_path is not null;

create unique index if not exists ecological_evidence_media_hash_unique
    on ecological_evidence_media (organization_id, evidence_id, sha256)
    where sha256 is not null and archived_at is null;

create index if not exists ecological_evidence_media_evidence_idx
    on ecological_evidence_media
    (organization_id, evidence_id, is_primary desc, created_at);

create table if not exists ecological_evidence_history (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references organizations(id) on delete cascade,
    evidence_id uuid not null,
    actor_user_id uuid not null references app_users(id) on delete restrict,
    event_type text not null,
    changes jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    foreign key (evidence_id, organization_id)
        references ecological_evidence(id, organization_id) on delete cascade,
    check (btrim(event_type) <> ''),
    check (jsonb_typeof(changes) = 'object')
);

create index if not exists ecological_evidence_history_idx
    on ecological_evidence_history
    (organization_id, evidence_id, created_at desc);

create or replace function set_ecological_evidence_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end
$$;

drop trigger if exists ecological_evidence_set_updated_at on ecological_evidence;
create trigger ecological_evidence_set_updated_at
before update on ecological_evidence
for each row execute function set_ecological_evidence_updated_at();

alter table ecological_evidence enable row level security;
alter table ecological_evidence_media enable row level security;
alter table ecological_evidence_history enable row level security;

drop policy if exists ecological_evidence_member_select on ecological_evidence;
create policy ecological_evidence_member_select on ecological_evidence
    for select using (has_organization_access(organization_id));

drop policy if exists ecological_evidence_authorized_insert on ecological_evidence;
create policy ecological_evidence_authorized_insert on ecological_evidence
    for insert with check (
        has_project_write_access(organization_id)
        and created_by_user_id in (
            select id from app_users
            where external_subject = current_oidc_subject()
        )
    );

drop policy if exists ecological_evidence_authorized_update on ecological_evidence;
create policy ecological_evidence_authorized_update on ecological_evidence
    for update
    using (has_project_write_access(organization_id))
    with check (has_project_write_access(organization_id));

-- Deliberately no DELETE policy: evidence is archived, never physically deleted.

drop policy if exists ecological_evidence_media_member_select on ecological_evidence_media;
create policy ecological_evidence_media_member_select on ecological_evidence_media
    for select using (has_organization_access(organization_id));

drop policy if exists ecological_evidence_media_authorized_insert on ecological_evidence_media;
create policy ecological_evidence_media_authorized_insert on ecological_evidence_media
    for insert with check (has_project_write_access(organization_id));

drop policy if exists ecological_evidence_media_authorized_update on ecological_evidence_media;
create policy ecological_evidence_media_authorized_update on ecological_evidence_media
    for update
    using (has_project_write_access(organization_id))
    with check (has_project_write_access(organization_id));

-- History is append-only: members may read, writers may insert, nobody updates/deletes.
drop policy if exists ecological_evidence_history_member_select on ecological_evidence_history;
create policy ecological_evidence_history_member_select on ecological_evidence_history
    for select using (has_organization_access(organization_id));

drop policy if exists ecological_evidence_history_authorized_insert on ecological_evidence_history;
create policy ecological_evidence_history_authorized_insert on ecological_evidence_history
    for insert with check (
        has_project_write_access(organization_id)
        and actor_user_id in (
            select id from app_users
            where external_subject = current_oidc_subject()
        )
    );

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'ecological-evidence',
    'ecological-evidence',
    false,
    15728640,
    array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- Direct client access, if enabled later, remains organization-scoped by the
-- first UUID segment of every object path. The current Streamlit app uses the
-- trusted service after checking project and role permissions.
drop policy if exists ecological_evidence_objects_member_select on storage.objects;
create policy ecological_evidence_objects_member_select on storage.objects
    for select using (
        bucket_id = 'ecological-evidence'
        and case
            when split_part(name, '/', 1) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                then has_organization_access(split_part(name, '/', 1)::uuid)
            else false
        end
    );

drop policy if exists ecological_evidence_objects_authorized_insert on storage.objects;
create policy ecological_evidence_objects_authorized_insert on storage.objects
    for insert with check (
        bucket_id = 'ecological-evidence'
        and case
            when split_part(name, '/', 1) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                then has_project_write_access(split_part(name, '/', 1)::uuid)
            else false
        end
    );
