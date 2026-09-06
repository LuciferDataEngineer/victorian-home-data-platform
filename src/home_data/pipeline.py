import logging
import re
from pathlib import Path

import pandas as pd

from home_data.geography import apply_crosswalk, load_manual_crosswalk
from home_data.models import BronzeManifest, QualityResult
from home_data.sources import ADAPTERS, HomesVictoriaRentalAdapter, VgvAnnualSalesAdapter
from home_data.storage import LocalMedallionStore

REQUIRED = {
    "sample_sales": {"suburb", "lga", "property_type", "period", "median_price", "sales_count"},
    "sample_rents": {"suburb", "lga", "property_type", "period", "median_weekly_rent"},
    "homes_victoria_rents": {
        "suburb",
        "rental_region",
        "property_type",
        "bedrooms",
        "period_end",
        "median_weekly_rent",
        "bond_count",
    },
}
LOGGER = logging.getLogger(__name__)


def ingest_source(
    source: str, store: LocalMedallionStore, input_dir: Path | None = None
) -> list[BronzeManifest]:
    if source not in ADAPTERS:
        raise ValueError(f"Unknown source: {source}")
    LOGGER.info("Starting extraction", extra={"source": source, "stage": "extract"})
    manifests = []
    if source == "vgv_annual_sales" and input_dir:
        adapter = VgvAnnualSalesAdapter(local_dir=input_dir)
    elif source == "homes_victoria_rents" and input_dir:
        adapter = HomesVictoriaRentalAdapter(local_dir=input_dir)
    else:
        adapter = ADAPTERS[source]()
    for payload in adapter.extract():
        manifest = store.land_bronze(payload)
        manifests.append(manifest)
        LOGGER.info(
            "Payload landed in Bronze",
            extra={
                "run_id": manifest.run_id,
                "source": source,
                "entity": payload.entity,
                "stage": "bronze",
                "object_path": manifest.object_path,
            },
        )
        frame = parse_payload(source, payload.entity, Path(manifest.object_path))
        results = validate_frame(source, frame)
        failures = [r for r in results if not r.passed and r.severity == "critical"]
        if failures:
            raise ValueError("; ".join(result.message for result in failures))
        silver_path = (
            store.data_root
            / "silver"
            / payload.domain
            / payload.entity
            / f"observation_year={payload.observation_date[:4]}"
            / f"run_id={manifest.run_id}.parquet"
        )
        silver_path.parent.mkdir(parents=True, exist_ok=True)
        frame.assign(
            source_id=source,
            run_id=manifest.run_id,
            publication_date=payload.publication_date,
        ).to_parquet(silver_path, index=False)
        LOGGER.info(
            "Dataset promoted to Silver",
            extra={
                "run_id": manifest.run_id,
                "source": source,
                "entity": payload.entity,
                "stage": "silver",
                "rows": len(frame),
                "object_path": str(silver_path),
            },
        )
    return manifests


def parse_payload(source: str, entity: str, path: Path) -> pd.DataFrame:
    if source == "vgv_annual_sales":
        property_type = entity.removeprefix("suburb_sales_")
        return parse_vgv_annual_workbook(path, property_type)
    if source == "homes_victoria_rents":
        return parse_homes_victoria_rent_workbook(path)
    return pd.read_csv(path)


def parse_homes_victoria_rent_workbook(path: Path) -> pd.DataFrame:
    """Convert repeated Count/Median quarter columns into canonical long form."""
    sheets = pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")
    frames = []
    sheet_pattern = re.compile(
        r"^(?:(\d+) bedroom )?(flat|house|All properties)$", re.IGNORECASE
    )
    for sheet_name, raw in sheets.items():
        match = sheet_pattern.match(sheet_name.strip())
        if not match or len(raw) < 4:
            continue
        bedrooms = int(match.group(1)) if match.group(1) else pd.NA
        kind = match.group(2).lower()
        property_type = "unit" if kind == "flat" else kind.replace(" properties", "")
        regions = raw.iloc[3:, 0].ffill().astype("string").str.strip()
        suburbs = raw.iloc[3:, 1].astype("string").str.strip().str.upper()
        columns = []
        for index in range(2, raw.shape[1]):
            metric = str(raw.iloc[2, index]).strip().lower()
            period = str(raw.iloc[1, index]).strip()
            if metric in {"count", "median"} and re.fullmatch(r"[A-Z][a-z]{2} 20\d{2}", period):
                columns.append((index, period, metric))
        periods = sorted({period for _, period, _ in columns})
        for period in periods:
            metric_columns = {metric: index for index, label, metric in columns if label == period}
            if "median" not in metric_columns:
                continue
            frame = pd.DataFrame(
                {
                    "suburb": suburbs,
                    "rental_region": regions,
                    "property_type": property_type,
                    "bedrooms": bedrooms,
                    "period_end": pd.Period(period, freq="Q").end_time.normalize(),
                    "median_weekly_rent": pd.to_numeric(
                        raw.iloc[3:, metric_columns["median"]], errors="coerce"
                    ).array,
                    "bond_count": pd.to_numeric(
                        raw.iloc[3:, metric_columns["count"]], errors="coerce"
                    ).array
                    if "count" in metric_columns
                    else pd.NA,
                }
            )
            frames.append(frame.dropna(subset=["suburb", "median_weekly_rent"]))
    if not frames:
        raise ValueError("No Homes Victoria rent tables found; workbook contract may have changed")
    result = pd.concat(frames, ignore_index=True)
    result = result[
        ~result["suburb"].isin({"<NA>", "NAN", "VICTORIA"})
        & ~result["suburb"].str.endswith("TOTAL")
    ]
    return result.drop_duplicates(
        ["suburb", "property_type", "bedrooms", "period_end"], keep="last"
    )


