import httpx

from home_data.dashboard_auth import (
    request_password_recovery,
    sign_in,
    sign_up,
    update_password,
    verify_recovery_token,
)


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


def test_password_recovery_token_can_update_password():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/verify"):
            return httpx.Response(
                200,
                json={"access_token": "recovery-token", "user": {"email": "buyer@example.com"}},
            )
        return httpx.Response(200, json={"user": {"email": "buyer@example.com"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = verify_recovery_token("https://project.supabase.co", "key", "hash", client)
    message = update_password(
        "https://project.supabase.co", "key", result.access_token or "", "new-password", client
    )
    assert result.authenticated is True
    assert message.startswith("Password updated")
    assert requests[1].headers["authorization"] == "Bearer recovery-token"


def test_request_password_recovery_uses_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["redirect_to"].endswith("streamlit.app/")
        return httpx.Response(200, json={})

    message = request_password_recovery(
        "https://project.supabase.co",
        "key",
        "buyer@example.com",
        "https://dashboard.streamlit.app/",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert "Check your email" in message
