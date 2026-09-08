"""Health & observability endpoints (spec §91)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    google_state = "configured" if settings.google_maps_api_key else "not_configured"
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "execution_mode": settings.execution_mode,
        "ai_provider": settings.ai_provider,
        "google_places": google_state,
        "database": "unknown",
        "redis": "inline" if settings.execution_mode != "celery" else "configured",
        "time": datetime.now().isoformat(),
    }


@router.get("/health/database")
def health_database(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get("/health/google")
def health_google() -> dict:
    if settings.google_maps_api_key:
        return {"status": "ok", "message": "Google Places API key configured"}
    return {"status": "degraded", "message": "Google Places API key not configured — running with mock provider"}


@router.get("/health/redis")
def health_redis() -> dict:
    if settings.execution_mode != "celery":
        return {"status": "ok", "mode": "inline", "message": "Redis not required in inline mode"}
    try:
        import redis as redis_lib

        client = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=3)
        client.ping()
        return {"status": "ok", "mode": "celery"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}
