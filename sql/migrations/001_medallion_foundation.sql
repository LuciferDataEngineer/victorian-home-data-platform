CREATE SCHEMA meta;
GO
CREATE SCHEMA core;
GO
CREATE SCHEMA mart;
GO
CREATE SCHEMA audit;
GO
CREATE SCHEMA security;
GO

CREATE TABLE audit.pipeline_run (
    run_id uniqueidentifier NOT NULL PRIMARY KEY,
    source_name varchar(100) NOT NULL,
    entity_name varchar(100) NOT NULL,
    git_commit char(40) NULL,
    contract_version varchar(30) NOT NULL,
    started_at datetimeoffset NOT NULL,
    completed_at datetimeoffset NULL,
    status varchar(30) NOT NULL,
    input_rows bigint NULL,
    output_rows bigint NULL,
    bronze_uri nvarchar(2048) NULL,
    source_sha256 char(64) NULL
);

CREATE TABLE audit.data_quality_result (
    quality_result_id bigint IDENTITY PRIMARY KEY,
    run_id uniqueidentifier NOT NULL,
    check_name varchar(150) NOT NULL,
    severity varchar(20) NOT NULL,
    passed bit NOT NULL,
    observed_value nvarchar(500) NULL,
    threshold_value nvarchar(500) NULL,
    recorded_at datetimeoffset NOT NULL DEFAULT sysdatetimeoffset(),
    CONSTRAINT FK_quality_run FOREIGN KEY (run_id) REFERENCES audit.pipeline_run(run_id)
);

CREATE TABLE core.dim_geography (
    geography_key int IDENTITY PRIMARY KEY,
    geography_type varchar(30) NOT NULL,
    publisher_code varchar(100) NOT NULL,
    geography_name nvarchar(200) NOT NULL,
    parent_publisher_code varchar(100) NULL,
    valid_from date NOT NULL,
    valid_to date NULL,
    is_current bit NOT NULL,
    CONSTRAINT UQ_geography_version UNIQUE (geography_type, publisher_code, valid_from)
);

CREATE TABLE core.dim_property_type (
    property_type_key smallint IDENTITY PRIMARY KEY,
    property_type_code varchar(30) NOT NULL UNIQUE,
    property_type_name varchar(100) NOT NULL
);

CREATE TABLE core.fact_property_market (
    geography_key int NOT NULL,
    property_type_key smallint NOT NULL,
    observation_period date NOT NULL,
    median_price decimal(19,2) NULL,
    sales_count int NULL,
    publication_date date NOT NULL,
    run_id uniqueidentifier NOT NULL,
    is_provisional bit NOT NULL DEFAULT 0,
    CONSTRAINT PK_property_market PRIMARY KEY (geography_key, property_type_key, observation_period, publication_date),
    CONSTRAINT FK_market_geography FOREIGN KEY (geography_key) REFERENCES core.dim_geography(geography_key),
    CONSTRAINT FK_market_property_type FOREIGN KEY (property_type_key) REFERENCES core.dim_property_type(property_type_key),
    CONSTRAINT FK_market_run FOREIGN KEY (run_id) REFERENCES audit.pipeline_run(run_id),
    CONSTRAINT CK_market_price CHECK (median_price IS NULL OR median_price >= 0),
    CONSTRAINT CK_market_sales CHECK (sales_count IS NULL OR sales_count >= 0)
);

CREATE TABLE core.fact_rent (
    geography_key int NOT NULL,
    property_type_key smallint NOT NULL,
    observation_period date NOT NULL,
    median_weekly_rent decimal(12,2) NULL,
    publication_date date NOT NULL,
    run_id uniqueidentifier NOT NULL,
    CONSTRAINT PK_rent PRIMARY KEY (geography_key, property_type_key, observation_period, publication_date),
    CONSTRAINT FK_rent_geography FOREIGN KEY (geography_key) REFERENCES core.dim_geography(geography_key),
    CONSTRAINT FK_rent_property_type FOREIGN KEY (property_type_key) REFERENCES core.dim_property_type(property_type_key),
    CONSTRAINT FK_rent_run FOREIGN KEY (run_id) REFERENCES audit.pipeline_run(run_id),
    CONSTRAINT CK_rent_value CHECK (median_weekly_rent IS NULL OR median_weekly_rent >= 0)
);

CREATE TABLE mart.suburb_score_snapshot (
    geography_key int NOT NULL,
    property_type_key smallint NOT NULL,
    as_of_date date NOT NULL,
    score_version varchar(30) NOT NULL,
    weight_version varchar(30) NOT NULL,
    estimated_gross_yield_pct decimal(9,4) NULL,
    composite_score decimal(9,4) NULL,
    uncertainty_grade char(1) NOT NULL,
    source_coverage_pct decimal(5,2) NOT NULL,
    run_id uniqueidentifier NOT NULL,
    CONSTRAINT PK_suburb_score PRIMARY KEY (geography_key, property_type_key, as_of_date, score_version),
    CONSTRAINT FK_score_geography FOREIGN KEY (geography_key) REFERENCES core.dim_geography(geography_key),
    CONSTRAINT FK_score_property_type FOREIGN KEY (property_type_key) REFERENCES core.dim_property_type(property_type_key),
    CONSTRAINT FK_score_run FOREIGN KEY (run_id) REFERENCES audit.pipeline_run(run_id)
);

CREATE ROLE etl_writer;
CREATE ROLE analyst_reader;
CREATE ROLE powerbi_reader;
GRANT SELECT ON SCHEMA::mart TO analyst_reader;
GRANT SELECT ON SCHEMA::mart TO powerbi_reader;

