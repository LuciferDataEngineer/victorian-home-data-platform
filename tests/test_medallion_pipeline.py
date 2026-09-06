import hashlib
import json

import httpx
import pandas as pd
from openpyxl import Workbook

from home_data.alerts import send_gold_change_alert
from home_data.geography import canonical_suburb_key
from home_data.operations import _manual_vgv_inputs_changed
from home_data.pipeline import (
    build_gold,
    build_roi_gold,
    ingest_source,
    parse_homes_victoria_rent_workbook,
    parse_vgv_annual_workbook,
    validate_frame,
)
from home_data.r2_sync import R2MedallionSync, normalise_r2_endpoint
from home_data.sources import HomesVictoriaRentalAdapter, VgvAnnualSalesAdapter
from home_data.storage import LocalMedallionStore


def test_bronze_is_immutable_and_manifested(tmp_path):
    store = LocalMedallionStore(tmp_path)
    store.initialise()
    manifest = ingest_source("sample_sales", store)[0]
    payload = tmp_path / manifest.object_path
    manifest_path = payload.parent / "manifest.json"
    assert payload.exists()
    assert manifest_path.exists()
    saved = json.loads(manifest_path.read_text())
    assert saved["sha256"] == manifest.sha256
    assert saved["bytes"] > 0


def test_quality_fails_missing_columns():
    results = validate_frame("sample_sales", pd.DataFrame({"suburb": ["TEST"]}))
    assert any(not result.passed and result.severity == "critical" for result in results)


def test_end_to_end_gold_yield(tmp_path):
    store = LocalMedallionStore(tmp_path)
    store.initialise()
    ingest_source("sample_sales", store)
    ingest_source("sample_rents", store)
    path = build_gold(tmp_path)
    mart = pd.read_parquet(path)
    assert set(mart["liquidity_confidence"].astype(str)) <= {"low", "medium", "high"}
    assert mart["estimated_gross_yield_pct"].between(0, 20).all()
    assert len(mart) == 4


def test_vgv_workbook_contract_parser(tmp_path):
    workbook = tmp_path / "vgv.xlsx"
    source = pd.DataFrame(
        {
            "Suburb": ["Ballarat Central", "Bendigo"],
            "2024": [590000, 570000],
            "2025": [610000, 590000],
        }
    )
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        source.to_excel(writer, sheet_name="House medians", index=False, startrow=3)
    parsed = parse_vgv_annual_workbook(workbook, "house")
    assert len(parsed) == 4
    assert set(parsed["property_type"]) == {"house"}
    assert parsed["median_price"].min() == 570000


def test_vgv_manual_drop_adapter(tmp_path):
    for name in ("houses.xlsx", "units.xlsx", "land.xlsx"):
        (tmp_path / name).write_bytes(b"workbook-bytes")
    payloads = VgvAnnualSalesAdapter(local_dir=tmp_path).extract()
    assert [payload.entity for payload in payloads] == [
        "suburb_sales_house",
        "suburb_sales_unit",
        "suburb_sales_residential_land",
    ]
    assert all(payload.source_url.startswith("file:") for payload in payloads)


def test_homes_victoria_rent_contract_parser(tmp_path):
    workbook = tmp_path / "rents.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "1 bedroom flat"
    sheet.append(["Moving annual median rent by suburb and town"])
    sheet.append(["1 bedroom flat", None, "Sep 2024", "Sep 2024", "Sep 2025", "Sep 2025"])
    sheet.append([None, None, "Count", "Median", "Count", "Median"])
    sheet.append(["Inner Melbourne", "Armadale", 100, 450, 110, 475])
    sheet.append([None, "Richmond", 120, 480, 130, 510])
    sheet.append([None, "Group Total", 220, 465, 240, 495])
    book.save(workbook)

    parsed = parse_homes_victoria_rent_workbook(workbook)
    assert len(parsed) == 4
    assert set(parsed["rental_region"]) == {"Inner Melbourne"}
    assert set(parsed["property_type"]) == {"unit"}
    assert set(parsed["bedrooms"]) == {1}
    assert parsed["median_weekly_rent"].max() == 510
    assert str(parsed["period_end"].max().date()) == "2025-09-30"


