"""Dashboard & analytics aggregation (spec §31-32, §67, §77, §84)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.emailing import Email, EmailAccount, Proposal, SuppressionEntry
from app.models.jobs import Job
from app.models.lead import Lead
from app.models.search import Search
from app.repositories.leads import LeadRepository
from app.utils.text import utcnow


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspace_id: int | None = None

    def set_workspace(self, workspace_id: int) -> "DashboardService":
        self.workspace_id = workspace_id
        return self

    def _scalar_count(self, stmt) -> int:
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    def build(self, workspace_id: int) -> dict[str, Any]:
        lead_repo = LeadRepository(self.db)
        funnel = lead_repo.funnel(workspace_id)
        ws = workspace_id

        base_leads = select(Lead).where(Lead.workspace_id == ws)
        total_leads = funnel["businesses_found"]

        # score averages over scored leads
        avg_lead = self.db.scalar(select(func.avg(Lead.lead_score)).where(Lead.workspace_id == ws, Lead.lead_score.is_not(None)))
        avg_web = self.db.scalar(select(func.avg(Lead.website_score)).where(Lead.workspace_id == ws, Lead.website_score.is_not(None)))
        avg_opp = self.db.scalar(select(func.avg(Lead.opportunity_score)).where(Lead.workspace_id == ws, Lead.opportunity_score.is_not(None)))

        hot = self._scalar_count(base_leads.where(Lead.lead_temperature == "HOT"))
        warm = self._scalar_count(base_leads.where(Lead.lead_temperature == "WARM"))
        potential = funnel["potential_clients"]
        websites_audited = funnel["websites_analyzed"]
        emails_found = funnel["emails_found"]

        proposals_total = self._scalar_count(select(Proposal).where(Proposal.workspace_id == ws))
        proposals_ready = self._scalar_count(
            select(Proposal).where(
                Proposal.workspace_id == ws,
                Proposal.status.in_(["READY_FOR_REVIEW", "APPROVED", "QUEUED"]),
            )
        )
        emails_sent = self._scalar_count(select(Email).where(Email.workspace_id == ws, Email.status == "SENT"))
        emails_queued = self._scalar_count(select(Email).where(Email.workspace_id == ws, Email.status == "QUEUED"))
        replies = self._scalar_count(base_leads.where(Lead.status == "REPLIED"))
        converted = 0  # no CRM webhook yet; kept as explicit metric (0 = no signal)

        accounts = self.db.scalars(
            select(EmailAccount).where(EmailAccount.workspace_id == ws, EmailAccount.status == "CONNECTED")
        ).all()
        suppression_count = self._scalar_count(
            select(SuppressionEntry).where(SuppressionEntry.workspace_id == ws, SuppressionEntry.active.is_(True))
        )
        running_jobs = self._scalar_count(
            select(Job).where(Job.workspace_id == ws, Job.status == "RUNNING")
        )

        recent_searches = list(
            self.db.scalars(select(Search).where(Search.workspace_id == ws).order_by(Search.id.desc()).limit(6)).all()
        )
        top_leads = list(
            self.db.scalars(
                select(Lead)
                .where(Lead.workspace_id == ws, Lead.lead_score.is_not(None))
                .order_by(Lead.lead_score.desc(), Lead.reviews_count.desc())
                .limit(6)
            ).all()
        )
        review_queue = list(
            self.db.scalars(
                select(Proposal)
                .where(Proposal.workspace_id == ws, Proposal.status.in_(["READY_FOR_REVIEW", "APPROVED"]))
                .order_by(Proposal.updated_at.desc())
                .limit(10)
            ).all()
        )

        return {
            "cards": {
                "total_leads": total_leads,
                "potential_clients": potential,
                "hot_leads": hot,
                "warm_leads": warm,
                "websites_audited": websites_audited,
                "emails_found": emails_found,
                "proposals_ready": proposals_ready,
                "emails_sent": emails_sent,
                "replies": replies,
            },
            "averages": {
                "avg_lead_score": round(avg_lead, 1) if avg_lead else None,
                "avg_website_score": round(avg_web, 1) if avg_web else None,
                "avg_opportunity_score": round(avg_opp, 1) if avg_opp else None,
            },
            "funnel": funnel,
            "analytics": {
                "total_searches": len(recent_searches),
                "total_leads": total_leads,
                "qualified": funnel["businesses_qualified"],
                "websites_analyzed": websites_audited,
                "emails_found": emails_found,
                "potential_clients": potential,
                "proposals_generated": funnel["proposals_generated"],
                "approved": funnel["approved"],
                "sent": funnel["sent"],
                "replied": replies,
                "converted": converted,
                "emails_queued": emails_queued,
                "emails_sent": emails_sent,
                "suppression_entries": suppression_count,
                "connected_accounts": len(accounts),
                "running_jobs": running_jobs,
                "proposals_total": proposals_total,
            },
            "recent_searches": [
                {
                    "id": s.id,
                    "query": s.query,
                    "status": s.status,
                    "results_total": s.results_total,
                    "results_qualified": s.results_qualified,
                    "emails_found": s.emails_found,
                    "hot": s.hot_count,
                    "created_at": s.created_at.isoformat(),
                }
                for s in recent_searches
            ],
            "top_leads": [
                {
                    "id": l.id,
                    "business_name": l.business_name,
                    "rating": l.rating,
                    "reviews_count": l.reviews_count,
                    "website_score": l.website_score,
                    "opportunity_score": l.opportunity_score,
                    "lead_score": l.lead_score,
                    "lead_temperature": l.lead_temperature,
                    "email": l.email,
                    "why_this_lead": l.why_this_lead,
                }
                for l in top_leads
            ],
            "review_queue": [
                {
                    "proposal_id": p.id,
                    "lead_id": p.lead_id,
                    "business_name": p.lead.business_name if p.lead else None,
                    "lead_score": p.lead.lead_score if p.lead else None,
                    "opportunity_score": p.lead.opportunity_score if p.lead else None,
                    "email": p.lead.email if p.lead else None,
                    "email_confidence": p.lead.email_confidence if p.lead else None,
                    "status": p.status,
                    "subject": p.subject,
                    "version": p.version,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                }
                for p in review_queue
            ],
            "health": {
                "time": utcnow().isoformat(),
                "funnel_consistent": funnel["potential_clients"] <= funnel["emails_found"] + 1
                or funnel["emails_found"] == 0,
            },
        }
