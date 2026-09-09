"""Lead repository with scoping, filtering, and the funnel aggregation."""
from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.emailing import Proposal
from app.models.lead import Lead
from app.models.search import SearchLead
from app.repositories.base import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    model = Lead

    # ------------------------------------------------------------- queries ---
    def _scoped(self, workspace_id: int) -> Select:
        return select(Lead).where(Lead.workspace_id == workspace_id)

    def get_for_workspace(self, workspace_id: int, lead_id: int) -> Lead | None:
        return self.db.scalar(self._scoped(workspace_id).where(Lead.id == lead_id))

    def get_by_place_id(self, workspace_id: int, place_id: str) -> Lead | None:
        return self.db.scalar(self._scoped(workspace_id).where(Lead.place_id == place_id))

    def list_for_workspace(
        self,
        workspace_id: int,
        search_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
        filters: dict[str, Any] | None = None,
        linked_only: bool = True,
    ) -> tuple[list[Lead], int]:
        stmt = self._scoped(workspace_id)
        if search_id is not None:
            stmt = stmt.join(SearchLead).where(SearchLead.search_id == search_id)
        elif linked_only:
            # By default the list shows qualified leads (matched in ≥1 search).
            stmt = stmt.where(
                Lead.id.in_(select(SearchLead.lead_id).scalar_subquery())
            )
        stmt = self._apply_filters(stmt, filters or {})
        count = self.db.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        ) or 0
        stmt = stmt.order_by(Lead.lead_score.desc().nullslast(), Lead.reviews_count.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        return list(self.db.scalars(stmt).all()), count

    @staticmethod
    def _apply_filters(stmt: Select, filters: dict[str, Any]) -> Select:
        temperature = filters.get("temperature")
        if temperature:
            values = temperature if isinstance(temperature, list) else [temperature]
            stmt = stmt.where(Lead.lead_temperature.in_(values))
        min_lead = filters.get("min_lead_score")
        if min_lead is not None:
            stmt = stmt.where(Lead.lead_score >= int(min_lead))
        min_opp = filters.get("min_opportunity_score")
        if min_opp is not None:
            stmt = stmt.where(Lead.opportunity_score >= int(min_opp))
        min_web = filters.get("min_website_score")
        if min_web is not None:
            stmt = stmt.where(Lead.website_score >= float(min_web))
        min_reviews = filters.get("min_reviews")
        if min_reviews is not None:
            stmt = stmt.where(Lead.reviews_count >= int(min_reviews))
        min_rating = filters.get("min_rating")
        if min_rating is not None:
            stmt = stmt.where(Lead.rating >= float(min_rating))
        has_website = filters.get("has_website")
        if has_website is not None:
            stmt = stmt.where(
                Lead.website.is_not(None) if has_website else Lead.website.is_(None)
            )
        has_email = filters.get("has_email")
        if has_email is not None:
            stmt = stmt.where(
                Lead.email.is_not(None) if has_email else Lead.email.is_(None)
            )
        conf = filters.get("email_confidence")
        if conf:
            stmt = stmt.where(Lead.email_confidence == conf)
        service = filters.get("recommended_service")
        if service:
            stmt = stmt.where(Lead.recommended_service == service)
        status = filters.get("status")
        if status:
            stmt = stmt.where(Lead.status == status)
        query = filters.get("q")
        if query:
            stmt = stmt.where(Lead.business_name.ilike(f"%{query}%"))
        return stmt

    # ------------------------------------------------------------- funnel -----
    def funnel(self, workspace_id: int) -> dict[str, int]:
        """Counts for the pipeline funnel (spec §32).

        `businesses_found` counts unique places ever stored in the workspace;
        all downstream stages are computed over the qualified population (leads
        that matched at least one search filter).
        """
        scoped = self._scoped(workspace_id)

        def count_over(stmt: Select) -> int:
            return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        total_found = count_over(scoped)
        qualified_ids = (
            select(Lead.id)
            .join(SearchLead, SearchLead.lead_id == Lead.id)
            .where(Lead.workspace_id == workspace_id)
        )
        qualified_count = count_over(qualified_ids)
        qualified_sub = qualified_ids.scalar_subquery()
        lead_of = Lead.id.in_(qualified_sub)

        def population(**where: Any) -> Select:
            stmt = scoped.where(lead_of)
            for col, value in where.items():
                stmt = stmt.where(getattr(Lead, col) == value)
            return stmt

        with_website = count_over(population().where(Lead.website.is_not(None)))
        websites_analyzed = count_over(population(website_status="ANALYZED"))
        emails_found = count_over(population().where(Lead.email.is_not(None)))
        potential = count_over(
            population().where(
                Lead.lead_temperature.in_(["HOT", "WARM"]),
                Lead.recommended_action.in_(["CONTACT_NOW", "REVIEW_FIRST"]),
            )
        )
        proposals = count_over(
            population().join(Proposal, Proposal.lead_id == Lead.id).where(
                Proposal.status.notin_(["DRAFT", "CANCELLED"])
            )
        )
        approved = count_over(
            population().join(Proposal, Proposal.lead_id == Lead.id).where(
                Proposal.status == "APPROVED"
            )
        )
        sent = count_over(population(status="CONTACTED"))
        replied = count_over(population(status="REPLIED"))
        return {
            "businesses_found": total_found,
            "businesses_qualified": qualified_count,
            "websites_analyzed": websites_analyzed,
            "with_website": with_website,
            "emails_found": emails_found,
            "potential_clients": potential,
            "proposals_generated": proposals,
            "approved": approved,
            "sent": sent,
            "replied": replied,
        }