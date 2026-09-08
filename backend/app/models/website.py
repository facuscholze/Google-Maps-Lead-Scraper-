"""Website audit models (spec §17, §21-24, §54)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class WebsiteAudit(Base, PKMixin, TimestampMixin):
    __tablename__ = "website_audits"

    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    audit_version: Mapped[str] = mapped_column(String(20), default="1", nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0-10
    subscores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    strengths: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    opportunities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extracted_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    services: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    technologies: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lead: Mapped["Lead"] = relationship(back_populates="audits")


class WebsitePage(Base, PKMixin, TimestampMixin):
    __tablename__ = "website_pages"

    audit_id: Mapped[int] = mapped_column(
        ForeignKey("website_audits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="other", nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audit: Mapped["WebsiteAudit"] = relationship(back_populates="pages")


WebsiteAudit.pages = relationship(WebsitePage, back_populates="audit", cascade="all, delete-orphan")
