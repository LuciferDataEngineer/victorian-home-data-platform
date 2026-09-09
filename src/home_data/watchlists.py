from typing import Any

import httpx


class WatchlistClient:
    def __init__(
        self,
        supabase_url: str,
        publishable_key: str,
        access_token: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.url = f"{supabase_url.rstrip('/')}/rest/v1/user_watchlists"
        self.headers = {
            "apikey": publishable_key,
            "Authorization": f"Bearer {access_token}",
        }
        self.client = client or httpx.Client(timeout=20)

    def list(self) -> list[dict[str, Any]]:
        response = self.client.get(
            self.url,
            headers=self.headers,
            params={"select": "*", "order": "created_at.desc"},
        )
        response.raise_for_status()
        return response.json()

    def save(self, watchlist: dict[str, Any]) -> None:
        response = self.client.post(
            self.url,
            headers={**self.headers, "Prefer": "resolution=merge-duplicates"},
            params={"on_conflict": "user_id,canonical_suburb_key,property_type,bedrooms"},
            json=watchlist,
        )
        response.raise_for_status()

    def delete(self, watchlist_id: str) -> None:
        response = self.client.delete(
            self.url,
            headers=self.headers,
            params={"id": f"eq.{watchlist_id}"},
        )
        response.raise_for_status()
