# Free-cloud deployment guide

This is the recommended development deployment. Azure remains an optional later migration path and should not be deployed simultaneously.

## 1 Create the GitHub repository

Use a public repository if you want scheduled GitHub-hosted Actions to remain free without consuming private-repository minutes. Runtime files, credentials, `.tools`, logs and local data are ignored. Push branch `main`, then enable Actions.

## 2 Create Cloudflare R2

Create an R2 bucket named `victorian-home-medallion`. Create a bucket-scoped API token with object read/write permission only. Record its S3 endpoint, access-key ID and secret once; never commit them.

GitHub secrets:

- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

GitHub variable:

- `R2_BUCKET=victorian-home-medallion`

R2 stores Bronze, Silver, Gold, alert state and weekly Supabase dumps. Add a lifecycle rule later if retained workbooks approach the free storage limit. Do not make the bucket public.

## 3 Create Supabase

Create one Free project in the closest acceptable region. In the SQL Editor, execute `supabase/migrations/001_gold_schema.sql`. Obtain a PostgreSQL connection string intended for server-side use. Prefer the session pooler when GitHub cannot reach the direct IPv6 endpoint.

Create a dedicated ETL database role with only usage/write access to `mart` and `audit`, and a separate dashboard login with only `USAGE` on `mart` and `SELECT` on `mart.vw_dashboard_roi`. Generate long random passwords in Supabase; store connection URLs only in the relevant secret store.

GitHub secret:

- `SUPABASE_DB_URL` — ETL writer connection, never an anonymous browser key

The workflow uses a staging table and one database transaction. Empty ROI output is rejected, so a bad refresh cannot erase the last published dashboard snapshot.

## 4 Configure Resend

Verify a sender domain in Resend. Add `RESEND_API_KEY` as a GitHub secret. Add `ALERT_TO_EMAIL`, `ALERT_FROM_EMAIL`, and `ALERT_DRY_RUN=true` as repository variables. Run manually and inspect logs before changing dry-run to `false`.

Email is content-hash idempotent. An unchanged ROI screen does not generate another message.

## 5 Load the official VGV history

The publisher currently blocks automated workbook download. Download the house, unit and land workbooks through its website and upload them to the private R2 prefix `manual-input/vgv/` with the canonical names `houses.xlsx`, `units.xlsx`, and `land.xlsx`. The next scheduled refresh detects a complete, previously unseen set and promotes it through Bronze and Silver before rebuilding Gold.

For local development, the equivalent command is:

```bash
home-data run --source vgv_annual_sales --input-dir ./manual-input/vgv
home-data build-official-gold
home-data build-roi
```

Then use the same R2 credentials locally to upload the medallion folder, or trigger the project sync after adding a controlled upload command. Do not upload the small regression fixtures as production history.

## 6 Test scheduled ingestion

Open GitHub Actions and manually run `free-cloud-refresh`. Expected first-run status is `rental_only` until official VGV Silver history exists. After VGV exists, expected status is `published`. Download the seven-day failure-log artifact if the job fails.

The schedule is minute 17 every 12 hours in UTC. GitHub schedules can be delayed during platform load, so this is near-real-time monitoring rather than a hard real-time guarantee.

## 7 Deploy Streamlit

Connect Streamlit Community Cloud to the GitHub repository and choose `streamlit_app.py`. Community Cloud installs `requirements.txt`, which selects the project's `free-cloud` dependency group. Add `SUPABASE_DB_URL` to Streamlit secrets using the read-only dashboard connection, not the ETL connection. The app caches queries for one hour and never writes to PostgreSQL.

## 8 Backups and recovery

Manually run `backup-supabase` once and verify a dated custom-format dump under `backups/supabase/` in R2. The workflow repeats weekly. Periodically test restoration into a disposable Supabase project; an untested backup is not a recovery plan.

## 9 Free-tier guardrails

- Keep Supabase Gold curated and exclude Bronze/Silver payloads.
- Keep R2 private and monitor stored bytes and operations.
- Set GitHub spending limits and review Actions usage.
- Never log database URLs, R2 secrets or Resend credentials.
- Export data before deleting or recreating any free-tier project.
