/* Additive Azure SQL model for bedroom-grain rents and governed geography matching. */
CREATE TABLE core.dim_bedroom (
    bedroom_key tinyint IDENTITY PRIMARY KEY,
    bedroom_count tinyint NULL,
    bedroom_label varchar(30) NOT NULL UNIQUE
);
GO

CREATE TABLE core.geography_crosswalk (
    source_system varchar(60) NOT NULL,
    source_geography_name nvarchar(200) NOT NULL,
    geography_key int NOT NULL,
    match_method varchar(30) NOT NULL,
    review_status varchar(20) NOT NULL,
    reviewed_by nvarchar(200) NULL,
    reviewed_at datetimeoffset NULL,
    valid_from date NOT NULL,
    valid_to date NULL,
    CONSTRAINT PK_geography_crosswalk PRIMARY KEY
        (source_system, source_geography_name, valid_from),
    CONSTRAINT FK_crosswalk_geography FOREIGN KEY (geography_key)
        REFERENCES core.dim_geography(geography_key),
    CONSTRAINT CK_crosswalk_method CHECK
        (match_method IN ('publisher_code', 'normalised_exact', 'manual_reviewed')),
    CONSTRAINT CK_crosswalk_review CHECK
        (review_status IN ('pending', 'approved', 'rejected'))
);
GO

CREATE TABLE core.fact_rent_bedroom (
    geography_key int NOT NULL,
    property_type_key smallint NOT NULL,
    bedroom_key tinyint NOT NULL,
    observation_period date NOT NULL,
    median_weekly_rent decimal(12,2) NULL,
    bond_count int NULL,
    publication_date date NOT NULL,
    run_id uniqueidentifier NOT NULL,
    CONSTRAINT PK_rent_bedroom PRIMARY KEY
        (geography_key, property_type_key, bedroom_key, observation_period, publication_date),
    CONSTRAINT FK_rent_bedroom_geography FOREIGN KEY (geography_key)
        REFERENCES core.dim_geography(geography_key),
    CONSTRAINT FK_rent_bedroom_property FOREIGN KEY (property_type_key)
        REFERENCES core.dim_property_type(property_type_key),
    CONSTRAINT FK_rent_bedroom_dimension FOREIGN KEY (bedroom_key)
        REFERENCES core.dim_bedroom(bedroom_key),
    CONSTRAINT FK_rent_bedroom_run FOREIGN KEY (run_id)
        REFERENCES audit.pipeline_run(run_id),
    CONSTRAINT CK_rent_bedroom_value CHECK (median_weekly_rent IS NULL OR median_weekly_rent >= 0),
    CONSTRAINT CK_rent_bedroom_count CHECK (bond_count IS NULL OR bond_count >= 0)
);
GO

CREATE TABLE mart.suburb_roi_screen (
    geography_key int NOT NULL,
    property_type_key smallint NOT NULL,
    bedroom_key tinyint NOT NULL,
    as_of_date date NOT NULL,
    price_observation_period date NOT NULL,
    rent_observation_period date NOT NULL,
    median_price decimal(19,2) NOT NULL,
    median_weekly_rent decimal(12,2) NOT NULL,
    estimated_gross_yield_pct decimal(9,4) NOT NULL,
    price_growth_cagr_pct decimal(9,4) NULL,
    indicative_score decimal(9,4) NULL,
    score_version varchar(30) NOT NULL,
    match_quality varchar(30) NOT NULL,
    run_id uniqueidentifier NOT NULL,
    CONSTRAINT PK_suburb_roi_screen PRIMARY KEY
        (geography_key, property_type_key, bedroom_key, as_of_date, score_version),
    CONSTRAINT FK_roi_geography FOREIGN KEY (geography_key) REFERENCES core.dim_geography(geography_key),
    CONSTRAINT FK_roi_property FOREIGN KEY (property_type_key) REFERENCES core.dim_property_type(property_type_key),
    CONSTRAINT FK_roi_bedroom FOREIGN KEY (bedroom_key) REFERENCES core.dim_bedroom(bedroom_key),
    CONSTRAINT FK_roi_run FOREIGN KEY (run_id) REFERENCES audit.pipeline_run(run_id),
    CONSTRAINT CK_roi_yield CHECK (estimated_gross_yield_pct BETWEEN 0 AND 100)
);
GO

GRANT SELECT ON OBJECT::mart.suburb_roi_screen TO analyst_reader;
GRANT SELECT ON OBJECT::mart.suburb_roi_screen TO powerbi_reader;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::core TO etl_writer;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::audit TO etl_writer;
GRANT SELECT, INSERT, UPDATE ON SCHEMA::mart TO etl_writer;
GO
