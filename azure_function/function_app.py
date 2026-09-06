import logging
import os
from pathlib import Path

import azure.functions as func

from home_data.alerts import send_gold_change_alert
from home_data.cloud_sync import sync_blob_prefix_down, sync_blob_prefix_up
from home_data.logging_config import configure_logging
from home_data.pipeline import build_official_gold, build_roi_gold, ingest_source
from home_data.secrets import get_secret
from home_data.storage import LocalMedallionStore

app = func.FunctionApp()
LOGGER = logging.getLogger(__name__)


def _workspace() -> tuple[Path, str, str]:
    root = Path("/tmp/victorian-home-data")
    account_url = os.environ["AZURE_STORAGE_ACCOUNT_URL"]
    container = os.getenv("MEDALLION_CONTAINER", "medallion")
    return root, account_url, container


@app.timer_trigger(schedule="0 17 */12 * * *", arg_name="timer", run_on_startup=False)
def refresh_rents(timer: func.TimerRequest) -> None:
    configure_logging()
    root, account_url, container = _workspace()
    sync_blob_prefix_down(account_url, container, root)
    store = LocalMedallionStore(root)
    store.initialise()
    ingest_source("homes_victoria_rents", store)
    price_history = root / "gold" / "mart_vgv_price_history.parquet"
    if price_history.exists():
        build_official_gold(root)
        paths = build_roi_gold(root, Path("config/geography_crosswalk.csv"))
        send_gold_change_alert(
            paths[0],
            root / "meta" / "last_alert.json",
            api_key=get_secret("RESEND_API_KEY", "resend-api-key"),
            to_email=get_secret("ALERT_TO_EMAIL", "alert-to-email"),
            from_email=get_secret("ALERT_FROM_EMAIL", "alert-from-email")
            or "alerts@example.invalid",
            dry_run=os.getenv("ALERT_DRY_RUN", "true").lower() == "true",
        )
    else:
        LOGGER.warning("ROI skipped; official VGV history is unavailable", extra={"stage": "gold"})
    sync_blob_prefix_up(account_url, container, root)