def parse_vgv_annual_workbook(path: Path, property_type: str) -> pd.DataFrame:
    """Convert a VGV wide annual workbook to canonical long-form observations.

    The parser searches every sheet for a header containing a suburb/locality column and
    four-digit year columns. This is more resilient than relying on a fixed sheet or row.
    """
    sheets = pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")
    frames = []
    for sheet_name, raw in sheets.items():
        header_index = None
        for index, row in raw.head(40).iterrows():
            values = [str(value).strip().lower() for value in row.tolist()]
            if any(value in {"suburb", "locality", "suburb/town"} for value in values):
                header_index = index
                break
        if header_index is None:
            continue
        frame = pd.read_excel(path, sheet_name=sheet_name, header=header_index, engine="openpyxl")
        frame.columns = [str(column).strip() for column in frame.columns]
        suburb_column = next(
            (c for c in frame.columns if c.lower() in {"suburb", "locality", "suburb/town"}),
            None,
        )
        if suburb_column is None:
            continue
        year_columns = [c for c in frame.columns if re.fullmatch(r"20\d{2}", str(c))]
        if not year_columns:
            continue
        long = frame.melt(
            id_vars=[suburb_column], value_vars=year_columns, var_name="period", value_name="median_price"
        ).rename(columns={suburb_column: "suburb"})
        long["suburb"] = long["suburb"].astype(str).str.strip().str.upper()
        long["median_price"] = pd.to_numeric(long["median_price"], errors="coerce")
        long["period"] = pd.to_numeric(long["period"], errors="coerce").astype("Int64")
        long = long.dropna(subset=["suburb", "median_price", "period"])
        long = long[~long["suburb"].isin({"NAN", "TOTAL", "VICTORIA"})]
        long["property_type"] = property_type
        long["sales_count"] = pd.NA
        long["lga"] = pd.NA
        frames.append(long[["suburb", "lga", "property_type", "period", "median_price", "sales_count"]])
    if not frames:
        raise ValueError("No VGV suburb/year table found; publisher workbook contract may have changed")
    return pd.concat(frames, ignore_index=True).drop_duplicates(
        ["suburb", "property_type", "period"], keep="last"
    )


def validate_frame(source: str, frame: pd.DataFrame) -> list[QualityResult]:
    contract_source = "sample_sales" if source == "vgv_annual_sales" else source
    missing = REQUIRED[contract_source] - set(frame.columns)
    results = [
        QualityResult(
            check_name="required_columns",
            passed=not missing,
            severity="critical",
            message="Required columns present" if not missing else f"Missing columns: {sorted(missing)}",
        ),
        QualityResult(
            check_name="non_empty",
            passed=not frame.empty,
            severity="critical",
            message=f"Rows: {len(frame)}",
        ),
    ]
    return results


def build_gold(data_root: Path) -> Path:
    sales_files = list((data_root / "silver" / "property_market" / "suburb_sales").rglob("*.parquet"))
    rent_files = list((data_root / "silver" / "rental_market" / "suburb_rents").rglob("*.parquet"))
    if not sales_files or not rent_files:
        raise ValueError("Run both sample_sales and sample_rents before building Gold")
    sales = pd.concat([pd.read_parquet(path) for path in sales_files]).drop_duplicates(
        ["suburb", "property_type", "period"], keep="last"
    )
    rents = pd.concat([pd.read_parquet(path) for path in rent_files]).drop_duplicates(
        ["suburb", "property_type", "period"], keep="last"
    )
    mart = sales.merge(
        rents,
        on=["suburb", "lga", "property_type", "period"],
        suffixes=("_sales", "_rents"),
        validate="one_to_one",
    )
    mart["estimated_gross_yield_pct"] = (
        mart["median_weekly_rent"] * 52 / mart["median_price"] * 100
    ).round(2)
    mart["liquidity_confidence"] = pd.cut(
        mart["sales_count"], bins=[-1, 24, 99, float("inf")], labels=["low", "medium", "high"]
    )
    path = data_root / "gold" / "mart_suburb_snapshot.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    mart.to_parquet(path, index=False)
    mart.to_csv(path.with_suffix(".csv"), index=False)
    LOGGER.info(
        "Gold mart built",
        extra={"stage": "gold", "rows": len(mart), "object_path": str(path)},
    )
    return path


