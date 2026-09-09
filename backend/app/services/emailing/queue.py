"""Email queue & scheduler (spec §46-49, §85-86).

Responsible outreach only:
- human approval is required before anything is queued (enforced by the caller)
- suppression list is always checked
- LOW email confidence is never sent
- per-account daily limits, allowed hours, working days and variable delays
  are enforced by the scheduler
- sending is mocked when no real account/token is available (tests / demo)
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import (
    AccountStatus,
    EmailEventType,
    EmailStatus,
    LeadStatus,
    ProposalStatus,
    RotationStrategy,
)
from app.core.logging import log_event
from app.core.security import decrypt_value
from app.integrations.gmail.sender import MockGmailSender, build_raw_message, send_message
from app.models.emailing import Email, EmailAccount, Proposal, SuppressionEntry
from app.models.lead import Lead
from app.repositories.emailing import (
    EmailAccountRepository,
    EmailRepository,
    ProposalRepository,
    SuppressionRepository,
    mark_lead_suppressed,
)
from app.utils.text import utcnow

logger = logging.getLogger("avascho.queue")


class QueueValidationError(Exception):
    pass


class EmailQueueService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.emails = EmailRepository(db)
        self.accounts = EmailAccountRepository(db)
        self.proposals = ProposalRepository(db)
        self.suppression = SuppressionRepository(db)

    # ------------------------------------------------------------- helpers ---
    def _timezone(self) -> ZoneInfo:
        try:
            return ZoneInfo(settings.default_timezone)
        except Exception:  # noqa: BLE001
            return ZoneInfo("UTC")

    def _within_allowed_window(self, when: datetime) -> bool:
        local = when.astimezone(self._timezone())
        if local.weekday() not in settings.working_day_set:
            return False
        return settings.allowed_hours_start <= local.hour < settings.allowed_hours_end

    # ------------------------------------------------------------- queue -----
    def queue_for_lead(
        self,
        workspace_id: int,
        lead_id: int,
        proposal_id: int,
        account_id: int | None = None,
        strategy: str = RotationStrategy.ROUND_ROBIN.value,
        scheduled_at: datetime | None = None,
        now: datetime | None = None,
    ) -> Email:
        now = now or utcnow()
        lead = self.db.scalar(select(Lead).where(Lead.id == lead_id, Lead.workspace_id == workspace_id))
        if lead is None:
            raise QueueValidationError("Lead not found")
        if lead.status in (LeadStatus.DO_NOT_CONTACT.value, LeadStatus.OPTED_OUT.value):
            raise QueueValidationError("Lead is on the suppression / do-not-contact list")
        if not lead.email:
            raise QueueValidationError("Lead has no public email")
        if lead.email_confidence == "LOW":
            raise QueueValidationError("Cannot send automatically to an email with LOW confidence")
        if self.suppression.is_suppressed(workspace_id, lead.email):
            mark_lead_suppressed(self.db, workspace_id, lead.email)
            raise QueueValidationError("Recipient is on the suppression list (DO_NOT_CONTACT)")

        proposal = self.proposals.get_for_workspace(workspace_id, proposal_id)
        if proposal is None or proposal.lead_id != lead_id:
            raise QueueValidationError("Proposal not found for this lead")
        if proposal.status != ProposalStatus.APPROVED.value:
            raise QueueValidationError("Proposal must be APPROVED before it can be queued")

        account = self._pick_account(workspace_id, account_id, strategy)
        if account is None and settings.allow_mock_email_sending:
            account = self._mock_account(workspace_id)
        if account is None:
            raise QueueValidationError(
                "No connected email account available. Connect a Gmail account first "
                "(or enable mock sending for development)."
            )
        if not self._account_available(account, now):
            raise QueueValidationError(
                f"Account {account.email} reached its daily limit ({account.daily_limit})"
            )

        # variable delay between sends — never in bursts
        delay = random.randint(settings.min_send_delay_seconds, settings.max_send_delay_seconds)
        if scheduled_at is None:
            scheduled_at = now + timedelta(seconds=delay)

        email = Email(
            workspace_id=workspace_id,
            lead_id=lead_id,
            proposal_id=proposal.id,
            gmail_account_id=account.id,
            to_email=lead.email,
            from_email=account.email,
            subject=proposal.subject,
            body_html=proposal.body_html,
            body_plain=proposal.body_plain,
            status=EmailStatus.QUEUED.value,
            scheduled_at=scheduled_at,
        )
        self.db.add(email)
        self.db.flush()
        proposal.status = ProposalStatus.QUEUED.value
        self.db.add(proposal)
        self.db.flush()
        log_event("email_queued", email_id=email.id, lead_id=lead_id, account=account.email)
        return email

    def _pick_account(
        self, workspace_id: int, account_id: int | None, strategy: str
    ) -> EmailAccount | None:
        connected = self.accounts.connected_accounts(workspace_id)
        if not connected:
            return None
        if account_id is not None:
            account = self.accounts.get_for_workspace(workspace_id, account_id)
            return account if account and account.status == AccountStatus.CONNECTED.value else None
        if strategy == RotationStrategy.LEAST_USED.value:
            return min(connected, key=lambda a: (a.sent_today / max(a.daily_limit, 1), a.id))
        if strategy == RotationStrategy.MANUAL.value:
            return None
        # ROUND_ROBIN
        if connected:
            return min(connected, key=lambda a: (a.last_sent_at or datetime.min.replace(tzinfo=utcnow().tzinfo), a.id))
        return None

    @staticmethod
    def _account_available(account: EmailAccount, now: datetime) -> bool:
        today = now.strftime("%Y-%m-%d")
        if account.sent_date != today:
            return True
        return account.sent_today < account.daily_limit

    # ------------------------------------------------------------- send ------
    def send_due(self, workspace_id: int, now: datetime | None = None) -> int:
        """Send all due emails for a workspace respecting limits. Returns count."""
        now = now or utcnow()
        if not self._within_allowed_window(now):
            return 0
        sent = 0
        for email in self.emails.due_emails(workspace_id, now):
            try:
                self._send_one(workspace_id, email)
                sent += 1
            except Exception as exc:  # noqa: BLE001
                email.status = EmailStatus.FAILED.value
                email.error = str(exc)[:1000]
                self.db.add(email)
                self.emails.add_event(workspace_id, email.id, EmailEventType.FAILED.value, str(exc)[:300])
                log_event("email_failed", email_id=email.id, error=str(exc)[:300])
        self.db.commit()
        return sent

    def _send_one(self, workspace_id: int, email: Email) -> None:
        if email.status != EmailStatus.QUEUED.value:
            return
        if self.suppression.is_suppressed(workspace_id, email.to_email):
            email.status = EmailStatus.DO_NOT_CONTACT.value
            self.db.add(email)
            self.emails.add_event(workspace_id, email.id, EmailEventType.OPTED_OUT.value, "suppression list")
            return
        account = self.accounts.get_for_workspace(workspace_id, email.gmail_account_id or 0)
        if account is None or account.status != AccountStatus.CONNECTED.value:
            if settings.allow_mock_email_sending:
                account = self._mock_account(workspace_id)
            else:
                raise QueueValidationError("No connected account")
        if not self._account_available(account, utcnow()):
            raise QueueValidationError(f"Daily limit reached for {account.email}")

        email.status = EmailStatus.PROCESSING.value
        email.attempts += 1
        self.db.add(email)
        self.db.flush()

        try:
            message_id = self._do_send(account, email)
        except Exception as exc:  # noqa: BLE001
            raise
        email.status = EmailStatus.SENT.value
        email.sent_at = utcnow()
        email.message_id = message_id
        self.db.add(email)
        self.accounts.bump_sent(account)
        self.emails.add_event(workspace_id, email.id, EmailEventType.SENT.value)

        lead = self.db.scalar(select(Lead).where(Lead.id == email.lead_id))
        if lead is not None:
            lead.status = LeadStatus.CONTACTED.value
            self.db.add(lead)
        proposal = self.db.get(Proposal, email.proposal_id) if email.proposal_id else None
        if proposal is not None:
            proposal.status = ProposalStatus.SENT.value
            self.db.add(proposal)
        self.db.flush()
        log_event("email_sent", email_id=email.id, lead_id=email.lead_id, account=account.email)

    def _do_send(self, account: EmailAccount, email: Email) -> str:
        if settings.allow_mock_email_sending and not self._has_live_token(account):
            return MockGmailSender().send(
                to_email=email.to_email,
                from_email=account.email,
                subject=email.subject or "",
                body_html=email.body_html,
                body_plain=email.body_plain,
            )["id"]
        access_token = self._access_token(account)
        raw = build_raw_message(
            to_email=email.to_email,
            from_email=account.email,
            subject=email.subject or "",
            body_html=email.body_html,
            body_plain=email.body_plain,
        )
        result = send_message(access_token, raw)
        return result.get("id", "")

    @staticmethod
    def _has_live_token(account: EmailAccount) -> bool:
        return bool(account.access_token_encrypted)

    def _access_token(self, account: EmailAccount) -> str:
        if not account.refresh_token_encrypted:
            raise QueueValidationError("Account has no refresh token")
        from app.integrations.gmail.oauth import refresh_access_token

        refresh_token = decrypt_value(account.refresh_token_encrypted)
        access_token, expires_in = refresh_access_token(refresh_token)
        return access_token

    def _mock_account(self, workspace_id: int) -> EmailAccount:
        """Demo account used only for offline sends (tests / demo)."""
        account = self.db.scalar(
            select(EmailAccount).where(
                EmailAccount.workspace_id == workspace_id,
                EmailAccount.provider == "mock",
                EmailAccount.email == "demo@avascho.local",
            )
        )
        if account is None:
            account = EmailAccount(
                workspace_id=workspace_id,
                email="demo@avascho.local",
                provider="mock",
                status=AccountStatus.CONNECTED.value,
                daily_limit=settings.daily_email_limit,
            )
            self.db.add(account)
            self.db.flush()
        return account
