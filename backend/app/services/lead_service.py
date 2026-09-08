"""Lead scoring persistence + contact discovery (spec §25-28, §63)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.website import WebsiteAudit
from app.services.analysis.scorer import LeadScorer


def score_lead(db: Session, lead: Lead) -> dict:
    """Compute explainable scores and persist them onto the lead."""
    scorer = LeadScorer()
    audit = db.scalar(
        select(WebsiteAudit)
        .where(WebsiteAudit.lead_id == lead.id)
        .order_by(WebsiteAudit.id.desc())
        .limit(1)
    )
    audit_result = None
    if audit is not None:
        from app.services.analysis.types import AuditResult, ExtractedWebsite

        data = audit.extracted_data or {}
        extracted = ExtractedWebsite(
            url=audit.url or lead.website or "",
            pages_seen=data.get("pages", []),
            emails=data.get("emails", []),
            phones=data.get("phones", []),
            whatsapp_numbers=data.get("whatsapp_numbers", []),
            social_links=data.get("social_links", []),
            page_count=int(data.get("page_count") or 0),
            has_booking_page=bool(data.get("has_booking_page")),
            has_form=bool(data.get("has_form")),
            has_cta=bool(data.get("has_cta")),
            has_contact_page=bool(data.get("has_contact_page")),
            has_about_page=bool(data.get("has_about_page")),
        )
        audit_result = AuditResult(
            overall_score=audit.overall_score,
            subscores=audit.subscores,
            strengths=audit.strengths,
            weaknesses=audit.weaknesses,
            opportunities=audit.opportunities,
            findings=[],
            extracted=extracted,
        )

    result = scorer.score(
        rating=lead.rating,
        reviews=lead.reviews_count,
        website_score=lead.website_score,
        audit=audit_result,
        has_email=bool(lead.email),
        email_confidence=lead.email_confidence,
        has_phone=bool(lead.phone or lead.international_phone),
        has_website=bool(lead.website),
        business_name=lead.business_name,
        social_count=len((lead.contact_channels or {}).get("social", []))
        if lead.contact_channels
        else 0,
    )

    lead.lead_score = result["lead_score"]
    lead.opportunity_score = result["opportunity_score"]
    lead.lead_temperature = result["temperature"]
    lead.priority = result["priority"]
    lead.recommended_action = result["recommended_action"]
    lead.recommended_service = result["recommended_service"]
    lead.confidence = result["confidence"]
    lead.why_this_lead = result["why_this_lead"]
    lead.why_now = result["why_now"]
    lead.score_breakdown = {
        "lead": result["lead_breakdown"],
        "opportunity": result["opportunity_breakdown"],
    }
    db.add(lead)
    db.flush()
    return result
