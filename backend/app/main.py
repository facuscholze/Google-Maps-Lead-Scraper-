"""AvaScho Lead Intelligence — FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging, log_event
from app.core.middleware import add_security_and_cors
from app.core.seed import seed_demo

configure_logging()
logger = logging.getLogger("avascho")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inline/development mode creates tables & seeds a demo user. Production
    # deployments run Alembic migrations instead (see scripts/run_migrations).
    if settings.app_env != "production":
        from app.core.database import init_db

        try:
            init_db()
            with SessionLocal() as db:
                seed_demo(db)
            log_event("app_started", mode="dev", db_ready=True)
        except Exception as exc:  # noqa: BLE001
            log_event("app_startup_db_error", error=str(exc)[:500])
            raise
    else:
        log_event("app_started", mode="production")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AvaScho Lead Intelligence API",
        description="Plataforma de prospección comercial: búsqueda, inteligencia de websites, "
        "scoring, propuestas y outreach responsable.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    add_security_and_cors(app)

    from app.api.routes_auth import router as auth_router
    from app.api.routes_dashboard import router as dashboard_router
    from app.api.routes_email_accounts import router as email_accounts_router
    from app.api.routes_emails import router as emails_router
    from app.api.routes_health import router as health_router
    from app.api.routes_jobs import router as jobs_router
    from app.api.routes_leads import router as leads_router
    from app.api.routes_proposals import router as proposals_router
    from app.api.routes_searches import router as searches_router
    from app.api.routes_suppression import router as suppression_router

    api = settings.api_prefix
    app.include_router(auth_router, prefix=api)
    app.include_router(searches_router, prefix=api)
    app.include_router(leads_router, prefix=api)
    app.include_router(proposals_router, prefix=api)
    app.include_router(email_accounts_router, prefix=api)
    app.include_router(emails_router, prefix=api)
    app.include_router(jobs_router, prefix=api)
    app.include_router(suppression_router, prefix=api)
    app.include_router(dashboard_router, prefix=api)
    app.include_router(health_router, prefix=api)

    @app.get("/")
    def root() -> dict:
        return {
            "name": settings.app_name,
            "docs": "/api/docs",
            "health": f"{api}/health",
        }

    return app


app = create_app()
