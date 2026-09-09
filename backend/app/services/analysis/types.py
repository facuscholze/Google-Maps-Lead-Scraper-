"""Shared value objects for the analysis engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    """A single audit finding with its evidence (spec §21, §62)."""

    problem: str
    evidence: str
    source_url: str | None = None
    kind: str = "INFERENCE"  # FACT | INFERENCE
    dimension: str = "general"
    score_impact: float = 0.0


@dataclass
class PageData:
    url: str
    http_status: int | None = None
    title: str | None = None
    html: str = ""
    text: str = ""
    links: list[str] = field(default_factory=list)
    kind: str = "other"  # home | about | services | contact | booking | other
    fetched_at: str | None = None
    error: str | None = None


@dataclass
class ExtractedWebsite:
    """Parsed, public information found on the site (spec §17)."""

    url: str = ""
    title: str | None = None
    meta_description: str | None = None
    text: str = ""
    business_description: str | None = None
    services: list[str] = field(default_factory=list)
    emails: list[dict[str, Any]] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    whatsapp_numbers: list[str] = field(default_factory=list)
    social_links: list[str] = field(default_factory=list)
    pages_seen: list[str] = field(default_factory=list)
    has_contact_page: bool = False
    has_about_page: bool = False
    has_booking_page: bool = False
    has_form: bool = False
    has_cta: bool = False
    cta_texts: list[str] = field(default_factory=list)
    address_found: str | None = None
    opening_hours_found: str | None = None
    tech_hints: dict[str, bool] = field(default_factory=dict)
    h1_count: int = 0
    has_viewport: bool = False
    https: bool = True
    word_count: int = 0
    img_without_alt: int = 0
    page_count: int = 0

    @property
    def best_email(self) -> tuple[str | None, str | None, str | None]:
        """Returns (email, confidence, source_url)."""
        if not self.emails:
            return None, None, None
        ranked = sorted(
            self.emails,
            key=lambda e: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(e.get("confidence"), 3),
        )
        best = ranked[0]
        return best.get("email"), best.get("confidence"), best.get("source_url")


@dataclass
class AuditResult:
    overall_score: float
    subscores: dict[str, float]
    strengths: list[dict[str, Any]]
    weaknesses: list[dict[str, Any]]
    opportunities: list[dict[str, Any]]
    findings: list[Finding]
    extracted: ExtractedWebsite
    content_hash: str | None = None
    model_used: str = "rule-based"