def build_official_gold(data_root: Path) -> list[Path]:
    """Publish source-faithful official histories without inventing a grain-crosswalk."""
    sales_files = list((data_root / "silver" / "property_market").glob("suburb_sales_*/*/*.parquet"))
    rent_files = list(
        (data_root / "silver" / "rental_market" / "moving_annual_rents_by_suburb").rglob(
            "*.parquet"
        )
    )
    if not sales_files or not rent_files:
        raise ValueError("Run vgv_annual_sales and homes_victoria_rents before official Gold")
    sales = pd.concat([pd.read_parquet(path) for path in sales_files], ignore_index=True)
    rents = pd.concat([pd.read_parquet(path) for path in rent_files], ignore_index=True)
    sales = sales.drop_duplicates(["suburb", "property_type", "period"], keep="last")
    rents = rents[~rents["suburb"].str.endswith("TOTAL")]
    rents = rents.drop_duplicates(
        ["suburb", "property_type", "bedrooms", "period_end"], keep="last"
    )
    gold = data_root / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    paths = [gold / "mart_vgv_price_history.parquet", gold / "mart_homes_rent_history.parquet"]
    for frame, path in zip((sales, rents), paths, strict=True):
        frame.to_parquet(path, index=False)
        frame.to_csv(path.with_suffix(".csv"), index=False)
        LOGGER.info(
            "Official Gold history built",
            extra={"stage": "gold", "rows": len(frame), "object_path": str(path)},
        )
    return paths


def build_roi_gold(data_root: Path, crosswalk_path: Path | None = None) -> list[Path]:
    """Build indicative yields only for conservative suburb/property-type matches."""
    price_path = data_root / "gold" / "mart_vgv_price_history.parquet"
    rent_path = data_root / "gold" / "mart_homes_rent_history.parquet"
    if not price_path.exists() or not rent_path.exists():
        raise ValueError("Run build-official-gold before building ROI")
    prices = pd.read_parquet(price_path)
    rents = pd.read_parquet(rent_path)
    manual = load_manual_crosswalk(crosswalk_path)
    for frame in (prices, rents):
        matches = frame["suburb"].map(lambda value: apply_crosswalk(value, manual))
        frame["canonical_suburb_key"] = matches.str[0]
        frame["geography_match_method"] = matches.str[1]

    prices = prices[prices["property_type"].isin(["house", "unit"])].copy()
    rents = rents[rents["property_type"].isin(["house", "unit"]) & rents["bedrooms"].notna()].copy()
    prices["observation_date"] = pd.to_datetime(prices["period"].astype(str) + "-12-31")
    prices = prices.sort_values("observation_date")
    history = prices.groupby(["canonical_suburb_key", "property_type"], observed=True)
    first = history.first()[["median_price", "observation_date"]].rename(
        columns={"median_price": "first_median_price", "observation_date": "first_price_date"}
    )
    latest_prices = history.last().reset_index()
    latest_prices = latest_prices.join(first, on=["canonical_suburb_key", "property_type"])
    years = (
        (latest_prices["observation_date"] - latest_prices["first_price_date"]).dt.days / 365.25
    )
    latest_prices["price_growth_cagr_pct"] = (
        ((latest_prices["median_price"] / latest_prices["first_median_price"]) ** (1 / years) - 1)
        * 100
    ).where(years >= 1)
    latest_rents = rents.sort_values("period_end").groupby(
        ["canonical_suburb_key", "property_type", "bedrooms"], observed=True
    ).last().reset_index()
    keys = ["canonical_suburb_key", "property_type"]
    candidates = latest_rents.merge(latest_prices, on=keys, suffixes=("_rent", "_price"))
    candidates["estimated_gross_yield_pct"] = (
        candidates["median_weekly_rent"] * 52 / candidates["median_price"] * 100
    ).round(3)
    candidates["yield_basis"] = "moving-annual bedroom rent / annual property-type price"
    candidates["is_investment_advice"] = False
    candidates["match_quality"] = "exact_or_reviewed"
    candidates["score_version"] = "roi_screen_v1"
    candidates["indicative_score"] = (
        candidates["estimated_gross_yield_pct"].rank(pct=True) * 60
        + candidates["price_growth_cagr_pct"].rank(pct=True) * 40
    ).round(2)

    matched = set(candidates["canonical_suburb_key"])
    unmatched = pd.concat(
        [
            prices.loc[~prices["canonical_suburb_key"].isin(matched), ["suburb", "canonical_suburb_key"]]
            .assign(source="vgv_annual_sales"),
            rents.loc[~rents["canonical_suburb_key"].isin(matched), ["suburb", "canonical_suburb_key"]]
            .assign(source="homes_victoria_rents"),
        ],
        ignore_index=True,
    ).drop_duplicates()
    gold = data_root / "gold"
    paths = [gold / "mart_suburb_roi_screen.parquet", gold / "dq_unmatched_geographies.parquet"]
    for frame, path in zip((candidates, unmatched), paths, strict=True):
        frame.to_parquet(path, index=False)
        frame.to_csv(path.with_suffix(".csv"), index=False)
        LOGGER.info(
            "ROI Gold product built",
            extra={"stage": "gold", "rows": len(frame), "object_path": str(path)},
        )
    return paths
