from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class AuthResult:
    authenticated: bool
    message: str
    email: str | None = None
    access_token: str | None = None


def _message(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return fallback
    return str(payload.get("msg") or payload.get("error_description") or fallback)


def sign_in(
    supabase_url: str,
    publishable_key: str,
    email: str,
    password: str,
    client: httpx.Client | None = None,
) -> AuthResult:
    if not email.strip() or not password:
        return AuthResult(False, "Enter both email and password.")
    response = (client or httpx.Client(timeout=20)).post(
        f"{supabase_url.rstrip('/')}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": publishable_key},
        json={"email": email.strip(), "password": password},
    )
    if response.is_error:
        return AuthResult(False, _message(response, "Sign-in failed."))
    payload = response.json()
    return AuthResult(
        True,
        "Signed in.",
        email=payload.get("user", {}).get("email", email.strip()),
        access_token=payload.get("access_token"),
    )


def sign_up(
    supabase_url: str,
    publishable_key: str,
    email: str,
    password: str,
    client: httpx.Client | None = None,
) -> AuthResult:
    if not email.strip() or not password:
        return AuthResult(False, "Enter both email and password.")
    if len(password) < 8:
        return AuthResult(False, "Use a password with at least 8 characters.")
    response = (client or httpx.Client(timeout=20)).post(
        f"{supabase_url.rstrip('/')}/auth/v1/signup",
        headers={"apikey": publishable_key},
        json={"email": email.strip(), "password": password},
    )
    if response.is_error:
        return AuthResult(False, _message(response, "Sign-up failed."))
    payload = response.json()
    token = payload.get("access_token")
    return AuthResult(
        bool(token),
        "Account created. Check your email to confirm it, then sign in."
        if not token
        else "Account created and signed in.",
        email=payload.get("user", {}).get("email", email.strip()),
        access_token=token,
    )


def request_password_recovery(
    supabase_url: str,
    publishable_key: str,
    email: str,
    redirect_to: str,
    client: httpx.Client | None = None,
) -> str:
    if not email.strip():
        return "Enter your email address."
    response = (client or httpx.Client(timeout=20)).post(
        f"{supabase_url.rstrip('/')}/auth/v1/recover",
        params={"redirect_to": redirect_to},
        headers={"apikey": publishable_key},
        json={"email": email.strip()},
    )
    if response.is_error:
        return _message(response, "Password recovery could not be started.")
    return "Check your email for the password-reset link."


def verify_recovery_token(
    supabase_url: str,
    publishable_key: str,
    token_hash: str,
    client: httpx.Client | None = None,
) -> AuthResult:
    response = (client or httpx.Client(timeout=20)).post(
        f"{supabase_url.rstrip('/')}/auth/v1/verify",
        headers={"apikey": publishable_key},
        json={"token_hash": token_hash, "type": "recovery"},
    )
    if response.is_error:
        return AuthResult(False, _message(response, "This recovery link is invalid or expired."))
    payload = response.json()
    return AuthResult(
        True,
        "Recovery link verified.",
        email=payload.get("user", {}).get("email"),
        access_token=payload.get("access_token"),
    )


def update_password(
    supabase_url: str,
    publishable_key: str,
    access_token: str,
    password: str,
    client: httpx.Client | None = None,
) -> str:
    if len(password) < 8:
        return "Use a password with at least 8 characters."
    response = (client or httpx.Client(timeout=20)).put(
        f"{supabase_url.rstrip('/')}/auth/v1/user",
        headers={"apikey": publishable_key, "Authorization": f"Bearer {access_token}"},
        json={"password": password},
    )
    if response.is_error:
        return _message(response, "The password could not be updated.")
    return "Password updated. You can now sign in."
