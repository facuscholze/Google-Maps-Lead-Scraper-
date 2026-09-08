"""Test bootstrap.

IMPORTANT: environment is configured BEFORE any app module import so that the
application Settings/engine are pointed at an isolated SQLite database and the
offline mock providers.
"""
from __future__ import annotations

import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_avascho.db"
os.environ["SEARCH_PROVIDER"] = "mock"
os.environ["AI_PROVIDER"] = "rule_based"
os.environ["AUTO_CREATE_DEMO_USER"] = "true"
os.environ["DEMO_EMAIL"] = "test@avascho.com"
os.environ["DEMO_PASSWORD"] = "test-password"
os.environ["DEMO_WORKSPACE"] = "Test Workspace"
os.environ["ALLOW_MOCK_EMAIL_SENDING"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789"
os.environ["ENCRYPTION_KEY"] = "YO8ODq897FaqEAtw-dLaaP7OoYyjw-L0bAmp9UhtZ8g="
os.environ["DAILY_EMAIL_LIMIT"] = "5"
os.environ["MIN_SEND_DELAY_SECONDS"] = "1"
os.environ["MAX_SEND_DELAY_SECONDS"] = "2"

import pytest  # noqa: E402
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _database():
    from app.core.database import SessionLocal, engine, init_db

    init_db()
    yield
    engine.dispose()
    if os.path.exists("test_avascho.db"):
        os.remove("test_avascho.db")


@pytest.fixture()
def db_session():
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def workspace(db_session):
    from app.core.seed import seed_demo

    seed_demo(db_session)
    from sqlalchemy import select

    from app.models.user import Workspace

    return db_session.scalar(select(Workspace).limit(1))


@pytest.fixture()
def demo_user(db_session):
    from app.core.seed import seed_demo

    seed_demo(db_session)
    from sqlalchemy import select

    from app.models.user import User

    return db_session.scalar(select(User).limit(1))
