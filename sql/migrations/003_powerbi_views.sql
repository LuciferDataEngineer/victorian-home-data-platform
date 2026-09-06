CREATE VIEW mart.vw_powerbi_roi_screen AS
SELECT
    r.as_of_date,
    g.geography_name AS suburb,
    g.parent_publisher_code AS lga_code,
    p.property_type_name AS property_type,
    b.bedroom_label,
    r.price_observation_period,
    r.rent_observation_period,
    r.median_price,
    r.median_weekly_rent,
    r.estimated_gross_yield_pct,
    r.price_growth_cagr_pct,
    r.indicative_score,
    r.score_version,
    r.match_quality
FROM mart.suburb_roi_screen AS r
JOIN core.dim_geography AS g ON g.geography_key = r.geography_key
JOIN core.dim_property_type AS p ON p.property_type_key = r.property_type_key
JOIN core.dim_bedroom AS b ON b.bedroom_key = r.bedroom_key
WHERE g.is_current = 1;
GO

CREATE VIEW mart.vw_powerbi_data_freshness AS
WITH latest_runs AS (
    SELECT
        source_name,
        entity_name,
        completed_at,
        status,
        output_rows,
        ROW_NUMBER() OVER (
            PARTITION BY source_name, entity_name ORDER BY completed_at DESC, started_at DESC
        ) AS recency
    FROM audit.pipeline_run
)
SELECT source_name, entity_name, completed_at, status, output_rows
FROM latest_runs
WHERE recency = 1;
GO

GRANT SELECT ON OBJECT::mart.vw_powerbi_roi_screen TO powerbi_reader;
GRANT SELECT ON OBJECT::mart.vw_powerbi_data_freshness TO powerbi_reader;
GO
