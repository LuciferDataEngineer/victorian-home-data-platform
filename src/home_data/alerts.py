import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlertResult:
    status: str
    fingerprint: str


def file_fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def send_gold_change_alert(
    gold_path: Path,
    state_path: Path,
    *,
    api_key: str | None,
    to_email: str | None,
    from_email: str,
    dry_run: bool = True,
    client: httpx.Client | None = None,
) -> AlertResult:
    """Send at most one email per Gold content hash and persist state after success."""
    fingerprint = file_fingerprint(gold_path)
    previous = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    if previous.get("fingerprint") == fingerprint:
        LOGGER.info("Alert suppressed; Gold content unchanged", extra={"stage": "alert"})
        return AlertResult("unchanged", fingerprint)
    if dry_run:
        LOGGER.info("Alert dry run", extra={"stage": "alert", "object_path": str(gold_path)})
        return AlertResult("dry_run", fingerprint)
    if not api_key or not to_email:
        raise ValueError("RESEND_API_KEY and ALERT_TO_EMAIL are required when dry-run is disabled")
    response = (client or httpx.Client(timeout=30)).post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_email,
            "to": [to_email],
            "subject": "Victorian home data: ROI screen updated",
            "html": (
                "<p>The governed ROI screening dataset changed.</p>"
                f"<p>Fingerprint: <code>{fingerprint[:12]}</code></p>"
                "<p>Review freshness, match quality and methodology before acting.</p>"
            ),
        },
    )
    response.raise_for_status()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"fingerprint": fingerprint}), encoding="utf-8")
    LOGGER.info("Change alert sent", extra={"stage": "alert"})
    return AlertResult("sent", fingerprint)
