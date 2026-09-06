# Implementation guide

This guide explains what each project step does, why it exists and how to verify it. Run commands from the repository root.

## Step 1 Create the local environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

The virtual environment isolates Python packages. The editable install exposes the `home-data` command while keeping source code editable. `.env` is ignored by Git and is for local non-production settings only.

Verify with `home-data --help` and `pytest`.

## Step 2 Start local service emulators

```bash
docker compose up -d
docker compose ps
```

Azurite emulates Azure Blob, Queue and Table Storage. SQL Edge provides a local SQL endpoint for interface and migration testing. Neither contains production data. Stop them with `docker compose down`; add `-v` only when intentionally deleting local volumes.

## Step 3 Initialise medallion folders

```bash
home-data init
```

This creates local `data/bronze`, `data/silver`, `data/gold` and `data/quarantine`. The directories emulate future ADLS containers and are ignored by Git.

## Step 4 Run deterministic sample ingestion

```bash
home-data run --source sample_sales
home-data run --source sample_rents
```

Each command obtains a source payload, assigns a UUID run ID, calculates SHA-256, writes the untouched payload and JSON manifest to Bronze, validates the schema, and writes typed Parquet to Silver. Fixtures make CI independent of network availability.

Verify that each Bronze run directory has `payload.csv` and `manifest.json`, and that each Silver entity has a run-specific Parquet file.

## Step 5 Run the official VGV connector

```bash
home-data run --source vgv_annual_sales
```

The adapter requests the current official Valuer-General Victoria annual house, unit and residential-land workbooks. Each workbook becomes an independent Bronze entity. The parser searches workbook sheets for a suburb/locality header and four-digit year columns, then converts wide annual columns to canonical long-form rows.

The Victorian publisher may reject automated downloads or alter workbook layout. A non-zero command exit and an exception in `logs/pipeline.jsonl` are intentional safe failure behaviour. Update URLs or parser contracts only after checking the official landing page and adding a historical regression fixture.

If the site rejects automated download, download the three linked workbooks in your browser and save them as `houses.xlsx`, `units.xlsx` and `land.xlsx` under a temporary input directory. Then run:

```bash
home-data run --source vgv_annual_sales --input-dir ./manual-input/vgv
```

The local files still enter immutable Bronze storage with checksums and file URIs. `manual-input/` should not be committed; add it to `.gitignore` if you use that exact location.

Official landing page: https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics

## Step 6 Run the official Homes Victoria rental connector

```bash
home-data run --source homes_victoria_rents
```

The connector queries the official DataVic metadata API and selects the XLSX with the newest `period_end`, so a new quarter does not require a code release. The untouched workbook and source dates go to Bronze. The parser reads each bedroom/property worksheet, forward-fills rental region, pairs the repeated quarter `Count` and `Median` columns, and writes one Silver row per suburb, property type, bedroom and quarter.

For a manual fallback, save the official workbook as `rents.xlsx` and run:

```bash
home-data run --source homes_victoria_rents --input-dir ./manual-input/rents
```

Dataset metadata: https://discover.data.vic.gov.au/dataset/rental-report-quarterly-moving-annual-rents-by-suburb

## Step 7 Build Gold marts

```bash
home-data build-gold
```

The current Gold proof joins sample sales and rents at suburb, LGA, property type and year grain. It calculates estimated gross yield and assigns liquidity confidence from sales count. This is deliberately simple; the real rent adapter and geography crosswalk come next.

Verify `data/gold/mart_suburb_snapshot.csv` and the equivalent Parquet file.

For source-faithful official histories, run `home-data build-official-gold`. It writes `mart_vgv_price_history` and `mart_homes_rent_history` as CSV and Parquet. They remain separate because rent has bedroom/quarter grain while sales has property-type/year grain, and source suburb labels still need a reviewed geography crosswalk. Calculating yield before that work would create false precision.

## Step 8 Inspect logs

```bash
tail -f logs/pipeline.jsonl
python -m json.tool < <(tail -n 1 logs/pipeline.jsonl)
```

Logs are JSON Lines so humans, PowerShell, jq, Log Analytics and Application Insights can read the same events. Each event includes timestamp, level, logger and message; pipeline events add run ID, source, entity, layer, row count and path where relevant.

See `docs/logging-and-errors.md` for triage.

## Step 9 Run quality checks

```bash
ruff check .
pytest
```

Linting catches unsafe or inconsistent code. Tests cover Bronze manifests, critical schema failures, the VGV workbook contract parser, and end-to-end Gold yield creation. A critical quality failure prevents Silver/Gold promotion.

## Step 10 Validate infrastructure

```bash
az bicep build --file infra/bicep/main.bicep
az deployment sub what-if --location australiaeast --template-file infra/bicep/main.bicep --parameters environment=dev sqlAdministratorObjectId=<entra-object-id>
```

Bicep provisions the resource group, hierarchical-namespace Storage Account, Key Vault, Entra-only Azure SQL server and serverless database, and consumption-plan Function App. `what-if` previews changes; it does not deploy.

## Step 11 Configure GitHub and deploy

Create GitHub environments named `dev` and `prod`. Add repository/environment variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` and `SQL_ENTRA_ADMIN_OBJECT_ID`. Configure a federated identity credential restricted to the repository environment. Do not create a client secret.

The CI workflow runs lint and tests for pull requests. The deployment workflow is manual and uses the GitHub OIDC token to deploy Bicep.

## Step 12 Schedule ingestion

The Azure Function timer will call the same source adapters. Recommended schedules are metadata-aware: poll annual/quarterly landing pages every 12 hours using ETag/Last-Modified, but download and process only changed resources. Realtime sources get separate schedules later.

## Step 13 Connect Power BI and alerts

Power BI will connect only to certified `mart` views. Resend alerts will read Gold changes, deduplicate by event fingerprint and fetch the API key through managed identity from Key Vault. Neither consumer may parse Bronze or Silver directly.

## Step 14 Build the governed ROI screen

```bash
home-data build-roi
```

The job creates a conservative uppercase alphanumeric suburb key, applies only reviewed aliases from `config/geography_crosswalk.csv`, and joins identical geography/property-type keys. It retains bedroom grain and uses the latest rent quarter and price year. The output is `mart_suburb_roi_screen`; non-matches go to `dq_unmatched_geographies` for human review.

The indicative score weights within-run percentiles: 60% gross yield and 40% historical price CAGR. A missing growth history produces no score rather than an invented value. It is a screening aid only and omits ownership costs, financing, tax, vacancy and property condition.

Migration `002_governed_roi_model.sql` adds the bedroom dimension, versioned reviewed geography crosswalk, bedroom-grain rent fact and ROI mart to Azure SQL. Run migrations in numeric order and grant people membership through Entra-backed database users rather than direct object grants.
