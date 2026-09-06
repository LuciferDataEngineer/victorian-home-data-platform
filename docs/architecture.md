# Architecture decisions

## ADR 001 Medallion architecture

Status: accepted.

Bronze is an immutable record of publisher payloads and manifests. Silver is typed, validated and reusable. Gold is decision-ready and relational. Consumption tools cannot bypass Gold.

## ADR 002 Start without Spark

Status: accepted.

Initial government datasets are small enough for Python and SQL. Reconsider Spark when measured backfill size, parcel-level spatial joins or realtime history exceed the memory or runtime SLO of a single worker.

## ADR 003 Azure SQL for Gold

Status: accepted.

Azure SQL provides a familiar DBMS, constraints, security roles and direct Power BI integration. General Purpose serverless controls cost for intermittent development usage.

## ADR 004 Passwordless Azure access

Status: accepted.

Workloads use managed identity. GitHub uses OIDC federation. Human access uses Microsoft Entra groups and MFA. Resend remains an external API secret stored in Key Vault.

## ADR 005 Conservative geography resolution

Status: accepted.

Automated matching is limited to normalised exact suburb names. Combined publisher areas are never split or fuzzily assigned. Non-matches are written to a data-quality mart for review. Approved exceptions live in the version-controlled crosswalk and later in `core.geography_crosswalk` with reviewer and validity dates.

## ADR 006 ROI is an indicative screening metric

Status: accepted.

Gross yield is calculated as `weekly rent × 52 ÷ median sale price`. Rent remains at bedroom grain and is matched only to the same property type. The metric excludes vacancy, management, maintenance, strata, rates, tax, finance and transaction costs. It is useful for shortlist exploration, not a valuation, forecast or investment recommendation.
