"""Website audit repository."""
from __future__ import annotations

from sqlalchemy import select

from app.models.website import WebsiteAudit, WebsitePage
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[WebsiteAudit]):
    model = WebsiteAudit

    def latest_for_lead(self, lead_id: int) -> WebsiteAudit | None:
        return self.db.scalar(
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.id.desc())
            .limit(1)
        )

    def pages_for_audit(self, audit_id: int) -> list[WebsitePage]:
        return list(
            self.db.scalars(
                select(WebsitePage).where(WebsitePage.audit_id == audit_id)
            ).all()
        )
