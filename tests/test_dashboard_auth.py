import httpx

from home_data.dashboard_auth import sign_in, sign_up


def test_sign_in_returns_authenticated_user():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "password"
        assert request.headers["apikey"] == "publishable"
        return httpx.Response(
            200,
            json={"access_token": "token", "user": {"email": "buyer@example.com"}},
        )

    result = sign_in(
        "https://project.supabase.co",
        "publishable",
        "buyer@example.com",
        "secure-password",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert result.authenticated is True
    assert result.email == "buyer@example.com"


def test_sign_in_surfaces_safe_api_error():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"error_description": "Invalid credentials"})
        )
    )
    result = sign_in("https://project.supabase.co", "key", "buyer@example.com", "bad", client)
    assert result.authenticated is False
    assert result.message == "Invalid credentials"


def test_sign_up_requires_eight_character_password():
    result = sign_up("https://project.supabase.co", "key", "buyer@example.com", "short")
    assert result.authenticated is False
    assert "8 characters" in result.message


def test_sign_up_requires_confirmation_when_no_session_returned():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"user": {"email": "buyer@example.com"}})
        )
    )
    result = sign_up(
        "https://project.supabase.co",
        "key",
        "buyer@example.com",
        "secure-password",
        client,
    )
    assert result.authenticated is False
    assert "confirm" in result.message.lower()
