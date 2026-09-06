# Logging and error operations

## Log locations

- Local structured pipeline log: `logs/pipeline.jsonl`
- Rotated files: `logs/pipeline.jsonl.1` through `.10`
- Azure destination: Application Insights and Log Analytics
- Data-quality history after SQL integration: `audit.data_quality_result`

Log files are ignored by Git. `logs/.gitkeep` preserves the directory.

## Event fields

Every event has `timestamp`, `level`, `logger` and `message`. Pipeline events may include `run_id`, `source`, `entity`, `stage`, `rows` and `object_path`. Exceptions include a stack trace in `exception`.

Never log API keys, access tokens, connection strings, email recipients or complete HTTP authorization headers.

## Common checks

```bash
tail -n 50 logs/pipeline.jsonl
grep '"level": "ERROR"' logs/pipeline.jsonl
grep '"source": "vgv_annual_sales"' logs/pipeline.jsonl
```

If `jq` is installed:

```bash
jq 'select(.level == "ERROR")' logs/pipeline.jsonl
jq -s 'group_by(.stage) | map({stage: .[0].stage, events: length})' logs/pipeline.jsonl
```

## Triage sequence

1. Find the newest ERROR event and its run ID.
2. Read earlier events with the same run ID to locate the failed stage.
3. Confirm the official publisher URL and release metadata.
4. Inspect the Bronze manifest and payload size without editing the payload.
5. Reproduce against a copied fixture or temporary directory.
6. Add a regression test before changing a parser or contract.
7. Rerun the same source. A new run ID is expected; Gold remains unchanged until validation passes.

## Expected error categories

- HTTP 403/404: publisher access rule or moved resource. Confirm the landing page; do not bypass access controls.
- Timeout/429/5xx: retry with exponential backoff and jitter; respect Retry-After.
- Workbook contract failure: sheet/header/year layout changed. Quarantine and update the parser with a fixture.
- Missing required columns: block promotion and compare source schema to the contract.
- Duplicate business grain: investigate revisions/crosswalks before choosing a survivor rule.
- Gold merge failure: rollback and keep the previous certified snapshot.
- Alert dry run: expected until Resend sender verification is complete.
- Alert unchanged: expected idempotency suppression; no email is sent.
- Cloud sync failure: keep the prior Blob copy, inspect managed-identity roles and retry.

## Rotation and retention

Local logs rotate at 10 MB with ten backups. In Azure, configure a cost-conscious Log Analytics retention period and sampling only for high-volume informational events. Retain ERROR, promotion, audit and security events according to the project policy.