def test_homes_victoria_manual_drop_adapter(tmp_path):
    (tmp_path / "rents.xlsx").write_bytes(b"workbook-bytes")
    payload = HomesVictoriaRentalAdapter(local_dir=tmp_path).extract()[0]
    assert payload.entity == "moving_annual_rents_by_suburb"
    assert payload.source_url.startswith("file:")


def test_conservative_geography_key():
    assert canonical_suburb_key("St Kilda (Vic.)") == "ST KILDA"
    assert canonical_suburb_key("  Mount-Waverley ") == "MOUNT WAVERLEY"


def test_governed_roi_mart_keeps_bedroom_grain(tmp_path):
    gold = tmp_path / "gold"
    gold.mkdir()
    pd.DataFrame(
        {
            "suburb": ["BENDIGO", "BENDIGO"],
            "property_type": ["house", "house"],
            "period": [2020, 2025],
            "median_price": [400000, 600000],
        }
    ).to_parquet(gold / "mart_vgv_price_history.parquet", index=False)
    pd.DataFrame(
        {
            "suburb": ["Bendigo", "Bendigo"],
            "property_type": ["house", "house"],
            "bedrooms": [2, 3],
            "period_end": pd.to_datetime(["2025-09-30", "2025-09-30"]),
            "median_weekly_rent": [450, 520],
            "bond_count": [100, 120],
        }
    ).to_parquet(gold / "mart_homes_rent_history.parquet", index=False)

    roi_path, unmatched_path = build_roi_gold(tmp_path)
    roi = pd.read_parquet(roi_path)
    assert len(roi) == 2
    assert set(roi["bedrooms"]) == {2, 3}
    assert roi["estimated_gross_yield_pct"].between(3, 5).all()
    assert pd.read_parquet(unmatched_path).empty


def test_resend_alert_is_idempotent(tmp_path):
    gold = tmp_path / "gold.parquet"
    gold.write_bytes(b"version-one")
    state = tmp_path / "last-alert.json"
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"id": "email-1"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    first = send_gold_change_alert(
        gold,
        state,
        api_key="test-key",
        to_email="buyer@example.com",
        from_email="alerts@example.com",
        dry_run=False,
        client=client,
    )
    second = send_gold_change_alert(
        gold,
        state,
        api_key="test-key",
        to_email="buyer@example.com",
        from_email="alerts@example.com",
        dry_run=False,
        client=client,
    )
    assert first.status == "sent"
    assert second.status == "unchanged"
    assert len(calls) == 1


def test_r2_endpoint_accepts_bucket_qualified_url():
    account = "https://example.r2.cloudflarestorage.com"
    assert normalise_r2_endpoint(account, "victorian-home-medallion") == account
    assert (
        normalise_r2_endpoint(
            f"{account}/victorian-home-medallion", "victorian-home-medallion"
        )
        == account
    )


def test_manual_vgv_change_detection_is_idempotent(tmp_path):
    input_dir = tmp_path / "manual-input" / "vgv"
    input_dir.mkdir(parents=True)
    payloads = {
        "houses.xlsx": b"houses",
        "units.xlsx": b"units",
        "land.xlsx": b"land",
    }
    for name, content in payloads.items():
        (input_dir / name).write_bytes(content)
    assert _manual_vgv_inputs_changed(tmp_path)

    for index, content in enumerate(payloads.values()):
        manifest_dir = tmp_path / "bronze" / "vgv_annual_sales" / str(index)
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps({"sha256": hashlib.sha256(content).hexdigest()})
        )
    assert not _manual_vgv_inputs_changed(tmp_path)


def test_r2_download_ignores_dashboard_folder_markers(tmp_path):
    class FakePaginator:
        def paginate(self, **_kwargs):
            return [{"Contents": [{"Key": "manual-input/vgv/"}, {"Key": "manual-input/vgv/houses.xlsx"}]}]

    class FakeClient:
        def __init__(self):
            self.downloads = []

        def get_paginator(self, _name):
            return FakePaginator()

        def download_file(self, bucket, key, target):
            self.downloads.append((bucket, key, target))

    sync = R2MedallionSync.__new__(R2MedallionSync)
    sync.bucket = "test-bucket"
    sync.client = FakeClient()
    assert sync.download(tmp_path) == 1
    assert sync.client.downloads[0][1] == "manual-input/vgv/houses.xlsx"
