"""Shared utilities: time helpers, text cleaning, JSON parsing."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """Return an aware datetime, treating naive values as UTC.

    SQLite DateTime columns come back naive while in-app datetimes are
    tz-aware; mixing the two raises ``can't compare offset-naive and
    offset-aware datetimes``. Normalise on read instead of scattering
    ``replace(tzinfo=…)`` across the codebase.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
DOMAIN_RE = re.compile(r"([a-z0-9\-]+\.)+[a-z]{2,}")


def clean_text(value: str | None, limit: int | None = None) -> str:
    if not value:
        return ""
    value = WHITESPACE_RE.sub(" ", value).strip()
    if limit and len(value) > limit:
        return value[:limit].rstrip() + "…"
    return value


def normalize_email(email: str) -> str:
    return email.strip().lower()


def parse_json_safe(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
