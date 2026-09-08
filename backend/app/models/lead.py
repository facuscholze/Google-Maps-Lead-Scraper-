"""Lead domain model (spec §13, §29)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class Lead(Base, PKMixin, TimestampMixin):
    __tablename__ = "leads"
    __table_args__ = (
        # Dedup guarantee: a Google place is stored once per workspace.
        UniqueConstraint("workspace_id", "place_id", name="uq_leads_workspace_place"),
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    place_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    business_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    international_phone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    email_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    email_source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    google_maps_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    business_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website_status: Mapped[str] = mapped_column(String(20), default="NONE", nullable=False)

    website_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    opportunity_score: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    lead_temperature: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    priority: Mapped[str | None] = mapped_column(String(5), nullable=True, index=True)
    recommended_service: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    why_this_lead: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_now: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSON evidence blobs (never used for logic; presentational + audit trail)
    raw_google_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_website_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    website_strengths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    website_weaknesses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    detected_opportunities: Mapped[list | None] = mapped_column(JSON, nullable=True)
    contact_channels: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    matched: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace: Mapped["Workspace"] = relationship(back_populates="leads")
    searches: Mapped[list["SearchLead"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    audits: Mapped[list["WebsiteAudit"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
