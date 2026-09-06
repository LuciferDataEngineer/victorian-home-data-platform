# Security and access

## Current free-cloud model

| Principal | Access |
|---|---|
| GitHub Actions ETL | Read/write only to the selected R2 bucket; write to Supabase `mart` and `audit` |
| Dashboard | Read-only access to `mart.vw_dashboard_roi` |
| Repository users | Code and documentation; no runtime secrets or raw data |
| Supabase `anon` / `authenticated` | No direct access to the private `mart` schema |
| Human administrator | Cloud-console administration with MFA |

## Secret locations

GitHub repository secrets:

- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `SUPABASE_DB_URL`
- `RESEND_API_KEY` when alerts are enabled

Repository variables contain non-secret configuration such as `R2_BUCKET`, alert addresses and `ALERT_DRY_RUN`. `.env` is for local development only and is ignored by Git.

Never paste connection strings or access keys into code, workflow logs, issues, commits or dashboard client code. Rotate a secret immediately if it appears in any of those places.

## Database controls

- PostgreSQL constraints enforce property types, bedroom range, positive prices and bounded yields.
- The ETL publishes through a staging table and guarded database function.
- Dashboard credentials must not have insert, update, delete, truncate or function-execution privileges.
- Prefer Supabase’s server-side pooler connection for GitHub Actions; never expose it as a browser environment variable.

## Storage controls

- Keep `victorian-home-medallion` private.
- Scope R2 tokens to this bucket and object read/write only.
- Store Bronze/Silver/Gold data in R2, not the public repository.
- Periodically test the Supabase backup workflow and recovery procedure.

## Optional Azure identity model

For Azure migration, replace long-lived workload credentials with GitHub OIDC and managed identities. Use Key Vault for external secrets, Microsoft Entra groups for people, ADLS RBAC by layer, and a separate read-only Power BI database principal. The Bicep and SQL migration folders provide the starting design.

## Access review checklist

- Review GitHub collaborators and Actions permissions.
- Review R2 API tokens and last-used dates.
- Review Supabase database roles and active connections.
- Confirm the R2 bucket remains non-public.
- Confirm logs and artifacts contain no secrets.
- Remove unused credentials and rotate production credentials periodically.
