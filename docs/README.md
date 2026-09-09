# Documentation index

Use this page as the entry point for the project documentation.

| Document | Read it when you need to… |
|---|---|
| [Architecture and decisions](architecture.md) | Understand the system, technology choices and failure boundaries |
| [Medallion architecture](medallion-architecture.md) | Understand Bronze, Silver, Gold, paths and promotion rules |
| [Data model and metrics](data-model.md) | Query the products or interpret yield, growth and score fields |
| [Free-cloud deployment](free-cloud-deployment.md) | Configure R2, Supabase, GitHub Actions, Resend and Streamlit |
| [Watchlists and alerts](watchlists-and-alerts.md) | Per-user RLS, thresholds, delivery audit and least-privilege access |
| [Operations runbook](operations-runbook.md) | Run, verify, recover or update the production pipeline |
| [Implementation guide](implementation-guide.md) | Build and exercise the project step by step |
| [Logging and errors](logging-and-errors.md) | Investigate JSONL logs and common failures |
| [Security and access](security-and-access.md) | Apply least privilege and manage secrets safely |
| [Power BI guide](powerbi-guide.md) | Build the interactive analytical report |
| [Optional Azure runbook](deployment-runbook.md) | Migrate to the enterprise Azure design |

## Recommended reading order

1. Root `README.md`
2. Architecture and decisions
3. Medallion architecture
4. Data model and metrics
5. Free-cloud deployment
6. Operations runbook

## Documentation conventions

- “Current” means the GitHub Actions + R2 + Supabase deployment.
- “Optional Azure” means a future migration path, not an active dependency.
- Runtime data and logs are deliberately absent from Git; R2 and workflow artifacts hold operational evidence.
- Dates and row counts describe verified runs and are not promises about publisher cadence.
