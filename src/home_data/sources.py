from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

import httpx

from home_data.models import SourcePayload


class SourceAdapter(ABC):
    @abstractmethod
    def extract(self) -> list[SourcePayload]:
        raise NotImplementedError


class SampleSalesAdapter(SourceAdapter):
    def extract(self) -> list[SourcePayload]:
        content = b"""suburb,lga,property_type,period,median_price,sales_count
BALLARAT CENTRAL,Ballarat,house,2025,610000,121
BENDIGO,Bendigo,house,2025,590000,164
GEELONG,Greater Geelong,house,2025,805000,97
MELBOURNE,Melbourne,unit,2025,615000,403
"""
        return [SourcePayload(
            source="sample_sales",
            domain="property_market",
            entity="suburb_sales",
            content=content,
            media_type="text/csv",
            source_url="internal://contract-fixture/sample-sales",
            observation_date="2025-12-31",
            publication_date="2026-06-12",
        )]


class SampleRentsAdapter(SourceAdapter):
    def extract(self) -> list[SourcePayload]:
        content = b"""suburb,lga,property_type,period,median_weekly_rent
BALLARAT CENTRAL,Ballarat,house,2025,470
BENDIGO,Bendigo,house,2025,460
GEELONG,Greater Geelong,house,2025,560
MELBOURNE,Melbourne,unit,2025,590
"""
        return [SourcePayload(
            source="sample_rents",
            domain="rental_market",
            entity="suburb_rents",
            content=content,
            media_type="text/csv",
            source_url="internal://contract-fixture/sample-rents",
            observation_date="2025-12-31",
            publication_date="2026-02-24",
        )]


class VgvAnnualSalesAdapter(SourceAdapter):
    """Official Valuer-General Victoria annual suburb sales workbooks."""

    WORKBOOKS: ClassVar[dict[str, str]] = {
        "house": "https://www.land.vic.gov.au/__data/assets/excel_doc/0033/775617/houses-by-suburb-2015-2025.xlsx",
        "unit": "https://www.land.vic.gov.au/__data/assets/excel_doc/0034/775618/units-by-suburb-2015-2025.xlsx",
        "residential_land": "https://www.land.vic.gov.au/__data/assets/excel_doc/0035/775619/land-by-suburb-2015-2025.xlsx",
    }
    LANDING_PAGE = (
        "https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics"
    )

    LOCAL_NAMES: ClassVar[dict[str, tuple[str, ...]]] = {
        "house": ("houses.xlsx", "houses-by-suburb-2015-2025.xlsx"),
        "unit": ("units.xlsx", "units-by-suburb-2015-2025.xlsx"),
        "residential_land": ("land.xlsx", "land-by-suburb-2015-2025.xlsx"),
    }

    def __init__(self, client: httpx.Client | None = None, local_dir: Path | None = None):
        self.local_dir = local_dir
        self.client = client or httpx.Client(
            timeout=60,
            follow_redirects=True,
            headers={"User-Agent": "VictorianHomeData/0.1 (+non-commercial research)"},
        )

    def extract(self) -> list[SourcePayload]:
        payloads = []
        for property_type, url in self.WORKBOOKS.items():
            if self.local_dir:
                path = next(
                    (
                        self.local_dir / name
                        for name in self.LOCAL_NAMES[property_type]
                        if (self.local_dir / name).exists()
                    ),
                    None,
                )
                if path is None:
                    expected = ", ".join(self.LOCAL_NAMES[property_type])
                    raise FileNotFoundError(f"Missing {property_type} workbook; expected {expected}")
                content = path.read_bytes()
                source_url = path.resolve().as_uri()
            else:
                response = self.client.get(url, headers={"Referer": self.LANDING_PAGE})
                response.raise_for_status()
                content = response.content
                source_url = url
            payloads.append(
                SourcePayload(
                    source="vgv_annual_sales",
                    domain="property_market",
                    entity=f"suburb_sales_{property_type}",
                    content=content,
                    media_type=(
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ),
                    source_url=source_url,
                    observation_date="2025-12-31",
                    publication_date="2026-07-10",
                    licence="CC-BY-4.0",
                )
            )
        return payloads


class HomesVictoriaRentalAdapter(SourceAdapter):
    """Latest official Homes Victoria moving-annual rent workbook."""

    DATASET_ID = "rental-report-quarterly-moving-annual-rents-by-suburb"
    CKAN_API = "https://discover.data.vic.gov.au/api/3/action/package_show"
    LOCAL_NAMES: ClassVar[tuple[str, ...]] = (
        "rents.xlsx",
        "moving-annual-rent-suburb.xlsx",
    )

    def __init__(self, client: httpx.Client | None = None, local_dir: Path | None = None):
        self.local_dir = local_dir
        self.client = client or httpx.Client(
            timeout=90,
            follow_redirects=True,
            headers={"User-Agent": "VictorianHomeData/0.1 (+non-commercial research)"},
        )

    def extract(self) -> list[SourcePayload]:
        if self.local_dir:
            path = next(
                (self.local_dir / name for name in self.LOCAL_NAMES if (self.local_dir / name).exists()),
                None,
            )
            if path is None:
                expected = ", ".join(self.LOCAL_NAMES)
                raise FileNotFoundError(f"Missing rental workbook; expected {expected}")
            content = path.read_bytes()
            source_url = path.resolve().as_uri()
            observation_date = "2025-09-30"
            publication_date = "2026-02-20"
        else:
            metadata = self.client.get(self.CKAN_API, params={"id": self.DATASET_ID})
            metadata.raise_for_status()
            result = metadata.json()["result"]
            resources = [
                resource
                for resource in result["resources"]
                if resource.get("format", "").upper() == "XLSX" and resource.get("period_end")
            ]
            if not resources:
                raise ValueError("DataVic returned no dated XLSX rental resources")
            resource = max(resources, key=lambda item: item["period_end"])
            response = self.client.get(resource["url"])
            response.raise_for_status()
            content = response.content
            source_url = resource["url"]
            observation_date = resource["period_end"][:10]
            publication_date = (resource.get("release_date") or resource["created"])[:10]
        return [
            SourcePayload(
                source="homes_victoria_rents",
                domain="rental_market",
                entity="moving_annual_rents_by_suburb",
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                source_url=source_url,
                observation_date=observation_date,
                publication_date=publication_date,
                licence="CC-BY-4.0",
            )
        ]


ADAPTERS: dict[str, type[SourceAdapter]] = {
    "sample_sales": SampleSalesAdapter,
    "sample_rents": SampleRentsAdapter,
    "vgv_annual_sales": VgvAnnualSalesAdapter,
    "homes_victoria_rents": HomesVictoriaRentalAdapter,
}
