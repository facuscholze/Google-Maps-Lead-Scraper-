"""Fase 4 (Leads Pro): bulk actions, tags/owner filters, sort, views, activity."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.core.seed import seed_demo
from app.main import create_app
from app.models.lead import Lead
from app.models.user import User


@pytest.fixture()
def client(demo_user) -> TestClient:
    return TestClient(create_app())


@pytest.fixture()
def auth(demo_user) -> dict[str, str]:
    token = create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)
    return {"Authorization": f"Bearer {token}"}


def _lead(db_session, workspace_id: int, **kw) -> Lead:
    name = kw.pop("business_name", "Test Co")
    lead = Lead(
        workspace_id=workspace_id,
        business_name=name,
        place_id=kw.pop("place_id", f"p-{name.lower().replace(' ', '-')}-{workspace_id}"),
        **kw,
    )
    db_session.add(lead)
    db_session.commit()
    return lead


def test_bulk_tags_owner_and_archive(db_session, workspace, client, auth):
    a = _lead(db_session, workspace.id, business_name="Panadería Sol", city="Montevideo")
    b = _lead(db_session, workspace.id, business_name="Café Río", city="Punta del Este")
    missing_id = 999999

    r = client.post("/api/leads/bulk", json={"ids": [a.id, b.id, missing_id], "action": "add_tag", "tag": " Frio "}, headers=auth)
    assert r.status_code == 200
    assert r.json()["updated"] == 2
    db_session.refresh(a)
    assert a.tags == ",frio,"  # normalizado lowercase

    r = client.post("/api/leads/bulk", json={"ids": [a.id], "action": "assign_owner", "owner": "Facu"}, headers=auth)
    assert r.status_code == 200
    r = client.post("/api/leads/bulk", json={"ids": [a.id], "action": "archive"}, headers=auth)
    assert r.json()["updated"] == 1
    r = client.post("/api/leads/bulk", json={"ids": [a.id], "action": "unarchive"}, headers=auth)
    db_session.refresh(a)
    assert a.status == "NEW"

    r = client.post("/api/leads/bulk", json={"ids": [a.id], "action": "add_tag"}, headers=auth)
    assert r.status_code == 422  # tag vacío no pasa


def test_list_filters_and_sort(db_session, workspace, client, auth):
    hot = _lead(db_session, workspace.id, business_name="Zeta Resto", city="Montevideo",
                tags=",frio,recontacto,", owner_name="Facu", lead_score=90, lead_temperature="HOT")
    cold = _lead(db_session, workspace.id, business_name="Alfa Gym", city="Maldonado",
                 tags=",vip,", lead_score=20, lead_temperature="COLD", status="NEW")

    r = client.get("/api/leads?tag=frio&include_unlinked=true", headers=auth)
    names = [i["business_name"] for i in r.json()["items"]]
    assert "Zeta Resto" in names and "Alfa Gym" not in names  # vineta padded: no matchea "vip"

    r = client.get("/api/leads?owner=facu&include_unlinked=true", headers=auth)
    owner_names = [i["business_name"] for i in r.json()["items"]]
    assert "Zeta Resto" in owner_names and "Alfa Gym" not in owner_names
    assert all(i["owner_name"] and "facu" in i["owner_name"].lower() for i in r.json()["items"])

    r = client.get("/api/leads?city=maldo&include_unlinked=true", headers=auth)
    city_names = [i["business_name"] for i in r.json()["items"]]
    assert "Alfa Gym" in city_names and "Zeta Resto" not in city_names

    r = client.get("/api/leads?sort=business_name&order=asc&include_unlinked=true", headers=auth)
    names = [i["business_name"] for i in r.json()["items"]]
    assert names == sorted(names, key=str.lower)

    r = client.get("/api/leads?sort=hacker_field", headers=auth)
    assert r.status_code == 422  # whitelist

    r = client.get("/api/leads?page_size=500", headers=auth)
    assert r.status_code == 200  # nuevo cap (D3.5)


def test_lead_views_crud(db_session, workspace, client, auth, demo_user):
    r = client.post("/api/lead-views", json={"name": "HOT Montevideo", "config": {"temperature": "HOT", "city": "Montevideo"}}, headers=auth)
    assert r.status_code == 201
    vid = r.json()["id"]
    # upsert por nombre
    r2 = client.post("/api/lead-views", json={"name": "HOT Montevideo", "config": {"temperature": "HOT"}}, headers=auth)
    assert r2.json()["id"] == vid and r2.json()["config_json"] == {"temperature": "HOT"}

    r = client.get("/api/lead-views", headers=auth)
    assert any(v["name"] == "HOT Montevideo" for v in r.json())

    r = client.delete(f"/api/lead-views/{vid}", headers=auth)
    assert r.status_code == 204
    r = client.delete(f"/api/lead-views/{vid}", headers=auth)
    assert r.status_code == 404


def test_lead_activity_timeline(db_session, workspace, client, auth):
    lead = _lead(db_session, workspace.id, business_name="Negocio A")
    r = client.get(f"/api/leads/{lead.id}/activity", headers=auth)
    items = r.json()["items"]
    assert any(i["kind"] == "created" for i in items)
    r = client.get("/api/leads/999999/activity", headers=auth)
    assert r.status_code == 404
