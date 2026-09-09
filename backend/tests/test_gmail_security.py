"""Gmail OAuth/raw message & security helpers tests (spec §43, §58)."""
from __future__ import annotations

import base64

import pytest

from app.core.security import encrypt_value, decrypt_value, hash_password, verify_password
from app.integrations.gmail.sender import build_raw_message


def test_password_hash_roundtrip():
    stored = hash_password("s3cret-avascho")
    assert stored != "s3cret-avascho"
    assert verify_password("s3cret-avascho", stored)
    assert not verify_password("wrong", stored)


def test_encryption_roundtrip():
    token = "ya29.live-refresh-token-value"
    encrypted = encrypt_value(token)
    assert token not in encrypted
    assert decrypt_value(encrypted) == token


def test_raw_message_build():
    raw = build_raw_message(
        to_email="lead@example.com",
        from_email="ventas@avascho.com",
        subject="Una idea para Example",
        body_html="<p>Hola</p>",
        body_plain="Hola",
    )
    decoded = base64.urlsafe_b64decode(raw.encode()).decode()
    assert "To: lead@example.com" in decoded
    assert "Subject: Una idea para Example" in decoded
    assert "Content-Type: text/html" in decoded


def test_gmail_oauth_not_configured_raises():
    from app.core.config import get_settings

    settings = get_settings()
    original = (settings.google_client_id, settings.google_client_secret)
    settings.google_client_id = ""
    settings.google_client_secret = ""
    try:
        from app.integrations.gmail.oauth import GmailOAuthError, build_authorization_url

        with pytest.raises(GmailOAuthError):
            build_authorization_url("state-123")
    finally:
        settings.google_client_id, settings.google_client_secret = original
