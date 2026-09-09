# Personal watchlists and alerts

Authenticated users can save suburb, property-type and bedroom cohorts with minimum yield, minimum score and maximum price thresholds. The browser calls Supabase PostgREST with the user's access token. Row-level security ensures users can only access their own records.

Apply `supabase/migrations/002_watchlists_and_access.sql` in the Supabase SQL editor before using the feature. The migration also creates an append-only alert-delivery audit table and a reusable `dashboard_reader` role with access only to the certified Gold view.

The service-side evaluator runs after each successful Gold publication, sends through Resend only when all configured thresholds match, and inserts the metric fingerprint into `audit.user_alert_delivery`. The composite primary key makes delivery idempotent for a watchlist and certified metric state. Recipient email addresses are never written to logs; only a one-way hash is stored in the audit table.

Keep `ALERT_DRY_RUN=true` until a Resend sending domain and `ALERT_FROM_EMAIL` are verified. Add `DASHBOARD_URL` as a GitHub Actions variable. After a dry run appears in the audit table, set `ALERT_DRY_RUN=false`; dry-run records are safely promoted to `sent` on the next evaluation.

For production hardening, create a login role that inherits `dashboard_reader` and store that role's connection string as `SUPABASE_DB_URL` in Streamlit. Keep the ETL publication credential only in GitHub Actions.
