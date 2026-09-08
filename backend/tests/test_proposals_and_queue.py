"""Proposal + queue + suppression + sending-limit tests (spec §42-49)."""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.enums import EmailStatus, ProposalStatus
from app.core.seed import seed_demo
from app.models.emailing import Email, EmailAccount, EmailEvent, Proposal, SuppressionEntry
from app.models.jobs import Job
from app.models.lead import Lead
from app.models.search import Search, SearchLead, SearchPreset
from app.models.website import WebsiteAudit, WebsitePage
from app.repositories.emailing import EmailAccountRepository, EmailRepository, SuppressionRepository
from app.services.emailing.proposal_service import ProposalService
from app.services.emailing.queue import EmailQueueService, QueueValidationError
from app.services.pipeline import SearchPipeline
from app.utils.text import utcnow


@pytest.fixture(autouse=True)
def _clean_domain(db_session):
    for model in (
        EmailEvent, Email, EmailAccount, Proposal, SuppressionEntry,
        WebsitePage, WebsiteAudit, Job, SearchLead, Lead, Search, SearchPreset,
    ):
        db_session.execute(model.__table__.delete())
    db_session.commit()
    yield


@pytest.fixture()
def ready_lead(db_session, workspace):
    seed_demo(db_session)
    search = Search(
        workspace_id=workspace.id, query="Clínicas, Montevideo", category="Clínicas",
        location="Montevideo", min_reviews=100, min_rating=4.3, max_results=25,
    )
    db_session.add(search)
    db_session.commit()
    SearchPipeline(db_session).run(search.id)
    lead = db_session.scalar(
        select(Lead).where(Lead.email.is_not(None), Lead.email_confidence == "HIGH", Lead.lead_temperature == "HOT")
    )
    if lead is None:
        lead = db_session.scalar(select(Lead).where(Lead.email.is_not(None), Lead.email_confidence == "HIGH"))
    assert lead is not None, "expected a lead with HIGH confidence email"
    return lead


def test_proposal_lifecycle(db_session, workspace, ready_lead):
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, ready_lead.id)
    assert proposal.status == ProposalStatus.READY_FOR_REVIEW.value
    assert proposal.subject and proposal.body_html and proposal.body_plain
    assert "AvaScho" in (proposal.body_html or "") or "AVASCHO" in (proposal.body_html or "")
    # human edit keeps plain/html consistent
    service.update_from_editor(proposal, {"subject": "Tema editado", "personalized_observation": "Texto humano."})
    assert proposal.subject == "Tema editado"
    service.approve(proposal, user_id=1)
    assert proposal.status == ProposalStatus.APPROVED.value


def test_proposal_is_personalized(ready_lead):
    """Subject/body must reference the real business, not a template name."""
    import re
    from app.services.emailing.proposal import ProposalWriter

    audit = None
    content = {
        "business_name": ready_lead.business_name,
        "rating": ready_lead.rating,
        "reviews": ready_lead.reviews_count,
        "website_score": ready_lead.website_score,
        "opportunities": ready_lead.detected_opportunities or [],
        "strengths": [s.get("text") if isinstance(s, dict) else s for s in (ready_lead.website_strengths or [])],
        "recommended_service": ready_lead.recommended_service,
    }
    proposal = ProposalWriter().build(content)
    first_word = ready_lead.business_name.split()[0].lower()
    assert first_word in proposal.subject.lower()
    assert not re.search(r"\b40%?\b|GANÁ|URGENTE", proposal.subject, re.I)


def test_queue_requires_approval(db_session, workspace, ready_lead):
    seed_demo(db_session)
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, ready_lead.id)
    with pytest.raises(QueueValidationError):
        EmailQueueService(db_session).queue_for_lead(workspace.id, ready_lead.id, proposal.id)


def test_queue_and_mock_send(db_session, workspace, ready_lead, monkeypatch):
    seed_demo(db_session)
    settings.allow_mock_email_sending = True
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, ready_lead.id)
    service.approve(proposal, user_id=1)
    email = EmailQueueService(db_session).queue_for_lead(
        workspace.id, ready_lead.id, proposal.id, scheduled_at=utcnow()
    )
    assert email.status == EmailStatus.QUEUED.value
    sent = []
    monkeypatch.setattr(
        "app.integrations.gmail.sender.MockGmailSender.send",
        lambda self, **kwargs: sent.append(kwargs) or {"id": "m1"},
    )
    EmailQueueService(db_session).send_due(workspace.id, now=utcnow() + timedelta(seconds=30))
    db_session.refresh(email)
    assert email.status == EmailStatus.SENT.value
    assert sent and sent[0]["to_email"] == ready_lead.email
    db_session.refresh(ready_lead)
    assert ready_lead.status == "CONTACTED"


def test_suppression_blocks_send(db_session, workspace, ready_lead):
    seed_demo(db_session)
    repo = SuppressionRepository(db_session)
    repo.add(workspace.id, ready_lead.email, "OPT_OUT")
    db_session.commit()
    assert repo.is_suppressed(workspace.id, ready_lead.email)
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, ready_lead.id)
    service.approve(proposal, user_id=1)
    with pytest.raises(QueueValidationError):
        EmailQueueService(db_session).queue_for_lead(workspace.id, ready_lead.id, proposal.id)


def test_daily_limit_enforced_at_send(db_session, workspace, ready_lead):
    seed_demo(db_session)
    account = EmailAccountRepository(db_session).create(
        workspace_id=workspace.id, email="ventas@avascho.local", provider="mock",
        status="CONNECTED", daily_limit=2,
    )
    db_session.commit()
    service = ProposalService(db_session)
    queue = EmailQueueService(db_session)
    for _ in range(3):
        proposal = service.generate(workspace.id, ready_lead.id)
        service.approve(proposal, user_id=1)
        queue.queue_for_lead(
            workspace.id, ready_lead.id, proposal.id, account_id=account.id, scheduled_at=utcnow()
        )
    now = utcnow() + timedelta(minutes=1)
    queue.send_due(workspace.id, now=now)
    statuses = db_session.execute(select(Email.status)).all()
    assert sum(1 for (s,) in statuses if s == EmailStatus.SENT.value) == 2
    assert sum(1 for (s,) in statuses if s == EmailStatus.FAILED.value) == 1
    db_session.refresh(account)
    assert account.sent_today == 2


def test_low_confidence_never_queued(db_session, workspace):
    seed_demo(db_session)
    lead = Lead(
        workspace_id=workspace.id,
        place_id="mockplace:low-conf",
        business_name="Negocio Test",
        email="test@example.com",
        email_confidence="LOW",
        reviews_count=10,
    )
    db_session.add(lead)
    db_session.commit()
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, lead.id)
    service.approve(proposal, user_id=1)
    with pytest.raises(QueueValidationError):
        EmailQueueService(db_session).queue_for_lead(workspace.id, lead.id, proposal.id)
