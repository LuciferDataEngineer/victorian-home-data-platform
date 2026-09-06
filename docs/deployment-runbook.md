# GitHub, Azure and Power BI deployment runbook

## 1 Push the repository

The project is initialised on branch `main`. Create an empty GitHub repository, then run:

```bash
git add .
git commit -m "Initial Victorian home data platform"
git remote add origin https://github.com/<account>/<repository>.git
git push -u origin main
```

Review `git status` before committing. Runtime data, local logs, virtual environments and secrets are excluded by `.gitignore`.

## 2 Create Azure federation

Create one Entra application/service principal for GitHub deployments. Add federated credentials restricted to the repository's `dev` and `prod` GitHub environments. Give it the minimum deployment role at the target subscription or resource-group scope.

Set these GitHub environment variables, not secrets containing passwords:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `SQL_ENTRA_ADMIN_OBJECT_ID`

Require reviewers for the `prod` environment. The workflow uses GitHub OIDC and therefore needs no client secret.

Create Key Vault secrets named `resend-api-key`, `alert-to-email`, and `alert-from-email`. The Function managed identity receives only Key Vault Secrets User and the required Storage data roles. Keep `ALERT_DRY_RUN=true` until the sender domain is verified in Resend and a test run has been reviewed.

## 3 Validate and deploy infrastructure

Install Azure CLI locally and run:

```bash
az login
az bicep build --file infra/bicep/main.bicep
az deployment sub what-if --location australiaeast --template-file infra/bicep/main.bicep --parameters environment=dev sqlAdministratorObjectId=<object-id>
```

Merge only after CI passes. Start `deploy-azure` manually with `dev`; inspect the deployment outputs and resources before deploying `prod`.
The workflow packages and deploys the Python Function after infrastructure succeeds.

## 4 Apply database migrations

Connect to the emitted SQL server as the configured Entra administrator and apply files in `sql/migrations` numeric order. Record the filename and checksum in a controlled migration-history table before production automation is introduced. Add Entra groups as contained database users and assign `analyst_reader` or `powerbi_reader`; never share the administrator identity.

## 5 Load Gold and connect Power BI

Load dimension and fact tables through the Function managed identity. Validate row counts and freshness, then connect Power BI to the two `mart.vw_powerbi_*` views. Follow `docs/powerbi-guide.md` and `powerbi/semantic-model.yml`.

## 6 Current release blocker

The VGV landing page advertises 2015–2025 suburb workbooks, but its file host returned HTTP 403 to the automated connector during the 5 September 2026 verification. Download the three workbooks through the publisher-supported browser flow, save them as `houses.xlsx`, `units.xlsx`, and `land.xlsx`, then run:

```bash
home-data run --source vgv_annual_sales --input-dir ./manual-input/vgv
home-data build-official-gold
home-data build-roi
```

Do not publish statewide rankings until the resulting unmatched-geography QA file is reviewed.

## 7 Scheduled refresh and alerts

The timer runs every 12 hours using UTC-based Azure Functions NCRONTAB. It synchronises the medallion container into an isolated temporary workspace, refreshes the latest Homes Victoria rental workbook, rebuilds official Gold and ROI when official VGV history exists, and synchronises outputs back to Blob Storage. If VGV history is missing, it logs a warning and does not send a ranking alert.

Alerts are content-hash idempotent: unchanged ROI output sends nothing. Dry-run mode logs the proposed alert without writing the sent-state fingerprint. After enabling delivery, the fingerprint is persisted only after Resend accepts the request.
