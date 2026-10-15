"""Fase 10 — visibilidad del canal de envío + cierre de BUG-07/08 (AUDIT.md).

- GET /emails/{id} expone `attempts` y el timeline de eventos cronológico
  (RETRY/SENT/FAILED), incluido el detalle de fallback mock (BUG-08).
- BUG-07: la decisión robots.txt vuelve a ser async — la lectura de red
  `robots.read()` corre en un thread, jamás adentro del event loop.
"""
from __future__ import annotations

import inspect
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.enums import EmailEventType, EmailStatus
from app.core.seed import seed_demo
from app.integrations.gmail.sender import MockGmailSender
from app.models.emailing import Email, EmailEvent, Proposal, SuppressionEntry
from app.models.lead import Lead
from app.services.emailing.proposal_service import ProposalService
from app.services.emailing.queue import EmailQueueService
from app.utils.text import utcnow


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
    monkeypatch.setattr(EmailQueueService, "_within_allowed_window", lambda self, when: True)
    yield


def _sent_email(db_session, workspace, monkeypatch) -> tuple[Email, list[dict]]:
    lead = Lead(
        workspace_id=workspace.id, place_id="mockplace:f10-1",
        business_name="Negocio Visibilidad", email="lead-f10@example.com",
        email_confidence="HIGH", reviews_count=50, rating=4.2,
    )
    db_session.add(lead)
    db_session.commit()
    service = ProposalService(db_session)
    proposal = service.generate(workspace.id, lead.id)
    service.approve(proposal, user_id=1)
    db_session.commit()
    queue = EmailQueueService(db_session)
    email = queue.queue_for_lead(workspace.id, lead.id, proposal.id, scheduled_at=utcnow())
    sends: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.gmail.sender.MockGmailSender.send",
        lambda self, **kwargs: sends.append(kwargs) or {"id": "mock-x"},
    )
    queue.send_due(workspace.id, now=utcnow() + timedelta(seconds=30))
    db_session.refresh(email)
    return email, sends


# ---------------------------------------------------------------- BUG-08 ----
def test_mock_fallback_is_explicit_in_events(db_session, workspace, monkeypatch):
    """Un SENT simulado dice "simulado" en el evento — jamás se disfraza de
    envío real (la regla cero-engaños también aplica al propio sistema)."""
    email, sends = _sent_email(db_session, workspace, monkeypatch)
    assert email.status == EmailStatus.SENT.value and sends, "el mock debió 'enviar'"
    events = db_session.execute(
        select(EmailEvent).where(EmailEvent.email_id == email.id)
    ).scalars().all()
    sent_events = [e for e in events if e.event_type == EmailEventType.SENT.value]
    assert len(sent_events) == 1
    assert sent_events[0].detail and "simulado" in sent_events[0].detail
    assert "mock" in sent_events[0].detail


def test_real_sender_event_has_no_mock_note(db_session, workspace, monkeypatch):
    """El camino REAL (con token) no lleva la nota de simulación."""
    email, _ = _sent_email(db_session, workspace, monkeypatch)
    # parcheamos _do_send como si hubiera token: via_mock=False
    monkeypatch.setattr(
        EmailQueueService, "_do_send",
        lambda self, account, eml: ("gmail-real-id", False),
    )
    email.status = EmailStatus.QUEUED.value
    db_session.commit()
    EmailQueueService(db_session).send_due(workspace.id, now=utcnow() + timedelta(minutes=2))
    db_session.refresh(email)
    sent_events = [
        e for e in db_session.execute(
            select(EmailEvent).where(
                EmailEvent.email_id == email.id,
                EmailEvent.event_type == EmailEventType.SENT.value,
            )
        ).scalars().all()
    ]
    assert any(e.detail is None for e in sent_events)


# ------------------------------------------------------------- visibilidad --
def test_email_detail_exposes_attempts_and_timeline(db_session, workspace, monkeypatch):
    """F9→F10: el detalle del correo cuenta su propia historia."""
    from starlette.testclient import TestClient

    from app.core.security import create_access_token
    from app.main import create_app

    email, _ = _sent_email(db_session, workspace, monkeypatch)
    assert email.attempts == 1

    from app.models.user import User as UserModel

    demo_user = db_session.scalar(select(UserModel).where(UserModel.email == "test@avascho.com"))
    assert demo_user is not None, "seed_demo debe crear el usuario test"
    client = TestClient(create_app())
    token = create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)
    resp = client.get(f"/api/emails/{email.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["attempts"] == 1
    assert data["message_id"].startswith("mock-")
    assert len(data["events"]) >= 1
    types = [e["event_type"] for e in data["events"]]
    assert "SENT" in types
    # cronológico: occurred_at no decrece
    stamps = [e["occurred_at"] for e in data["events"]]
    assert stamps == sorted(stamps)

    # 404 limpio para ids ajenos/inexistentes (bug dormido pre-F10: el handler
    # usaba `status` sin importarlo → 500 en vez de 404)
    resp404 = client.get("/api/emails/999999", headers={"Authorization": f"Bearer {token}"})
    assert resp404.status_code == 404


# ---------------------------------------------------------------- BUG-07 ----
def test_robots_txt_decision_is_async_runs_in_thread():
    """BUG-07: `_allowed` vuelve a ser coroutine y la lectura de robots (red
    síncrona) vive en `_load_robots` para irse a un thread (asyncio.to_thread).
    Regression-guard estructural: evita volver a bloquear el event loop."""
    from app.integrations.crawler.crawler import HttpFetcher

    assert inspect.iscoroutinefunction(HttpFetcher._allowed), \
        "_allowed debe seguir async (se la espera con await desde fetch)"
    assert not inspect.iscoroutinefunction(HttpFetcher._load_robots), \
        "_load_robots es la parte síncrona — va a thread, no al loop"
    # la red síncrona vive SOLO en _load_robots (va a un thread vía to_thread);
    # el método async solo la referencia como callable
    allowed_src = inspect.getsource(HttpFetcher._allowed)
    loader_src = inspect.getsource(HttpFetcher._load_robots)
    assert "to_thread" in allowed_src and "_load_robots" in allowed_src
    assert "robots.read()" in loader_src


def test_robots_loader_degrades_open_on_error(monkeypatch):
    """Si robots.txt no se puede leer, se permite el fetch (documentado) y el
    parser queda usable — nunca se cae (offline: se fuerza el fallo de red)."""
    from urllib.robotparser import RobotFileParser

    from app.integrations.crawler.crawler import HttpFetcher

    monkeypatch.setattr(
        RobotFileParser, "read",
        lambda self: (_ for _ in ()).throw(OSError("offline sandbox — no network")),
    )
    parser = HttpFetcher._load_robots("cualquier-host.test")
    assert parser.can_fetch("*", "https://cualquier-host.test/cualquier/path")
