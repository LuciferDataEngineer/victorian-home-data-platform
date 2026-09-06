# Operations runbook

## Normal schedule

`.github/workflows/free-cloud-refresh.yml` runs at minute 17 every 12 hours UTC and also supports manual dispatch. Publisher cadence is annual for VGV and quarterly for Homes Victoria; the schedule is a freshness check, not real-time source generation.

## Manual production refresh

1. Open GitHub → Actions → `free-cloud-refresh`.
2. Choose **Run workflow** on `main`.
3. Wait for **Refresh medallion and publish Gold** to complete.
4. Confirm the final message is `Free-cloud refresh completed: published`.
5. If it fails, download the `pipeline-failure-logs` artifact.

Command-line equivalent for an authenticated GitHub CLI:

```bash
gh workflow run free-cloud-refresh.yml
gh run list --workflow free-cloud-refresh.yml --limit 5
```

## Annual VGV update

1. Download the three current publisher workbooks through the official page.
2. Validate that they are Excel workbooks and record their SHA-256 hashes.
3. Upload them privately to `manual-input/vgv/` using exactly:
   - `houses.xlsx`
   - `units.xlsx`
   - `land.xlsx`
4. Run the workflow manually.
5. Confirm logs say `New complete VGV manual input set detected`.
6. Confirm all three entities are promoted to Silver and Supabase Gold load completes.

Do not remove the previous certified medallion data during an update. A complete successful run writes a new immutable Bronze version.

## Verification queries

```sql
select count(*) from mart.suburb_roi_screen;
select max(published_at) from mart.suburb_roi_screen;
select property_type, count(*)
from mart.suburb_roi_screen
group by property_type;
select source, count(*)
from audit.unmatched_geography
group by source;
```

Also confirm that the R2 bucket contains `bronze/`, `silver/`, `gold/`, `manual-input/` and expected backup objects.

## Failure triage

| Symptom | Likely cause | Action |
|---|---|---|
| R2 sync fails | Endpoint, bucket or token mismatch | Check secret names, bucket scope and endpoint format |
| VGV is not detected | Missing/misnamed file or unchanged hashes | Verify all three canonical names and hashes |
| Parser fails | Publisher layout changed | Preserve Bronze, add a regression fixture, update parser and rerun tests |
| `rental_only` | No VGV Silver history exists | Upload complete official VGV input set |
| PostgreSQL COPY fails | Dataframe/DB type mismatch | Inspect column named in error; add boundary regression test |
| Empty publish rejected | Matching or upstream quality removed all rows | Inspect Gold histories and unmatched-geography output; do not bypass guard |
| No email | Dry-run enabled, missing Resend configuration or unchanged hash | Check variables and alert log status |

## Local validation before push

```bash
source .venv/bin/activate
ruff check src tests
pytest -q
git diff --check
```

For local VGV validation:

```bash
home-data run \
  --source vgv_annual_sales \
  --input-dir ./manual-input/vgv \
  --data-root ./data
```

## Recovery principles

- Never overwrite or edit Bronze evidence.
- Do not truncate the published Gold table manually during an incident.
- Fix code or configuration, validate locally, then rerun from preserved inputs.
- Restore Supabase from the latest tested R2 backup only when transactional replay is insufficient.
- Document material incidents and their corrective tests in the repository.

See [logging and errors](logging-and-errors.md) for JSONL fields and investigation commands.
