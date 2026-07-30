-- Inventory and account-linking bridge for phased login retirement.
-- Passwords and password hashes must never be copied into this table.

create table if not exists legacy_identity_links (
    id uuid primary key default gen_random_uuid(),
    source_application text not null,
    legacy_identifier text not null,
    normalized_email text,
    user_id uuid references app_users(id) on delete set null,
    match_status text not null default 'pending',
    force_password_reset boolean not null default true,
    reviewed_by_user_id uuid references app_users(id) on delete set null,
    reviewed_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (source_application, legacy_identifier),
    check (
        match_status in (
            'pending',
            'matched_by_verified_email',
            'manual_review_required',
            'linked',
            'invited',
            'ignored'
        )
    )
);

create index if not exists legacy_identity_links_email_idx
    on legacy_identity_links (lower(normalized_email))
    where normalized_email is not null;

alter table legacy_identity_links enable row level security;

-- Deliberately no client policies. Only the trusted migration/admin service
-- may inspect or modify identity-linking records.
