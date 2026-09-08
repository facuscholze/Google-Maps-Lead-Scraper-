"""Search domain models (spec §50, §55, §65)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, PKMixin, TimestampMixin


class Search(Base, PKMixin, TimestampMixin):
    __tablename__ = "searches"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_results: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    min_reviews: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    only_with_website: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    only_with_phone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    try_find_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    results_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    results_qualified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    websites_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    emails_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hot_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warm_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cold_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    google_pages: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped["Workspace"] = relationship(back_populates="searches")
    links: Mapped[list["SearchLead"]] = relationship(
        back_populates="search", cascade="all, delete-orphan"
    )


class SearchLead(Base):
    """Association lead<->search; a lead may appear in many searches (dedup by place_id)."""

    __tablename__ = "search_leads"

    search_id: Mapped[int] = mapped_column(
        ForeignKey("searches.id", ondelete="CASCADE"), primary_key=True
    )
    lead_id: Mapped[int] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True
    )
    matched: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    search: Mapped["Search"] = relationship(back_populates="links")
    lead: Mapped["Lead"] = relationship(back_populates="searches")


class SearchPreset(Base, PKMixin, TimestampMixin):
    """Saved filter presets (spec §65)."""

    __tablename__ = "search_presets"

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    workspace: Mapped["Workspace"] = relationship(back_populates="presets")
