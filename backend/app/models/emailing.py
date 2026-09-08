"""Email / proposal / suppression models (spec §38-49)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class EmailAccount(Base, PKMixin, TimestampMixin):
    __tablename__ = "email_accounts"
    __table_args__ = (UniqueConstraint("email", name="uq_email_accounts_email"),)

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), default="gmail", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="CONNECTED", nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    sent_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD UTC
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="email_accounts")
    emails: Mapped[list["Email"]] = relationship(back_populates="account")


class Proposal(Base, PKMixin, TimestampMixin):
    __tablename__ = "proposals"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening: Mapped[str | None] = mapped_column(Text, nullable=True)
    personalized_observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    opportunities_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    recommended_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_to_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ai_reasoning: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="proposals")
    lead: Mapped["Lead"] = relationship(back_populates="proposals")
    emails: Mapped[list["Email"]] = relationship(back_populates="proposal")


class Email(Base, PKMixin, TimestampMixin):
    __tablename__ = "emails"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proposal_id: Mapped[int | None] = mapped_column(
        ForeignKey("proposals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    gmail_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_plain: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", nullable=False, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    workspace: Mapped["Workspace"] = relationship()
    lead: Mapped["Lead"] = relationship()
    proposal: Mapped["Proposal"] = relationship(back_populates="emails")
    account: Mapped["EmailAccount"] = relationship(back_populates="emails")
    events: Mapped[list["EmailEvent"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )


class EmailEvent(Base, PKMixin):
    __tablename__ = "email_events"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email_id: Mapped[int] = mapped_column(
        ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    email: Mapped["Email"] = relationship(back_populates="events")


class SuppressionEntry(Base, PKMixin, TimestampMixin):
    """DO_NOT_CONTACT registry (spec §48)."""

    __tablename__ = "suppression_list"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_suppression_workspace_email"),
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(30), default="OPT_OUT", nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="suppression")
