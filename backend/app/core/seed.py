"""Dev/demo bootstrap: workspace + demo user + settings defaults."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import Role
from app.core.security import hash_password
from app.models.user import User, Workspace

logger = logging.getLogger("avascho.seed")


def seed_demo(db: Session) -> None:
    if not settings.auto_create_demo_user or settings.app_env == "production":
        return
    workspace = db.scalar(select(Workspace).where(Workspace.name == settings.demo_workspace))
    if workspace is None:
        workspace = Workspace(name=settings.demo_workspace, settings_json="{}")
        db.add(workspace)
        db.flush()
    user = db.scalar(select(User).where(User.email == settings.demo_email))
    if user is None:
        user = User(
            email=settings.demo_email,
            password_hash=hash_password(settings.demo_password),
            name="Demo AvaScho",
            workspace_id=workspace.id,
            role=Role.OWNER.value,
        )
        db.add(user)
        db.flush()
    db.commit()
    logger.info("demo user ready: %s (workspace %s)", settings.demo_email, workspace.name)
