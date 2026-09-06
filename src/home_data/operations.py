import logging
import os
from pathlib import Path

from home_data.alerts import send_gold_change_alert
from home_data.pipeline import build_official_gold, build_roi_gold, ingest_source
from home_data.postgres_loader import load_roi_to_postgres
from home_data.r2_sync import R2MedallionSync
from home_data.storage import LocalMedallionStore

LOGGER = logging.getLogger(__name__)


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def run_free_cloud_refresh(data_root: Path) -> str:
    sync = R2MedallionSync(
        _required("R2_ENDPOINT_URL"),
        _required("R2_BUCKET"),
        _required("R2_ACCESS_KEY_ID"),
        _required("R2_SECRET_ACCESS_KEY"),
    )
    sync.download(data_root)
    store = LocalMedallionStore(data_root)
    store.initialise()
    ingest_source("homes_victoria_rents", store)
    sales_files = list((data_root / "silver" / "property_market").glob("suburb_sales_*/*/*.parquet"))
    if not sales_files:
        LOGGER.warning(
            "Gold publish skipped; upload official VGV Silver history first",
            extra={"stage": "gold"},
        )
        sync.upload(data_root)
        return "rental_only"
    build_official_gold(data_root)
    roi_path, unmatched_path = build_roi_gold(data_root, Path("config/geography_crosswalk.csv"))
    load_roi_to_postgres(_required("SUPABASE_DB_URL"), roi_path, unmatched_path)
    send_gold_change_alert(
        roi_path,
        data_root / "meta" / "last_alert.json",
        api_key=os.getenv("RESEND_API_KEY"),
        to_email=os.getenv("ALERT_TO_EMAIL"),
        from_email=os.getenv("ALERT_FROM_EMAIL", "alerts@example.invalid"),
        dry_run=os.getenv("ALERT_DRY_RUN", "true").lower() == "true",
    )
    sync.upload(data_root)
    return "published"
