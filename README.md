# Victorian Home Investment Data Platform

A portfolio-grade data engineering project that turns Victorian open data into reproducible suburb-level investment screening features. It uses a medallion architecture, runs locally, and supports a free-first deployment using GitHub Actions, Cloudflare R2, Supabase and Streamlit. Azure remains an optional enterprise path.

## Architecture

```text
Victorian Government and ABS sources
                 |
                 v
Bronze: immutable source payloads and manifests in R2
                 |
                 v
Silver: typed, validated, canonical Parquet in R2
                 |
                 v
Gold: Supabase PostgreSQL marts and scores
                 |
                 +--> Streamlit (Power BI optional)
                 +--> Resend alerts
```

Bronze objects are immutable and content-addressed. Silver is the stable contract boundary. Gold contains only decision-ready, versioned products. Failed promotion leaves the last certified Gold snapshot available.

## Quick start

Requirements: Python 3.12 and Docker Desktop.

```bash
cp .env.example .env
docker compose up -d
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
home-data init
home-data run --source sample_sales
home-data run --source sample_rents
home-data build-gold
pytest
```

The sample adapters prove the complete medallion flow without depending on changing publisher files. Production HTTP adapters will be added one source at a time with captured contract fixtures.

## Project layout

- `src/home_data/`: ingestion, storage, quality and transformation code
- `config/`: buyer preferences and source metadata
- `sql/migrations/`: Azure SQL schemas, tables and roles
- `infra/bicep/`: Azure infrastructure as code
- `azure_function/`: 12-hour cloud refresh and idempotent alert entry point
- `supabase/migrations/`: PostgreSQL Gold schema and guarded publishing function
- `streamlit_app.py`: free interactive dashboard
- `powerbi/`: semantic model, measures and refresh contract
- `tests/`: unit and medallion contract tests
- `data/`: ignored local Bronze, Silver and Gold outputs
- `docs/`: architecture decisions and runbooks
- `logs/`: rotating JSON Lines pipeline and error logs

## Configuration

`config/buyer_profile.yml` defaults to all Victoria, every residential property type, owner-occupier and investment use cases, and no price/deposit ceiling. These are filters rather than hard-coded pipeline rules.

## Security principles

- GitHub Actions uses Azure OIDC; no long-lived Azure client secret.
- Azure Functions use managed identity for Storage, Key Vault and Azure SQL.
- Resend API credentials remain in Key Vault.
- Power BI reads certified Gold views only.
- Humans authenticate through Microsoft Entra groups.

See `docs/architecture.md` and the research blueprint in `outputs/` for the detailed design.

The complete operating sequence is in `docs/implementation-guide.md`. Error investigation and log queries are in `docs/logging-and-errors.md`.
Deployment is covered by `docs/deployment-runbook.md`, and the report design by `docs/powerbi-guide.md`.
The recommended A$0-development path is documented in `docs/free-cloud-deployment.md`.

## Official sales connector

Run `home-data run --source vgv_annual_sales` to ingest the official annual VGV house, unit and residential-land workbooks. Publisher access or layout changes fail closed and are written to `logs/pipeline.jsonl`; deterministic fixture tests continue to protect the transformation contract.

## Official rental connector

Run `home-data run --source homes_victoria_rents`. The connector asks DataVic for the latest dated XLSX resource, lands the unmodified workbook in Bronze, and normalises its suburb, property type, bedroom, quarter, bond-count and median-rent cells into Silver. Use `--input-dir` with a file named `rents.xlsx` when a publisher blocks automated access.

After both official sales and rent sources exist in Silver, run `home-data build-official-gold`. This creates independent price and rent history marts. It intentionally does not calculate a yield yet: VGV suburb names, Homes Victoria rental geographies and bedroom grains require an audited crosswalk before a defensible join.

Run `home-data build-roi` after the official histories. It creates a conservative, bedroom-grain ROI screening mart plus an unmatched-geography QA file. Review proposed aliases and add only approved mappings to `config/geography_crosswalk.csv`; fuzzy matching is intentionally disabled.
