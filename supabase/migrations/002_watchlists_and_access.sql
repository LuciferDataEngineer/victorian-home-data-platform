create table if not exists public.user_watchlists (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
    canonical_suburb_key text not null,
    property_type text not null check (property_type in ('house', 'unit')),
    bedrooms smallint not null check (bedrooms between 0 and 20),
    min_gross_yield_pct numeric(8,3),
    min_score numeric(8,2),
    max_median_price numeric(14,2),
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, canonical_suburb_key, property_type, bedrooms)
);

alter table public.user_watchlists enable row level security;

drop policy if exists "Users read own watchlists" on public.user_watchlists;
create policy "Users read own watchlists" on public.user_watchlists
for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "Users create own watchlists" on public.user_watchlists;
create policy "Users create own watchlists" on public.user_watchlists
for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "Users update own watchlists" on public.user_watchlists;
create policy "Users update own watchlists" on public.user_watchlists
for update to authenticated using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

drop policy if exists "Users delete own watchlists" on public.user_watchlists;
create policy "Users delete own watchlists" on public.user_watchlists
for delete to authenticated using ((select auth.uid()) = user_id);

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.user_watchlists to authenticated;

create table if not exists audit.user_alert_delivery (
    watchlist_id uuid not null references public.user_watchlists(id) on delete cascade,
    metric_fingerprint text not null,
    recipient_hash text not null,
    status text not null check (status in ('sent', 'failed', 'dry_run')),
    provider_message_id text,
    error_message text,
    evaluated_at timestamptz not null default now(),
    primary key (watchlist_id, metric_fingerprint)
);

alter table audit.user_alert_delivery enable row level security;
revoke all on audit.user_alert_delivery from anon, authenticated;

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'dashboard_reader') then
        create role dashboard_reader nologin;
    end if;
end
$$;

grant usage on schema mart to dashboard_reader;
grant select on mart.vw_dashboard_roi to dashboard_reader;
revoke insert, update, delete, truncate on mart.suburb_roi_screen from dashboard_reader;
