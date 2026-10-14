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
        from app.services.catalog import AVA_SCHO_SERVICES, recommended_web_service

        # F7/D7.1: las fortalezas quedan ANCLADAS en evidencia del audit (dict
        # con text + evidence + kind) — nunca strings sueltas, así la métrica
        # de grounding puede verificar cada afirmación del email.
        strengths: list[dict[str, Any]] = []
        if audit:
            for s in audit.strengths or []:
                if isinstance(s, dict):
                    strengths.append({
                        "text": s.get("text", ""),
                        "evidence": s.get("evidence"),
                        "kind": s.get("kind", "FACT"),
                    })
                else:
                    strengths.append({"text": str(s), "evidence": None, "kind": "FACT"})
        # Old audits may contain automation offers. Never reuse those in web proposals.
        opportunities = [o for o in ((audit.opportunities if audit else lead.detected_opportunities) or [])
                         if o.get("service") in AVA_SCHO_SERVICES]
        service = recommended_web_service(bool(lead.website), lead.website_score)
        if not lead.website:
            opportunities = [{
                "title": "Un sitio propio para el negocio",
                "opportunity": "Crear una web que presente sus servicios y facilite el contacto.",
                "evidence": "La ficha consultada no incluye una URL web; conviene confirmar si ya tienen sitio.",
                "service": service,
            }]
        catalog = AVA_SCHO_SERVICES
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
        result = self._ground_proposal(
            result, lead=lead, audit=audit,
            recommended_service=context.get("recommended_service"),
        )

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
        proposal.approved_at = None
        proposal.reviewed_by_user_id = None
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
        # F7/D7.3: ledger de evidencia — cada dato del email queda atado a su
        # fuente (Google Places oficial / auditoría propia con fecha y URL).
        strength_source_urls = sorted({
            f["source_url"] for f in (audit.findings or [])
            if isinstance(f, dict) and f.get("source_url")
        }) if audit else []
        proposal.ai_reasoning = {
            "model_note": result.model_note,
            "lead_score": lead.lead_score,
            "opportunity_score": lead.opportunity_score,
            "recommended_service": context["recommended_service"],
            "template": "innblock",
            "evidence_ledger": {
                "places": {
                    "source": "Google Maps Platform — Places API (New) / Text Search",
                    "rating": lead.rating,
                    "reviews": lead.reviews_count,
                },
                "audit": {
                    "audit_id": audit.id if audit else None,
                    "audit_version": audit.audit_version if audit else None,
                    "audited_at": audit.audited_at.isoformat() if audit and audit.audited_at else None,
                    "url": audit.url if audit else lead.website,
                    "overall_score": audit.overall_score if audit else None,
                    "findings_count": len(audit.findings or []) if audit else 0,
                    "source_urls": strength_source_urls[:10],
                    "screenshots_count": len(audit.screenshots or []) if audit else 0,
                },
                "grounded_items": {
                    "strengths": len(result.strengths),
                    "opportunities": len(result.opportunities),
                },
            },
        }
        self.db.flush()
        log_event("proposal_generated", proposal_id=proposal.id, lead_id=lead_id, model=provider.name)
        return proposal

    # -------------------------------------------------------- grounding (F7) --
    @staticmethod
    def _ground_proposal(
        result: AIProposal,
        *,
        lead: Lead,
        audit: WebsiteAudit | None,
        recommended_service: str | None = None,
    ) -> AIProposal:
        """F7/D7.2: la propuesta final queda trazada ítem a ítem.

        - Cada strength se normaliza como {text, evidence, kind} (str → dict).
        - Toda oportunidad SIN evidence se descarta y se cuenta en el ledger
          (regla: nada al email sin evidencia — mejor menos ítems y todos reales).
        - El HTML/plain se re-renderiza con los ítems ya normalizados, así lo
          persistido y lo enviado coinciden punto por punto.
        """
        from app.services.emailing.email_html import render_plain_text, render_proposal_email

        strengths_norm: list[dict[str, Any]] = []
        for s in result.strengths or []:
            if isinstance(s, dict) and (s.get("text") or s.get("title")):
                strengths_norm.append({
                    "text": s.get("text") or s.get("title", ""),
                    "evidence": s.get("evidence"),
                    "kind": s.get("kind", "FACT"),
                })
            elif isinstance(s, str) and s.strip():
                strengths_norm.append({"text": s.strip(), "evidence": None, "kind": "FACT"})
        result.strengths = strengths_norm  # type: ignore[assignment]

        opps_norm: list[dict[str, Any]] = []
        for o in result.opportunities or []:
            if not isinstance(o, dict) or not (o.get("evidence") or "").strip():
                # sin evidencia: NO sale hacia el cliente (regla de producto)
                continue
            opps_norm.append({
                "title": o.get("title", ""),
                "opportunity": o.get("opportunity", ""),
                "evidence": o["evidence"],
                "service": o.get("service"),
            })
        result.opportunities = opps_norm

        content = {
            "business_name": lead.business_name,
            "website_score": lead.website_score,
            "opening": result.opening,
            "personalized_observation": result.personalized_observation,
            "strengths": strengths_norm,
            "opportunities": opps_norm,
            "recommended_service": recommended_service or "Nuestra propuesta web",
            "recommended_solution": result.recommended_solution,
            "call_to_action": result.call_to_action,
            "signature": result.signature,
        }
        result.html = render_proposal_email(content)
        result.plain_text = render_plain_text(content)
        return result

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
            ProposalStatus.APPROVED.value,
        ):
            proposal.status = ProposalStatus.READY_FOR_REVIEW.value
            proposal.approved_at = None
            proposal.reviewed_by_user_id = None
        self.db.flush()
        return proposal

    @staticmethod
    def _content_for_render(proposal: Proposal) -> dict[str, Any]:
        return {
            "business_name": proposal.lead.business_name if proposal.lead else "",
            "recommended_service": (proposal.ai_reasoning or {}).get("recommended_service"),
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
