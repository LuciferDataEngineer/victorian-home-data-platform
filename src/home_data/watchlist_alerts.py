import hashlib
import html
import json
import logging
from dataclasses import dataclass

import httpx
import psycopg
from psycopg.rows import dict_row

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WatchlistAlertSummary:
    matched: int
    sent: int
    suppressed: int
    dry_run: int


MATCH_QUERY = """
select
    w.id as watchlist_id, u.email, r.canonical_suburb_key, r.property_type, r.bedrooms,
    r.median_price, r.estimated_gross_yield_pct, r.indicative_score, r.published_at
from public.user_watchlists w
join auth.users u on u.id = w.user_id
join mart.vw_dashboard_roi r
  on r.canonical_suburb_key = w.canonical_suburb_key
 and r.property_type = w.property_type
 and r.bedrooms = w.bedrooms
where w.enabled
  and (w.min_gross_yield_pct is null or r.estimated_gross_yield_pct >= w.min_gross_yield_pct)
  and (w.min_score is null or r.indicative_score >= w.min_score)
  and (w.max_median_price is null or r.median_price <= w.max_median_price)
"""


def _fingerprint(row: dict) -> str:
    values = {
        key: str(row[key])
        for key in (
            "watchlist_id",
            "median_price",
            "estimated_gross_yield_pct",
            "indicative_score",
            "published_at",
        )
    }
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def evaluate_watchlist_alerts(
    database_url: str,
    *,
    api_key: str | None,
    from_email: str,
    dashboard_url: str,
    dry_run: bool = True,
    client: httpx.Client | None = None,
) -> WatchlistAlertSummary:
    sender = client or httpx.Client(timeout=30)
    sent = suppressed = dry_run_count = 0
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        rows = connection.execute(MATCH_QUERY).fetchall()
        for row in rows:
            fingerprint = _fingerprint(row)
            previous = connection.execute(
                "select status from audit.user_alert_delivery "
                "where watchlist_id = %s and metric_fingerprint = %s",
                (row["watchlist_id"], fingerprint),
            ).fetchone()
            if previous and previous["status"] == "sent":
                suppressed += 1
                continue
            recipient_hash = hashlib.sha256(row["email"].lower().encode()).hexdigest()
            status = "dry_run"
            provider_message_id = None
            if dry_run:
                dry_run_count += 1
            else:
                if not api_key:
                    raise ValueError("RESEND_API_KEY is required when alert dry-run is disabled")
                response = sender.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "from": from_email,
                        "to": [row["email"]],
                        "subject": f"Property alert: {row['canonical_suburb_key']}",
                        "html": (
                            f"<p><strong>{html.escape(row['canonical_suburb_key'])}</strong> now "
                            "matches your saved thresholds.</p>"
                            f"<ul><li>Median price: A${row['median_price']:,.0f}</li>"
                            f"<li>Gross yield: {row['estimated_gross_yield_pct']:.2f}%</li>"
                            f"<li>Indicative score: {row['indicative_score']:.1f}</li></ul>"
                            f"<p><a href=\"{html.escape(dashboard_url)}\">Open dashboard</a></p>"
                            "<p>Indicative screening only; not financial advice.</p>"
                        ),
                    },
                )
                response.raise_for_status()
                provider_message_id = response.json().get("id")
                status = "sent"
                sent += 1
            connection.execute(
                """
                insert into audit.user_alert_delivery
                    (watchlist_id, metric_fingerprint, recipient_hash, status, provider_message_id)
                values (%s, %s, %s, %s, %s)
                on conflict (watchlist_id, metric_fingerprint) do update set
                    recipient_hash = excluded.recipient_hash,
                    status = excluded.status,
                    provider_message_id = excluded.provider_message_id,
                    error_message = null,
                    evaluated_at = now()
                """,
                (row["watchlist_id"], fingerprint, recipient_hash, status, provider_message_id),
            )
        connection.commit()
    LOGGER.info(
        "Watchlist alerts evaluated",
        extra={"stage": "alert", "row_count": len(rows), "status": "complete"},
    )
    return WatchlistAlertSummary(len(rows), sent, suppressed, dry_run_count)
