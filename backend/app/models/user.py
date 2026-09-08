"""Multi-tenant & identity models."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Role
from app.models.base import Base, PKMixin, TimestampMixin


class Workspace(Base, PKMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    users: Mapped[list["User"]] = relationship(back_populates="workspace")
    searches: Mapped[list["Search"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    leads: Mapped[list["Lead"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    email_accounts: Mapped[list["EmailAccount"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    presets: Mapped[list["SearchPreset"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    suppression: Mapped[list["SuppressionEntry"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class User(Base, PKMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default=Role.MEMBER.value, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="users")


from app.models.search import (  # noqa: E402,F401  (kept at end to break cycles cleanly)
    Search,
    SearchPreset,
)
from app.models.lead import Lead  # noqa: E402,F401
from app.models.emailing import (  # noqa: E402,F401
    Email,
    EmailAccount,
    EmailEvent,
    Proposal,
    SuppressionEntry,
)
from app.models.jobs import Job  # noqa: E402,F401
from app.models.website import WebsiteAudit, WebsitePage  # noqa: E402,F401
