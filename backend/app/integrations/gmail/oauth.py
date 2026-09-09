"""Gmail OAuth 2.0 flow (spec §43).

Never asks for passwords. Tokens are exchanged server-side and encrypted at
rest by the caller (ENCRYPTION_KEY).
"""
from __future__ import annotations

import urllib.parse
from typing import Any

import httpx

from app.core.config import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GmailOAuthError(Exception):
    """OAuth configuration or exchange failure."""


def configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def build_authorization_url(state: str) -> str:
    if not configured():
        raise GmailOAuthError("Google OAuth is not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    if not configured():
        raise GmailOAuthError("Google OAuth is not configured")
    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_oauth_redirect_uri,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise GmailOAuthError(f"Token exchange failed: {response.status_code} {response.text[:200]}")
    return response.json()


def refresh_access_token(refresh_token: str) -> tuple[str, int]:
    """Returns (access_token, expires_in_seconds)."""
    if not configured():
        raise GmailOAuthError("Google OAuth is not configured")
    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise GmailOAuthError(f"Token refresh failed: {response.status_code} {response.text[:200]}")
    data = response.json()
    return data["access_token"], int(data.get("expires_in", 3600))


async def fetch_profile_email(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("email") or ""
