"""Repositories for proposals, email accounts, emails, suppression."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.enums import EmailEventType, EmailStatus, ProposalStatus
from app.models.emailing import (
    Email,
    EmailAccount,
    EmailEvent,
    Proposal,
    SuppressionEntry,
)
from app.models.lead import Lead
from app.repositories.base import BaseRepository
from app.utils.text import utcnow


class ProposalRepository(BaseRepository[Proposal]):
    model = Proposal

    def get_for_workspace(self, workspace_id: int, proposal_id: int) -> Proposal | None:
        return self.db.scalar(
            select(Proposal).where(
                Proposal.workspace_id == workspace_id, Proposal.id == proposal_id
            )
        )

    def list_for_workspace(self, workspace_id: int, lead_id: int | None = None) -> list[Proposal]:
        stmt = select(Proposal).where(Proposal.workspace_id == workspace_id)
        if lead_id is not None:
            stmt = stmt.where(Proposal.lead_id == lead_id)
        return list(self.db.scalars(stmt.order_by(Proposal.id.desc())).all())

    def latest_for_lead(self, lead_id: int) -> Proposal | None:
        return self.db.scalar(
            select(Proposal)
            .where(Proposal.lead_id == lead_id)
            .order_by(Proposal.id.desc())
            .limit(1)
        )

    def set_status(self, proposal: Proposal, status: ProposalStatus) -> None:
        proposal.status = status.value
        if status == ProposalStatus.APPROVED:
            proposal.approved_at = utcnow()
        self.db.add(proposal)
        self.db.flush()


class EmailAccountRepository(BaseRepository[EmailAccount]):
    model = EmailAccount

    def get_for_workspace(self, workspace_id: int, account_id: int) -> EmailAccount | None:
        return self.db.scalar(
            select(EmailAccount).where(
                EmailAccount.workspace_id == workspace_id, EmailAccount.id == account_id
            )
        )

    def list_for_workspace(self, workspace_id: int) -> list[EmailAccount]:
        return list(
            self.db.scalars(
                select(EmailAccount)
                .where(EmailAccount.workspace_id == workspace_id)
                .order_by(EmailAccount.id)
            ).all()
        )

    def connected_accounts(self, workspace_id: int) -> list[EmailAccount]:
        return list(
            self.db.scalars(
                select(EmailAccount).where(
                    EmailAccount.workspace_id == workspace_id,
                    EmailAccount.status == "CONNECTED",
                )
            ).all()
        )

    def bump_sent(self, account: EmailAccount, when: datetime | None = None) -> None:
        now = when or utcnow()
        today = now.strftime("%Y-%m-%d")
        if account.sent_date != today:
            account.sent_today = 0
            account.sent_date = today
        account.sent_today += 1
        account.last_sent_at = now
        self.db.add(account)
        self.db.flush()


class EmailRepository(BaseRepository[Email]):
    model = Email

    def get_for_workspace(self, workspace_id: int, email_id: int) -> Email | None:
        return self.db.scalar(
            select(Email).where(
                Email.workspace_id == workspace_id, Email.id == email_id
            )
        )

    def list_for_workspace(self, workspace_id: int, status: str | None = None) -> list[Email]:
        stmt = select(Email).where(Email.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Email.status == status)
        return list(self.db.scalars(stmt.order_by(Email.id.desc())).all())

    def due_emails(self, workspace_id: int, now: datetime) -> list[Email]:
        return list(
            self.db.scalars(
                select(Email).where(
                    Email.workspace_id == workspace_id,
                    Email.status == EmailStatus.QUEUED.value,
                    Email.scheduled_at <= now,
                ).order_by(Email.scheduled_at)
            ).all()
        )

    def add_event(self, workspace_id: int, email_id: int, event_type: str, detail: str | None = None) -> None:
        self.db.add(
            EmailEvent(
                workspace_id=workspace_id,
                email_id=email_id,
                event_type=event_type,
                detail=detail,
                occurred_at=utcnow(),
            )
        )
        self.db.flush()


class SuppressionRepository(BaseRepository[SuppressionEntry]):
    model = SuppressionEntry

    def is_suppressed(self, workspace_id: int, email: str) -> bool:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(SuppressionEntry)
                .where(
                    SuppressionEntry.workspace_id == workspace_id,
                    SuppressionEntry.email == email.lower(),
                    SuppressionEntry.active.is_(True),
                )
            )
            or 0
        ) > 0

    def add(self, workspace_id: int, email: str, reason: str, note: str | None = None) -> SuppressionEntry:
        entry = self.create(
            workspace_id=workspace_id,
            email=email.lower(),
            reason=reason,
            note=note,
        )
        self.db.flush()
        return entry

    def list_for_workspace(self, workspace_id: int, search: str | None = None) -> list[SuppressionEntry]:
        stmt = select(SuppressionEntry).where(SuppressionEntry.workspace_id == workspace_id)
        if search:
            stmt = stmt.where(SuppressionEntry.email.ilike(f"%{search.strip()}%"))
        return list(self.db.scalars(stmt.order_by(SuppressionEntry.id.desc())).all())

    def remove(self, workspace_id: int, entry_id: int) -> bool:
        entry = self.db.scalar(
            select(SuppressionEntry).where(
                SuppressionEntry.workspace_id == workspace_id,
                SuppressionEntry.id == entry_id,
            )
        )
        if entry is None:
            return False
        entry.active = False
        self.db.add(entry)
        self.db.flush()
        return True

    def import_emails(self, workspace_id: int, emails: list[str], reason: str = "IMPORT") -> int:
        added = 0
        for email in emails:
            email = email.strip().lower()
            if not email or self.is_suppressed(workspace_id, email):
                continue
            self.add(workspace_id, email, reason)
            added += 1
        self.db.flush()
        return added


def mark_lead_suppressed(db: Session, workspace_id: int, email: str) -> None:
    """Mark every lead with this email as DO_NOT_CONTACT (privacy-friendly)."""
    db.execute(
        update(Lead)
        .where(
            Lead.workspace_id == workspace_id,
            Lead.email == email.lower(),
        )
        .values(status="DO_NOT_CONTACT", recommended_action="DO_NOT_CONTACT")
    )
    db.flush()
