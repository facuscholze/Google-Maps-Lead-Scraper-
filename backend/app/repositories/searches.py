"""Search repository."""
from __future__ import annotations

from sqlalchemy import Select, func, select

from app.models.lead import Lead
from app.models.search import Search, SearchLead
from app.repositories.base import BaseRepository


class SearchRepository(BaseRepository[Search]):
    model = Search

    def _scoped(self, workspace_id: int) -> Select:
        return select(Search).where(Search.workspace_id == workspace_id)

    def get_for_workspace(self, workspace_id: int, search_id: int) -> Search | None:
        return self.db.scalar(
            self._scoped(workspace_id).where(Search.id == search_id)
        )

    def list_for_workspace(self, workspace_id: int) -> list[Search]:
        return list(
            self.db.scalars(
                self._scoped(workspace_id).order_by(Search.created_at.desc())
            ).all()
        )

    def update_totals(self, search: Search) -> None:
        """Refresh aggregate counters from the *qualified* (linked) leads.

        `results_total` (businesses found by the provider) is preserved and
        managed by the pipeline stages; every other counter counts qualified
        leads only.
        """
        base = (
            select(Lead.id)
            .join(SearchLead, SearchLead.lead_id == Lead.id)
            .where(SearchLead.search_id == search.id)
        )

        def n(stmt) -> int:
            return len(self.db.scalars(stmt).all())

        qualified = n(base)
        analyzed = n(base.where(Lead.website_status == "ANALYZED"))
        emails = n(base.where(Lead.email.is_not(None)))
        hot = n(base.where(Lead.lead_temperature == "HOT"))
        warm = n(base.where(Lead.lead_temperature == "WARM"))
        cold = n(base.where(Lead.lead_temperature == "COLD"))
        low = n(base.where(Lead.lead_temperature == "LOW"))

        search.results_qualified = qualified
        search.websites_analyzed = analyzed
        search.emails_found = emails
        search.hot_count = hot
        search.warm_count = warm
        search.cold_count = cold + low
        self.db.add(search)
        self.db.flush()
