"""Website intelligence orchestration (crawl → extract → audit → persist).

Cache: when the most recent audit matches the stored content hash and is
fresh (within TTL), it is reused instead of re-crawling (spec §54).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import WebsiteStatus
from app.integrations.ai.provider import get_ai_provider
from app.integrations.crawler.crawler import (
    WebsiteCrawler,
    content_hash_of,
)
from app.integrations.crawler.extractor import WebsiteExtractor
from app.models.lead import Lead
from app.models.website import WebsiteAudit, WebsitePage
from app.schemas.ai import AIWebsiteAudit
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.types import AuditResult, ExtractedWebsite, PageData
from app.utils.text import utcnow

logger = logging.getLogger("avascho.website")
CACHE_TTL = timedelta(hours=168)  # 7 days


class WebsiteAnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.crawler = WebsiteCrawler()
        self.extractor = WebsiteExtractor()
        self.auditor = WebsiteAuditor()
        self.ai = get_ai_provider()

    # -------------------------------------------------------------- cache ----
    def _latest_audit(self, lead_id: int) -> WebsiteAudit | None:
        return self.db.scalar(
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.id.desc())
            .limit(1)
        )

    def reusable_audit(self, lead: Lead) -> WebsiteAudit | None:
        audit = self._latest_audit(lead.id)
        if audit is None:
            return None
        if not lead.content_hash or audit.content_hash != lead.content_hash:
            return None
        if lead.last_crawled_at is None or lead.last_crawled_at + CACHE_TTL < utcnow():
            return None
        return audit

    # ------------------------------------------------------------- pipeline ---
    def crawl_lead(self, lead: Lead, max_pages: int | None = None) -> list[PageData]:
        return self.crawler.crawl(lead.website or "", max_pages=max_pages)

    def analyze_pages(self, pages: list[PageData]) -> tuple[AuditResult, str]:
        site = self.extractor.extract(pages)
        content_hash = content_hash_of(pages)
        result = self.auditor.audit(site, content_hash)
        return result, content_hash

    def enrich_with_ai(self, result: AuditResult) -> AuditResult:
        """Optional refinement pass via the configured AI provider.

        The provider receives extracted evidence only, and its JSON output is
        validated; any failure keeps the deterministic result untouched.
        """
        provider_name = getattr(self.ai, "name", "rule_based")
        if provider_name == "rule_based":
            return result
        try:
            evidence = {
                "url": result.extracted.url,
                "title": result.extracted.title,
                "meta_description": result.extracted.meta_description,
                "text": (result.extracted.text or "")[:4000],
                "emails": result.extracted.emails,
                "phones": result.extracted.phones,
                "whatsapp": result.extracted.whatsapp_numbers,
                "social_links": result.extracted.social_links,
                "pages_seen": result.extracted.pages_seen,
                "has_contact_page": result.extracted.has_contact_page,
                "has_booking_page": result.extracted.has_booking_page,
                "has_form": result.extracted.has_form,
                "has_cta": result.extracted.has_cta,
                "cta_texts": result.extracted.cta_texts,
                "services": result.extracted.services,
                "opening_hours_found": result.extracted.opening_hours_found,
                "tech_hints": result.extracted.tech_hints,
            }
            validated: AIWebsiteAudit = self.ai.analyze_website(evidence)
            # keep deterministic strengths/evidence; overlay the validated numbers
            result.overall_score = validated.website_score
            result.subscores = validated.subscores
            result.model_used = self.ai.name
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI enrichment failed for %s: %s", result.extracted.url, exc)
        return result

    # ------------------------------------------------------------- persist ----
    def persist_audit(self, lead: Lead, result: AuditResult, pages: list[PageData]) -> WebsiteAudit:
        audit = WebsiteAudit(
            workspace_id=lead.workspace_id,
            lead_id=lead.id,
            url=lead.website or result.extracted.url,
            audit_version="1.0",
            content_hash=result.content_hash,
            overall_score=result.overall_score,
            subscores=result.subscores,
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            opportunities=result.opportunities,
            extracted_data={
                "emails": result.extracted.emails,
                "phones": result.extracted.phones,
                "whatsapp_numbers": result.extracted.whatsapp_numbers,
                "social_links": result.extracted.social_links,
                "services": result.extracted.services,
                "cta_texts": result.extracted.cta_texts,
                "address_found": result.extracted.address_found,
                "opening_hours_found": result.extracted.opening_hours_found,
                "tech_hints": result.extracted.tech_hints,
                "pages": [p.url for p in pages],
                "page_count": len(pages),
                "has_booking_page": result.extracted.has_booking_page,
                "has_contact_page": result.extracted.has_contact_page,
                "has_about_page": result.extracted.has_about_page,
                "has_form": result.extracted.has_form,
                "has_cta": result.extracted.has_cta,
                "title": result.extracted.title,
                "meta_description": result.extracted.meta_description,
                "business_description": result.extracted.business_description,
            },
            title=result.extracted.title,
            meta_description=result.extracted.meta_description,
            business_description=result.extracted.business_description,
            services=result.extracted.services,
            technologies=result.extracted.tech_hints,
            ai_model=result.model_used,
            crawled_at=utcnow(),
            audited_at=utcnow(),
        )
        self.db.add(audit)
        self.db.flush()
        for page in pages:
            self.db.add(
                WebsitePage(
                    audit_id=audit.id,
                    url=page.url,
                    kind=page.kind,
                    http_status=page.http_status,
                    title=page.title,
                    fetched_at=utcnow(),
                )
            )
        self.db.flush()

        lead.website_status = WebsiteStatus.ANALYZED.value
        lead.website_score = result.overall_score
        lead.last_crawled_at = utcnow()
        lead.content_hash = result.content_hash
        lead.website_strengths = result.strengths
        lead.website_weaknesses = result.weaknesses
        lead.detected_opportunities = result.opportunities
        lead.raw_website_data = {
            "title": result.extracted.title,
            "meta_description": result.extracted.meta_description,
            "services": result.extracted.services,
            "urls": result.extracted.pages_seen,
        }
        self._apply_contact_data(lead, result.extracted)
        self.db.add(lead)
        self.db.flush()
        return audit

    @staticmethod
    def _apply_contact_data(lead: Lead, site: ExtractedWebsite) -> None:
        email, confidence, source_url = site.best_email
        if email and not lead.email:
            lead.email = email.lower()
            lead.email_confidence = confidence
            lead.email_source_url = source_url
        lead.contact_channels = {
            "whatsapp": site.whatsapp_numbers[:2],
            "social": site.social_links[:4],
            "phones_from_site": site.phones[:4],
            "form": site.has_form,
            "booking": site.has_booking_page,
        }
        lead.raw_website_data = lead.raw_website_data or {}

    # --------------------------------------------------------------- facade ---
    def analyze_lead(self, lead: Lead, pages: list[PageData] | None = None) -> dict[str, Any]:
        """Full analysis for one lead. Returns {audited, reused, pages, audit_id}."""
        if not lead.website:
            return {"audited": False, "reused": False, "pages": 0, "audit_id": None}
        cached = self.reusable_audit(lead)
        if cached is not None:
            return {"audited": True, "reused": True, "pages": 0, "audit_id": cached.id}
        pages = pages if pages is not None else self.crawl_lead(lead)
        if not pages:
            lead.website_status = WebsiteStatus.ERROR.value
            self.db.add(lead)
            self.db.flush()
            return {"audited": False, "reused": False, "pages": 0, "audit_id": None, "error": "no_pages"}
        result, content_hash = self.analyze_pages(pages)
        result = self.enrich_with_ai(result)
        audit = self.persist_audit(lead, result, pages)
        return {"audited": True, "reused": False, "pages": len(pages), "audit_id": audit.id}
