import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


def load_roi_to_postgres(database_url: str, roi_path: Path, unmatched_path: Path) -> dict[str, int]:
    """Transactionally upsert Gold outputs into Supabase-compatible PostgreSQL."""
    import psycopg

    roi = pd.read_parquet(roi_path).copy()
    unmatched = pd.read_parquet(unmatched_path).copy()
    roi_columns = [
        "canonical_suburb_key",
        "property_type",
        "bedrooms",
        "observation_date",
        "period_end",
        "median_price",
        "median_weekly_rent",
        "estimated_gross_yield_pct",
        "price_growth_cagr_pct",
        "indicative_score",
        "match_quality",
        "score_version",
    ]
    roi = roi[roi_columns].rename(
        columns={"observation_date": "price_observation_date", "period_end": "rent_period_end"}
    )
    roi = roi.astype(object).where(pd.notna(roi), None)
    unmatched = unmatched.astype(object).where(pd.notna(unmatched), None)
    with psycopg.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE mart.suburb_roi_screen_stage")
        with cursor.copy(
            "COPY mart.suburb_roi_screen_stage "
            "(canonical_suburb_key, property_type, bedrooms, price_observation_date, "
            "rent_period_end, median_price, median_weekly_rent, estimated_gross_yield_pct, "
            "price_growth_cagr_pct, indicative_score, match_quality, score_version) FROM STDIN"
        ) as copy:
            for row in roi.itertuples(index=False, name=None):
                copy.write_row(row)
        cursor.execute("SELECT mart.publish_roi_screen()")
        cursor.execute("TRUNCATE audit.unmatched_geography")
        if not unmatched.empty:
            with cursor.copy(
                "COPY audit.unmatched_geography (source, source_suburb, canonical_suburb_key) "
                "FROM STDIN"
            ) as copy:
                for row in unmatched[["source", "suburb", "canonical_suburb_key"]].itertuples(
                    index=False, name=None
                ):
                    copy.write_row(row)
    counts = {"roi": len(roi), "unmatched": len(unmatched)}
    LOGGER.info("Supabase Gold load complete", extra={"stage": "gold", "rows": len(roi)})
    return counts
