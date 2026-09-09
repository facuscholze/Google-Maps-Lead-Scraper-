"""Proposal generation & lifecycle (spec §37, §41-42)."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ProposalStatus
from app.core.logging import log_event
from app.integrations.ai.provider import get_ai_provider
from app.models.emailing import Proposal
from app.models.lead import Lead
from app.models.website import WebsiteAudit
from app.repositories.emailing import ProposalRepository
from app.schemas.ai import AIProposal
from app.utils.text import utcnow

logger = logging.getLogger("avascho.proposal")


class ProposalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProposalRepository(db)

    # ---------------------------------------------------------------- context --
    def build_context(self, lead: Lead, audit: WebsiteAudit | None) -> dict[str, Any]:
        strengths = []
        if audit:
            strengths = [s.get("text") or s for s in (audit.strengths or [])]
        opportunities = audit.opportunities if audit else []
        if not opportunities:
            opportunities = lead.detected_opportunities or []
        service = lead.recommended_service or "Custom AI Integration"
        catalog = {}
        try:
            from app.services.catalog import AVA_SCHO_SERVICES

            catalog = AVA_SCHO_SERVICES
        except Exception:  # noqa: BLE001
            pass
        return {
            "business_name": lead.business_name,
            "rating": lead.rating,
            "reviews": lead.reviews_count,
            "website_score": lead.website_score,
            "website_url": lead.website,
            "strengths": strengths[:6],
            "opportunities": [
                {
                    "title": o.get("title"),
                    "opportunity": o.get("opportunity"),
                    "evidence": o.get("evidence"),
                }
                for o in opportunities[:4]
            ],
            "recommended_service": service,
            "service_description": catalog.get(service, {}).get("description", ""),
            "confidence": lead.confidence,
            "lead_score": lead.lead_score,
            "opportunity_score": lead.opportunity_score,
            "why_this_lead": lead.why_this_lead,
        }

    # ------------------------------------------------------------- generate ----
    def generate(self, workspace_id: int, lead_id: int) -> Proposal:
        lead = self.db.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id)
        )
        if lead is None:
            raise ValueError("Lead not found")
        audit = self.db.scalar(
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.id.desc())
            .limit(1)
        )
        context = self.build_context(lead, audit)
        provider = get_ai_provider()
        result: AIProposal = provider.generate_proposal(context)

        proposal = self.repo.latest_for_lead(lead_id)
        if proposal is None or proposal.status in (ProposalStatus.SENT.value, ProposalStatus.CANCELLED.value):
            proposal = Proposal(
                workspace_id=workspace_id,
                lead_id=lead_id,
                version=1,
            )
            self.db.add(proposal)
        else:
            proposal.version += 1
        proposal.status = ProposalStatus.READY_FOR_REVIEW.value
        proposal.subject = result.subject
        proposal.opening = result.opening
        proposal.personalized_observation = result.personalized_observation
        proposal.strengths_json = result.strengths
        proposal.opportunities_json = result.opportunities
        proposal.recommended_solution = result.recommended_solution
        proposal.call_to_action = result.call_to_action
        proposal.signature = result.signature
        proposal.body_html = result.html
        proposal.body_plain = result.plain_text
        proposal.ai_model = provider.name
        proposal.ai_reasoning = {
            "model_note": result.model_note,
            "lead_score": lead.lead_score,
            "opportunity_score": lead.opportunity_score,
            "recommended_service": lead.recommended_service,
        }
        self.db.flush()
        log_event("proposal_generated", proposal_id=proposal.id, lead_id=lead_id, model=provider.name)
        return proposal

    def update_from_editor(self, proposal: Proposal, payload: dict[str, Any]) -> Proposal:
        """Human edits (spec §41): keep proposal truthful — edits are user-owned."""
        for field in ("subject", "opening", "personalized_observation",
                      "recommended_solution", "call_to_action", "signature"):
            if field in payload and payload[field] is not None:
                setattr(proposal, field, str(payload[field]))
        if payload.get("strengths") is not None:
            proposal.strengths_json = payload["strengths"]
        if payload.get("opportunities") is not None:
            proposal.opportunities_json = payload["opportunities"]

        content = self._content_for_render(proposal)
        if payload.get("body_html"):
            proposal.body_html = payload["body_html"]
        else:
            # Any human edit re-renders the brand HTML from the current fields.
            from app.services.emailing.email_html import render_proposal_email

            proposal.body_html = render_proposal_email(content)
        if payload.get("body_plain"):
            proposal.body_plain = payload["body_plain"]
        else:
            from app.services.emailing.email_html import render_plain_text

            proposal.body_plain = render_plain_text(content)
        if proposal.status in (
            ProposalStatus.DRAFT.value,
            ProposalStatus.READY_FOR_REVIEW.value,
            ProposalStatus.AI_GENERATED.value,
        ):
            proposal.status = ProposalStatus.READY_FOR_REVIEW.value
        self.db.flush()
        return proposal

    @staticmethod
    def _content_for_render(proposal: Proposal) -> dict[str, Any]:
        return {
            "business_name": proposal.lead.business_name if proposal.lead else "",
            "opening": proposal.opening or "",
            "personalized_observation": proposal.personalized_observation or "",
            "strengths": proposal.strengths_json or [],
            "opportunities": proposal.opportunities_json or [],
            "recommended_solution": proposal.recommended_solution or "",
            "call_to_action": proposal.call_to_action or "",
            "signature": proposal.signature or "",
        }

    def approve(self, proposal: Proposal, user_id: int | None = None) -> Proposal:
        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_at = utcnow()
        proposal.reviewed_by_user_id = user_id
        self.db.flush()
        log_event("proposal_approved", proposal_id=proposal.id)
        return proposal

    def discard(self, proposal: Proposal) -> Proposal:
        proposal.status = ProposalStatus.CANCELLED.value
        self.db.flush()
        return proposal
