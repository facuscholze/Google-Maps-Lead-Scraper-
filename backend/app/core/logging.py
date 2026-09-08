"""Structured logging helpers.

Sensitive values (API keys, OAuth tokens, passwords) are never logged.
Use `log_event` for domain events so they remain greppable in production.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

RESERVED = {"GOOGLE_MAPS_API_KEY", "GOOGLE_CLIENT_SECRET", "SECRET_KEY", "ENCRYPTION_KEY"}


def _safe_env() -> dict[str, str]:
    """Environment summary without secrets."""
    return {"APP_ENV": settings.app_env, "EXECUTION_MODE": settings.execution_mode}


def configure_logging(level: str | None = None) -> None:
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    logging.basicConfig(level=getattr(logging, (level or settings.log_level).upper(), logging.INFO),
                        format=fmt, stream=sys.stdout)


def log_event(event: str, **payload: Any) -> None:
    """Emit a structured, single-line JSON log record for a domain event."""
    record: dict[str, Any] = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    logging.getLogger("avascho.events").info(json.dumps(record, default=str))
