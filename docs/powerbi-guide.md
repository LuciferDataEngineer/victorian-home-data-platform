# Power BI implementation guide

## Connection

Connect Power BI Desktop to Azure SQL using the server output from Bicep and database `homeinsights`. Select Microsoft Entra authentication. Import only `mart.vw_powerbi_roi_screen` and `mart.vw_powerbi_data_freshness`; report authors must not query Bronze/Silver or core facts directly.

Use Import mode initially. Configure incremental refresh on `as_of_date` after publishing, using the ranges in `powerbi/semantic-model.yml`. Azure SQL is a cloud source, so no on-premises gateway is required.

## Pages

1. **Data readiness** — latest refresh, source status, observation periods and unmatched geography count. Show a prominent warning if required inputs failed or are stale.
2. **Victoria explorer** — suburb, property type and bedroom filters; median price, rent, gross yield and CAGR cards; scatter plot of yield versus growth.
3. **Shortlist** — ranked table with all metric dates and match quality visible. Conditional formatting must not hide null growth or score values.
4. **Methodology** — formula definitions, excluded ownership costs, source links and the “screening only” disclaimer.

## Measure rules

Use the measures defined in `powerbi/semantic-model.yml`. Never sum medians or percentages. The database stores percentages as values such as `4.25`; the DAX display measures divide by 100 before percentage formatting.

## Access

Use a Power BI workspace backed by Entra groups. Report viewers receive the Viewer workspace role and membership in the Azure SQL `powerbi_reader` role. Authors receive Contributor separately. The Function managed identity is an ETL writer and must not own the workspace.

## Release gate

Do not publish statewide rankings until the full VGV workbooks have been ingested, `dq_unmatched_geographies` has been reviewed, required sources show successful freshness, and metric spot checks agree with the official source workbooks.
