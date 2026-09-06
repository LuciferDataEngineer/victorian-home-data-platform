create schema if not exists mart;
create schema if not exists audit;

create table if not exists mart.suburb_roi_screen (
    canonical_suburb_key text not null,
    property_type text not null check (property_type in ('house', 'unit')),
    bedrooms smallint not null check (bedrooms between 0 and 20),
    price_observation_date date not null,
    rent_period_end date not null,
    median_price numeric(14,2) not null check (median_price > 0),
    median_weekly_rent numeric(10,2) not null check (median_weekly_rent >= 0),
    estimated_gross_yield_pct numeric(8,3) not null check (estimated_gross_yield_pct between 0 and 100),
    price_growth_cagr_pct numeric(8,3),
    indicative_score numeric(8,2),
    match_quality text not null,
    score_version text not null,
    published_at timestamptz not null default now(),
    primary key (canonical_suburb_key, property_type, bedrooms, score_version)
);

create unlogged table if not exists mart.suburb_roi_screen_stage
(like mart.suburb_roi_screen including defaults including constraints);

alter table mart.suburb_roi_screen_stage drop column if exists published_at;

create table if not exists audit.unmatched_geography (
    source text not null,
    source_suburb text not null,
    canonical_suburb_key text not null,
    recorded_at timestamptz not null default now(),
    primary key (source, source_suburb)
);

create or replace function mart.publish_roi_screen()
returns void
language plpgsql
security invoker
as $$
begin
    if not exists (select 1 from mart.suburb_roi_screen_stage) then
        raise exception 'Refusing to publish an empty ROI screen';
    end if;
    delete from mart.suburb_roi_screen;
    insert into mart.suburb_roi_screen (
        canonical_suburb_key, property_type, bedrooms, price_observation_date,
        rent_period_end, median_price, median_weekly_rent, estimated_gross_yield_pct,
        price_growth_cagr_pct, indicative_score, match_quality, score_version
    )
    select
        canonical_suburb_key, property_type, bedrooms, price_observation_date,
        rent_period_end, median_price, median_weekly_rent, estimated_gross_yield_pct,
        price_growth_cagr_pct, indicative_score, match_quality, score_version
    from mart.suburb_roi_screen_stage;
end;
$$;

create or replace view mart.vw_dashboard_roi as
select * from mart.suburb_roi_screen;

revoke all on schema mart from anon, authenticated;
revoke all on all tables in schema mart from anon, authenticated;
