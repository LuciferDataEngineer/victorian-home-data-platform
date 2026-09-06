import hashlib
import json
import logging
import os
from pathlib import Path

from home_data.alerts import send_gold_change_alert
from home_data.pipeline import build_official_gold, build_roi_gold, ingest_source
from home_data.postgres_loader import load_roi_to_postgres
from home_data.r2_sync import R2MedallionSync
from home_data.storage import LocalMedallionStore

LOGGER = logging.getLogger(__name__)

VGV_MANUAL_INPUTS = ("houses.xlsx", "units.xlsx", "land.xlsx")


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def _manual_vgv_inputs_changed(data_root: Path) -> bool:
    """Return true only when a complete, previously unseen VGV set is present."""
    input_dir = data_root / "manual-input" / "vgv"
    paths = [input_dir / name for name in VGV_MANUAL_INPUTS]
    if not all(path.is_file() for path in paths):
        return False

    known_hashes: set[str] = set()
    bronze_root = data_root / "bronze" / "vgv_annual_sales"
    for manifest_path in bronze_root.glob("**/manifest.json"):
        try:
            known_hashes.add(json.loads(manifest_path.read_text(encoding="utf-8"))["sha256"])
        except (OSError, KeyError, json.JSONDecodeError):
            LOGGER.warning(
                "Ignoring unreadable Bronze manifest",
                extra={"stage": "bronze", "object_path": str(manifest_path)},
            )

    current_hashes = {
        hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }
    return not current_hashes.issubset(known_hashes)


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
    manual_vgv_dir = data_root / "manual-input" / "vgv"
    if _manual_vgv_inputs_changed(data_root):
        LOGGER.info(
            "New complete VGV manual input set detected",
            extra={"stage": "extract", "object_path": str(manual_vgv_dir)},
        )
        ingest_source("vgv_annual_sales", store, manual_vgv_dir)
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
