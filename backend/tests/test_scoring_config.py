"""Fase 6 — scoring configurable: defaults, validación, ponderación, rescore."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.core.enums import LeadTemperature
from app.core.security import create_access_token
from app.main import create_app
from app.models.lead import Lead
from app.services.analysis.scorer import LeadScorer, resolve_weights, temperature_for


@pytest.fixture()
def client(demo_user) -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def auth(demo_user) -> dict[str, str]:
    token = create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)
    return {"Authorization": f"Bearer {token}"}


_counter = 0


def _lead(db_session, workspace, **kw) -> Lead:
    global _counter
    _counter += 1
    lead = Lead(
        workspace_id=workspace.id,
        business_name=kw.pop("business_name", f"Lead F6 {_counter}"),
        place_id=f"p-f6-{_counter}",
        **kw,
    )
    db_session.add(lead)
    db_session.commit()
    return lead


# ----------------------------------------------------------------- unitario --
def test_resolve_weights_defaults_and_clamp():
    w = resolve_weights(None)
    assert all(w[c] == 1.0 for c in ("reputation", "reviews", "email"))
    w = resolve_weights({"reputation": 5.0, "email": -2, "hacker": 9})
    assert w["reputation"] == 3.0 and w["email"] == 0.0 and "hacker" not in w


def test_temperature_custom_thresholds():
    assert temperature_for(85) == LeadTemperature.HOT.value
    assert temperature_for(85, thresholds=(90, 70, 50)) == LeadTemperature.WARM.value
    assert temperature_for(55, thresholds=(90, 70, 50)) == LeadTemperature.COLD.value


def test_weighted_scoring_scales_deltas_and_records_meta():
    scorer = LeadScorer()
    base = scorer.score(rating=4.9, reviews=320, website_score=None, audit=None,
                        has_email=True, email_confidence="HIGH", has_phone=True,
                        has_website=False, business_name="X")
    weighted = scorer.score(rating=4.9, reviews=320, website_score=None, audit=None,
                            has_email=True, email_confidence="HIGH", has_phone=True,
                            has_website=False, business_name="X",
                            weights={"reputation": 1.5, "email": 0.5})
    rep_item = next(i for i in weighted["lead_breakdown"] if i["category"] == "reputation")
    assert rep_item["base_delta"] == 24 and rep_item["delta"] == 36 and rep_item["weight"] == 1.5
    email_item = next(i for i in weighted["lead_breakdown"] if i["category"] == "email")
    assert email_item["base_delta"] == 9 and email_item["delta"] in (4, 5) and email_item["weight"] == 0.5
    assert weighted["lead_score"] != base["lead_score"]
    # determinismo: mismos inputs → mismo resultado
    again = scorer.score(rating=4.9, reviews=320, website_score=None, audit=None,
                         has_email=True, email_confidence="HIGH", has_phone=True,
                         has_website=False, business_name="X",
                         weights={"reputation": 1.5, "email": 0.5})
    assert again["lead_score"] == weighted["lead_score"]


# ------------------------------------------------------------------ API -------
def test_config_roundtrip_defaults_then_update(client, auth):
    r = client.get("/api/scoring-config", headers=auth)
    assert r.status_code == 200 and r.json()["is_default"] is True
    assert r.json()["hot_min"] == 80

    r = client.put("/api/scoring-config", json={
        "weights": {"reputation": 1.5, "email": 0.5},
        "hot_min": 85, "warm_min": 65, "cold_min": 45,
    }, headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["is_default"] is False
    assert data["weights"]["reputation"] == 1.5
    assert data["weights"]["email"] == 0.5
    assert data["weights"]["reviews"] == 1.0  # merge con defaults/vigente
    assert (data["hot_min"], data["warm_min"], data["cold_min"]) == (85, 65, 45)

    r = client.get("/api/scoring-config", headers=auth)
    assert r.json()["weights"]["reputation"] == 1.5


def test_config_validation_errors(client, auth):
    r = client.put("/api/scoring-config", json={"weights": {"reputation": 4.0}}, headers=auth)
    assert r.status_code == 422  # peso fuera de rango
    r = client.put("/api/scoring-config", json={"hot_min": 50, "warm_min": 60, "cold_min": 40}, headers=auth)
    assert r.status_code == 422  # hot > warm > cold exigido


def test_rescore_endpoint_applies_weights(db_session, workspace, client, auth):
    lead = _lead(db_session, workspace, rating=4.9, reviews_count=400, website="https://x.test",
                 email="x@x.test", email_confidence="HIGH")
    from app.services.lead_service import score_lead
    from app.services.scoring_config_service import load_scoring_config

    score_lead(db_session, lead, config=load_scoring_config(db_session, workspace.id))
    db_session.commit()
    before = lead.lead_score

    client.put("/api/scoring-config", json={"weights": {"reputation": 0.0, "email": 0.0}}, headers=auth)
    r = client.post("/api/scoring-config/rescore", json={"ids": [lead.id]}, headers=auth)
    assert r.status_code == 200 and r.json()["rescored"] == 1
    db_session.refresh(lead)
    assert lead.lead_score < before  # sin reputación/email el score baja
    # breakdown con meta de ponderación
    rep = next(b for b in lead.score_breakdown["lead"] if b["category"] == "reputation")
    assert rep["delta"] == 0 and rep["base_delta"] == 24


def test_rescore_skips_unknown_ids_and_archived(db_session, workspace, client, auth):
    lead = _lead(db_session, workspace, status="ARCHIVED")
    r = client.post("/api/scoring-config/rescore", json={"ids": [lead.id, 999999]}, headers=auth)
    assert r.status_code == 200
    assert 999999 in r.json()["skipped"]
    # rescore global ignora archivados
    r = client.post("/api/scoring-config/rescore", json={}, headers=auth)
    assert r.status_code == 200


def test_config_roundtrip_reset(client, auth):
    client.put("/api/scoring-config", json={"hot_min": 90, "warm_min": 70, "cold_min": 50}, headers=auth)
    r = client.delete("/api/scoring-config", headers=auth)
    assert r.status_code == 204
    r = client.get("/api/scoring-config", headers=auth)
    assert r.json()["is_default"] is True and r.json()["hot_min"] == 80


def test_endpoint_rescore_lead_single(db_session, workspace, client, auth, demo_user):
    """POST /leads/{id}/rescore — recálculo explícito per-lead (F6/D6.4)."""
    lead = _lead(db_session, workspace, rating=4.6, reviews_count=120, website="https://y.test")
    from app.services.lead_service import score_lead
    from app.services.scoring_config_service import load_scoring_config

    score_lead(db_session, lead, config=load_scoring_config(db_session, workspace.id))
    db_session.commit()
    before = lead.lead_score

    client.put("/api/scoring-config", json={"weights": {"reputation": 2.0}}, headers=auth)
    r = client.post(f"/api/leads/{lead.id}/rescore", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["lead_score"] != before
    rep = next(b for b in data["score_breakdown"]["lead"] if b["category"] == "reputation")
    assert rep["weight"] == 2.0 and rep["delta"] == rep["base_delta"] * 2

    r = client.post("/api/leads/999999/rescore", headers=auth)
    assert r.status_code == 404
