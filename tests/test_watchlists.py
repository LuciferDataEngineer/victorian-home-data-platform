import httpx

from home_data.watchlists import WatchlistClient


def test_watchlist_client_uses_user_token_and_rls_endpoint():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "watch-1"}])
        return httpx.Response(204)

    client = WatchlistClient(
        "https://project.supabase.co",
        "publishable",
        "user-token",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.list() == [{"id": "watch-1"}]
    client.save({"canonical_suburb_key": "CARLTON"})
    client.delete("watch-1")

    assert [request.method for request in requests] == ["GET", "POST", "DELETE"]
    assert all(request.headers["authorization"] == "Bearer user-token" for request in requests)
    assert all(request.headers["apikey"] == "publishable" for request in requests)
