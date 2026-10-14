"""Search HTTP endpoints: preview plan, persistence, cancel, SSE auth (Fase 2)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from app.core.seed import seed_demo
from app.core.security import create_access_token
from app.main import create_app
from app.models.search import Search
from app.models.user import User


@pytest.fixture()
def client(db_session, demo_user) -> TestClient:
    app = create_app()
    return TestClient(app)


@pytest.fixture()
def token(demo_user) -> str:
    return create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)


@pytest.fixture()
def auth(token) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


GEO_SMALL = {
    "rect": {"sw": [-34.93, -56.19], "ne": [-34.90, -56.15]},
}

# Whole continent — way beyond the cell cap
GEO_GIANT = {
    "rect": {"sw": [-56.0, -70.0], "ne": [-20.0, -40.0]},
}


def test_preview_text_mode_cost_estimate(client: TestClient):
    res = client.post("/api/searches/preview", json={"category": "Dentistas", "location": "Montevideo"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["mode"] == "text"
    assert 1 <= data["estimated_api_calls"] <= 3
    assert data["estimated_cost_usd"] > 0
    assert data["grid_cells"] == 0


def test_preview_warns_about_60_result_cap(client: TestClient):
    res = client.post(
        "/api/searches/preview",
        json={"category": "Dentistas", "location": "Montevideo", "max_results": 200},
    )
    assert res.status_code == 200
    data = res.json()
    assert any("60" in w for w in data["warnings"])


def test_preview_grid_mode_cells_and_cost(client: TestClient):
    res = client.post(
        "/api/searches/preview",
        json={"category": "Dentistas", "location": "Montevideo", "geo": GEO_SMALL},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["mode"] == "grid"
    assert data["grid_cells"] >= 1
    assert data["estimated_api_calls"] == data["grid_cells"]
    assert data["estimated_cost_usd"] > 0
    assert data["estimated_cost_max_usd"] >= data["estimated_cost_usd"]


def test_preview_giant_area_warns_and_create_rejects(client: TestClient, auth):
    res = client.post(
        "/api/searches/preview",
        json={"category": "Dentistas", "geo": GEO_GIANT},
    )
    assert res.status_code == 200
    assert res.json()["warnings"]

    res = client.post(
        "/api/searches",
        json={"category": "Dentistas", "geo": GEO_GIANT},
        headers=auth,
    )
    assert res.status_code == 422, res.text


def test_create_persists_plan_estimate(client: TestClient, auth, db_session):
    res = client.post(
        "/api/searches",
        json={
            "category": "Clínicas",
            "location": "Montevideo",
            "geo": GEO_SMALL,
            "budget_cap_usd": 1.5,
        },
        headers=auth,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["mode"] == "grid"
    assert data["geo_json"]["type"] == "rect"
    assert data["budget_cap_usd"] == 1.5
    assert data["estimated_api_calls"] >= 1
    assert data["estimated_cost_usd"] > 0

    search = db_session.scalar(select(Search).where(Search.id == data["id"]))
    assert search.mode == "grid"
    assert search.geo_json == {"type": "rect", "sw": [-34.93, -56.19], "ne": [-34.90, -56.15]}


def test_geo_validation_exactly_one_shape(client: TestClient):
    res = client.post(
        "/api/searches/preview",
        json={"category": "X", "geo": {"rect": GEO_SMALL["rect"], "circle": {"center": [0, 0], "radius_km": 1}}},
    )
    assert res.status_code == 422


def test_pending_search_cancel(client: TestClient, auth, db_session):
    res = client.post("/api/searches", json={"category": "Clínicas", "location": "Montevideo"}, headers=auth)
    search_id = res.json()["id"]
    res = client.post(f"/api/searches/{search_id}/cancel", headers=auth)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED"
    # already terminal: conflict
    res = client.post(f"/api/searches/{search_id}/cancel", headers=auth)
    assert res.status_code == 409


def test_sse_requires_auth(client: TestClient, db_session, demo_user):
    search = Search(
        workspace_id=demo_user.workspace_id, query="X, MVD", category="X",
        location="Montevideo", status="COMPLETED",
    )
    db_session.add(search)
    db_session.commit()
    db_session.refresh(search)

    # no auth at all
    res = client.get(f"/api/searches/{search.id}/events")
    assert res.status_code == 401
    # bad token
    res = client.get(f"/api/searches/{search.id}/events?token=nope")
    assert res.status_code == 401


def test_sse_streams_snapshot_and_done(client: TestClient, db_session, demo_user, token):
    search = Search(
        workspace_id=demo_user.workspace_id, query="X, MVD", category="X",
        location="Montevideo", status="COMPLETED", results_total=3,
    )
    db_session.add(search)
    db_session.commit()
    db_session.refresh(search)

    with client.stream("GET", f"/api/searches/{search.id}/events?token={token}") as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        body = res.read().decode()

    assert "event: snapshot" in body
    assert "event: done" in body
    snapshot_line = next(
        line[6:] for line in body.splitlines() if line.startswith("data: {")
    )
    payload = json.loads(snapshot_line)
    assert payload["search"]["id"] == search.id
    assert payload["search"]["status"] == "COMPLETED"
    assert payload["search"]["results_total"] == 3


def test_sse_rejects_foreign_workspace(client: TestClient, db_session, demo_user, token):
    # another workspace's search must 404 for our user
    from app.models.user import Workspace

    other = Workspace(name="Otro Workspace")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    search = Search(
        workspace_id=other.id, query="Q", category="Q", status="COMPLETED",
    )
    db_session.add(search)
    db_session.commit()
    db_session.refresh(search)
    res = client.get(f"/api/searches/{search.id}/events?token={token}")
    assert res.status_code == 404
