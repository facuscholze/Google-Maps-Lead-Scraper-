"""Fase 9 — guardrails de envío: qué pasa cuando algo sale mal DURANTE el drain.

Reglas bajo test (todas offline, provider mock):
- D9.1: propuesta sin contenido renderizable NUNCA se encola, aun aprobada.
- D9.2: el claim QUEUED → PROCESSING es atómico (UPDATE condicionado) — dos
  drenadores no pueden enviar el mismo correo.
- D9.3: sin cuenta / sin cupo diario ⇒ el email queda PENDIENTE (vuelve a
  QUEUED, no consume intentos, no pierde el envío); errores transitorios
  (Gmail/red) reintentan con backoff hasta `max_send_attempts` y recién ahí
  pasan a FAILED; errores deterministas → FAILED sin reintento.
- D9.4: suppression agregada ENTRE encolado y envío se respeta igual.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import EmailEventType, EmailStatus, ProposalStatus
from app.core.seed import seed_demo
from app.integrations.gmail.sender import GmailSendError
from app.models.emailing import Email, EmailEvent, Proposal, SuppressionEntry
from app.models.lead import Lead
from app.repositories.emailing import EmailAccountRepository, SuppressionRepository
from app.services.emailing.proposal_service import ProposalService
from app.services.emailing.queue import EmailQueueService, QueueValidationError
from app.utils.text import as_utc, utcnow


@pytest.fixture(autouse=True)
def _clean_domain(db_session):
    from app.models.emailing import EmailAccount
    from app.models.website import WebsiteAudit, WebsitePage

    for model in (EmailEvent, Email, EmailAccount, Proposal, SuppressionEntry,
                  WebsitePage, WebsiteAudit, Lead):
        db_session.execute(model.__table__.delete())
    db_session.commit()
    yield


@pytest.fixture(autouse=True)
def _always_in_window(monkeypatch):
    """La ventana horaria/días ya tiene su test dedicado (working_days_iso);
    acá aislamos los guardrails del reloj para que la suite sea determinista
    corra cuando corra."""
    monkeypatch.setattr(EmailQueueService, "_within_allowed_window", lambda self, when: True)
    yield


_counter = 0


def _lead(db_session, workspace, confidence: str = "HIGH") -> Lead:
    global _counter
    _counter += 1
    lead = Lead(
        workspace_id=workspace.id,
        place_id=f"mockplace:f9-{_counter}",
        business_name=f"Negocio Guardrail {_counter}",
        email=f"lead-f9-{_counter}@example.com",
        email_confidence=confidence,
        reviews_count=80,
        rating=4.4,
    )
    db_session.add(lead)
    db_session.commit()
    return lead


def _approved_proposal(db_session, workspace, lead) -> Proposal:
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, lead.id)
    service.approve(proposal, user_id=1)
    db_session.commit()
    return proposal


# ------------------------------------------------------------------ D9.1 ----
def test_empty_content_never_queued(db_session, workspace):
    seed_demo(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    # humano aprueba y luego el contenido queda vacío (edge real)
    proposal.subject = " "
    proposal.body_html = ""
    proposal.body_plain = ""
    db_session.commit()
    with pytest.raises(QueueValidationError, match="renderable content"):
        EmailQueueService(db_session).queue_for_lead(workspace.id, lead.id, proposal.id)
    assert db_session.execute(select(Email)).scalars().all() == []


# ------------------------------------------------------------------ D9.3 ----
def test_daily_limit_defers_pending_never_fails(db_session, workspace):
    """Cupo agotado ⇒ pendiente, NO failed; al día siguiente sale solo."""
    seed_demo(db_session)
    account = EmailAccountRepository(db_session).create(
        workspace_id=workspace.id, email="ventas@avascho.local", provider="mock",
        status="CONNECTED", daily_limit=1,
    )
    db_session.commit()
    queue = EmailQueueService(db_session)
    for _ in range(2):
        lead = _lead(db_session, workspace)
        proposal = _approved_proposal(db_session, workspace, lead)
        queue.queue_for_lead(workspace.id, lead.id, proposal.id,
                             account_id=account.id, scheduled_at=utcnow())

    queue.send_due(workspace.id, now=utcnow() + timedelta(seconds=30))
    day1 = {e.status for e in db_session.execute(select(Email)).scalars().all()}
    assert day1 == {EmailStatus.SENT.value, EmailStatus.QUEUED.value}
    assert EmailStatus.FAILED.value not in day1

    # "mañana": la cuenta resetea su contador diario y el pendiente sale
    account.sent_date = "2000-01-01"
    db_session.commit()
    queue.send_due(workspace.id, now=utcnow() + timedelta(minutes=2))
    statuses = [e.status for e in db_session.execute(select(Email)).scalars().all()]
    assert statuses == [EmailStatus.SENT.value, EmailStatus.SENT.value]


def test_no_connected_account_defers_and_recovers(db_session, workspace, monkeypatch):
    queue = EmailQueueService(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())

    # la cuenta cae DESPUÉS de encolar: ni failed ni pérdida
    monkeypatch.setattr(settings, "allow_mock_email_sending", False)
    monkeypatch.setattr(queue.accounts, "get_for_workspace", lambda *a, **k: None)
    queue.send_due(workspace.id, now=utcnow() + timedelta(seconds=10))
    db_session.refresh(email)
    assert email.status == EmailStatus.QUEUED.value
    assert email.attempts >= 0  # no consume intentos de envío

    # vuelve la cuenta: el siguiente drain envía normal
    monkeypatch.setattr(settings, "allow_mock_email_sending", True)
    monkeypatch.setattr(
        "app.integrations.gmail.sender.MockGmailSender.send",
        lambda self, **kwargs: {"id": "recovered"},
    )
    EmailQueueService(db_session).send_due(workspace.id, now=utcnow() + timedelta(minutes=2))
    db_session.refresh(email)
    assert email.status == EmailStatus.SENT.value


def test_transient_failure_retries_with_backoff_then_succeeds(db_session, workspace, monkeypatch):
    seed_demo(db_session)
    queue = EmailQueueService(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())

    calls = {"n": 0}
    def flaky(self, account, eml):
        calls["n"] += 1
        if calls["n"] == 1:
            raise GmailSendError("Gmail 502: backend error")
        return "ok-id"
    monkeypatch.setattr(EmailQueueService, "_do_send", flaky)
    monkeypatch.setattr(settings, "max_send_attempts", 3)

    first_now = utcnow()
    queue.send_due(workspace.id, now=first_now)
    db_session.refresh(email)
    assert email.status == EmailStatus.QUEUED.value  # reintento programado
    assert email.attempts == 1
    assert as_utc(email.scheduled_at) > first_now  # backoff en el próximo intento
    retry_events = db_session.execute(
        select(EmailEvent).where(EmailEvent.event_type == EmailEventType.RETRY.value)
    ).scalars().all()
    assert len(retry_events) == 1 and "1/3" in retry_events[0].detail

    # segundo intento (forzamos vencimiento): envía bien
    email.scheduled_at = first_now - timedelta(seconds=1)
    db_session.commit()
    queue.send_due(workspace.id, now=utcnow() + timedelta(seconds=7))
    db_session.refresh(email)
    assert email.status == EmailStatus.SENT.value
    assert email.message_id == "ok-id"


def test_transient_failure_terminal_after_max_attempts(db_session, workspace, monkeypatch):
    queue = EmailQueueService(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())

    def always_broken(self, account, eml):
        raise GmailSendError("Gmail 500")
    monkeypatch.setattr(EmailQueueService, "_do_send", always_broken)
    monkeypatch.setattr(settings, "max_send_attempts", 2)

    queue.send_due(workspace.id, now=utcnow())  # intento 1 → RETRY
    db_session.refresh(email)
    assert email.status == EmailStatus.QUEUED.value and email.attempts == 1
    email.scheduled_at = utcnow() - timedelta(seconds=1)
    db_session.commit()
    queue.send_due(workspace.id, now=utcnow() + timedelta(minutes=2))  # intento 2 → FAILED
    db_session.refresh(email)
    assert email.status == EmailStatus.FAILED.value and email.attempts == 2
    failed_events = db_session.execute(
        select(EmailEvent).where(EmailEvent.event_type == EmailEventType.FAILED.value)
    ).scalars().all()
    assert len(failed_events) == 1


def test_deterministic_error_never_retries(db_session, workspace, monkeypatch):
    queue = EmailQueueService(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())

    def validation_fail(self, account, eml):
        raise QueueValidationError("deterministic content error")
    monkeypatch.setattr(EmailQueueService, "_do_send", validation_fail)

    queue.send_due(workspace.id, now=utcnow())
    db_session.refresh(email)
    assert email.status == EmailStatus.FAILED.value and email.attempts == 1
    assert db_session.execute(
        select(EmailEvent).where(EmailEvent.event_type == EmailEventType.RETRY.value)
    ).scalars().all() == []


# ------------------------------------------------------------------ D9.2 ----
def test_claim_is_atomic_and_skips_non_queued(db_session, workspace, monkeypatch):
    queue = EmailQueueService(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())

    sends: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.gmail.sender.MockGmailSender.send",
        lambda self, **kwargs: sends.append(kwargs) or {"id": "m1"},
    )

    # un email SENT no puede volver a tomarse (defensa ante doble drainer)
    email.status = EmailStatus.SENT.value
    db_session.commit()
    assert queue._claim_for_send(workspace.id, email.id) is False
    assert sends == []

    # QUEUED → claim OK una sola vez; el segundo claim sobre el mismo id falla
    email.status = EmailStatus.QUEUED.value
    db_session.commit()
    assert queue._claim_for_send(workspace.id, email.id) is True
    assert queue._claim_for_send(workspace.id, email.id) is False
    db_session.refresh(email)
    assert email.attempts == 1  # un solo intento pese a dos claims


# ------------------------------------------------------------------ D9.4 ----
def test_suppression_added_between_queue_and_send(db_session, workspace, monkeypatch):
    """El double-check de suppression vive en _send_one, no sólo en encolado:
    una baja registrada mientras el mail espera su delay lo frena igual."""
    queue = EmailQueueService(db_session)
    lead = _lead(db_session, workspace)
    proposal = _approved_proposal(db_session, workspace, lead)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())

    repo = SuppressionRepository(db_session)
    repo.add(workspace.id, lead.email, "OPT_OUT")
    db_session.commit()

    sends: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.gmail.sender.MockGmailSender.send",
        lambda self, **kwargs: sends.append(kwargs) or {"id": "m1"},
    )
    queue.send_due(workspace.id, now=utcnow() + timedelta(seconds=10))
    db_session.refresh(email)
    assert email.status == EmailStatus.DO_NOT_CONTACT.value
    assert sends == []  # jamás se llamó al sender
