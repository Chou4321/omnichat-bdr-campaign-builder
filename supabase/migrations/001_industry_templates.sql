create table if not exists public.industry_templates (
    id text primary key,
    industry_name text not null,
    payload jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists industry_templates_industry_name_idx
    on public.industry_templates (industry_name);

create table if not exists public.app_migrations (
    key text primary key,
    applied_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists industry_templates_set_updated_at
    on public.industry_templates;

create trigger industry_templates_set_updated_at
before update on public.industry_templates
for each row execute function public.set_updated_at();

alter table public.industry_templates enable row level security;
alter table public.app_migrations enable row level security;

comment on table public.industry_templates is
    'Permanent Industry Knowledge records managed by the Streamlit backend.';

comment on table public.app_migrations is
    'One-time application data migration markers.';
