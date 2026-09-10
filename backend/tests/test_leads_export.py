"""Tests for the lead filters, the CSV export and the Google Sheets export.

Covers:
- `GET /api/leads` with the exact query params the frontend sends (FIX 4)
- `GET /api/leads/export` honouring those filters, not just `selection` (FIX 6)
- `POST /api/leads/export-to-sheets` + `GoogleSheetsExportService` (FIX 7)
"""
from __future__ import annotations

import csv
import io
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.core.seed import seed_demo
from app.models.emailing import Email, EmailAccount, EmailEvent, Proposal, SuppressionEntry
from app.models.jobs import Job
from app.models.lead import Lead
from app.models.search import Search, SearchLead, SearchPreset
from app.models.website import WebsiteAudit, WebsitePage
from app.services.google_sheets_service import (
    SHEET_COLUMNS,
    GoogleSheetsError,
    GoogleSheetsExportService,
    GoogleSheetsNotConfiguredError,
    SheetsAppendResult,
    build_generic_tab_name,
    INVALID_SHEET_NAME_CHARS,
    build_search_tab_name,
    sanitize_sheet_name,
    unique_sheet_name,
)
from app.utils.text import utcnow

TABLES = (
    EmailEvent, Email, EmailAccount, Proposal, SuppressionEntry,
    WebsitePage, WebsiteAudit, Job, SearchLead, Lead, Search, SearchPreset,
)

SECRET_JSON = '{"type":"service_account","private_key":"SUPER-SECRET-KEY"}'


def wipe_domain(db_session) -> None:
    for model in TABLES:
        db_session.execute(model.__table__.delete())
    db_session.commit()


def _make_lead(db, workspace, search, **overrides) -> Lead:
    name = overrides.get("business_name", "Negocio")
    params = dict(
        workspace_id=workspace.id,
        place_id=f"place-{name}",
        business_name=name,
        category="Clínica estética",
        address="Av. Siempre Viva 123",
        city="Montevideo",
        country="Uruguay",
        latitude=-34.9,
        longitude=-56.1,
        phone="+598 2 000 000",
        website="https://example.com",
        email="hola@example.com",
        email_confidence="HIGH",
        google_maps_url="https://maps.google.com/?cid=1",
        rating=4.6,
        reviews_count=120,
        business_status="OPERATIONAL",
        lead_score=85,
        opportunity_score=70,
        website_score=6.5,
        lead_temperature="HOT",
        status="NEW",
    )
    params.update(overrides)
    lead = Lead(**params)
    db.add(lead)
    db.flush()
    db.add(SearchLead(search_id=search.id, lead_id=lead.id, matched=True, created_at=utcnow()))
    db.commit()
    return lead


@pytest.fixture()
def api(db_session, demo_user):
    """TestClient + leads fixture set + auth headers for the demo user."""
    wipe_domain(db_session)
    seed_demo(db_session)
    search = Search(
        workspace_id=demo_user.workspace_id,
        query="Clínicas estéticas, Montevideo",
        location="Montevideo, Uruguay",
        category="Clínicas estéticas",
        max_results=50,
    )
    db_session.add(search)
    db_session.commit()

    hot_with_email = _make_lead(
        db_session, demo_user, search, business_name="Clínica Aurora",
        place_id="p-aurora", lead_temperature="HOT", email="aurora@example.com",
        website="https://aurora.example.com", lead_score=92, status="NEW",
    )
    warm_with_email = _make_lead(
        db_session, demo_user, search, business_name="Estudio Bruma",
        place_id="p-bruma", lead_temperature="WARM", email="bruma@example.com",
        email_confidence="MEDIUM", website=None, lead_score=74, status="CONTACTED",
    )
    warm_high_confidence = _make_lead(
        db_session, demo_user, search, business_name="Spa Duna",
        place_id="p-duna", lead_temperature="WARM", email="duna@example.com",
        email_confidence="HIGH", website="https://duna.example.com", lead_score=80,
        status="CONTACTED",
    )
    cold_no_email = _make_lead(
        db_session, demo_user, search, business_name="Spa Ceniza",
        place_id="p-ceniza", lead_temperature="COLD", email=None, website=None,
        lead_score=41, status="NEW",
    )

    from app.main import create_app

    token = create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)
    client = TestClient(create_app())
    return SimpleNamespace(
        client=client,
        headers={"Authorization": f"Bearer {token}"},
        search=search,
        leads={
            "hot": hot_with_email,
            "warm": warm_with_email,
            "warm_high": warm_high_confidence,
            "cold": cold_no_email,
        },
    )


# ------------------------------------------------------- GET /api/leads ----
def test_list_leads_applies_ui_filters(api):
    """The exact query params the leads page sends must filter the results."""
    r = api.client.get("/api/leads", params={"temperature": "HOT", "has_email": "true"},
                       headers=api.headers)
    assert r.status_code == 200, r.text
    names = {item["business_name"] for item in r.json()["items"]}
    assert names == {"Clínica Aurora"}

    r = api.client.get(
        "/api/leads",
        params={"has_website": "false", "min_lead_score": "40", "status": "NEW"},
        headers=api.headers,
    )
    assert r.status_code == 200, r.text
    assert {i["business_name"] for i in r.json()["items"]} == {"Spa Ceniza"}

    r = api.client.get("/api/leads", params={"q": "bruma", "search_id": api.search.id},
                       headers=api.headers)
    assert r.status_code == 200, r.text
    assert {i["business_name"] for i in r.json()["items"]} == {"Estudio Bruma"}


# ------------------------------------------------------ GET /leads/export --
def _csv_rows(response: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response)))


def test_export_requires_bearer_token(api):
    r = api.client.get("/api/leads/export")
    assert r.status_code == 401
    assert r.json()["detail"] == "Missing bearer token"


def test_export_csv_respects_filters(api):
    r = api.client.get(
        "/api/leads/export",
        params={"fmt": "csv", "temperature": "HOT", "has_email": "true"},
        headers=api.headers,
    )
    assert r.status_code == 200, r.text
    assert "avascho_leads.csv" in r.headers["content-disposition"]
    rows = _csv_rows(r.text)
    assert [row["business_name"] for row in rows] == ["Clínica Aurora"]

    # has_website=false + min_lead_score + status narrow it the same way as GET /leads
    r = api.client.get(
        "/api/leads/export",
        params={"fmt": "csv", "has_website": "false", "min_lead_score": 40, "status": "NEW"},
        headers=api.headers,
    )
    assert [row["business_name"] for row in _csv_rows(r.text)] == ["Spa Ceniza"]

    # search_id + q
    r = api.client.get(
        "/api/leads/export",
        params={"fmt": "csv", "search_id": api.search.id, "q": "ceniza"},
        headers=api.headers,
    )
    assert [row["business_name"] for row in _csv_rows(r.text)] == ["Spa Ceniza"]

    # no filters at all → every qualified lead, not just the first page
    r = api.client.get("/api/leads/export", params={"fmt": "csv"}, headers=api.headers)
    assert {row["business_name"] for row in _csv_rows(r.text)} == {
        "Clínica Aurora", "Estudio Bruma", "Spa Ceniza", "Spa Duna",
    }


def test_export_selection_presets_still_work(api):
    r = api.client.get("/api/leads/export", params={"fmt": "csv", "selection": "HOT"},
                       headers=api.headers)
    assert [row["business_name"] for row in _csv_rows(r.text)] == ["Clínica Aurora"]

    r = api.client.get("/api/leads/export", params={"fmt": "csv", "selection": "WARM"},
                       headers=api.headers)
    assert [row["business_name"] for row in _csv_rows(r.text)] == ["Spa Duna", "Estudio Bruma"]

    # READY_TO_CONTACT = HOT/WARM **and** HIGH email confidence, by lead_score desc
    r = api.client.get(
        "/api/leads/export", params={"fmt": "csv", "selection": "READY_TO_CONTACT"},
        headers=api.headers,
    )
    assert [row["business_name"] for row in _csv_rows(r.text)] == [
        "Clínica Aurora", "Spa Duna",
    ]

    r = api.client.get(
        "/api/leads/export",
        params={"fmt": "csv", "selection": "selected", "ids": str(api.leads["warm"].id)},
        headers=api.headers,
    )
    assert [row["business_name"] for row in _csv_rows(r.text)] == ["Estudio Bruma"]


def test_export_json_format_still_works(api):
    r = api.client.get(
        "/api/leads/export", params={"fmt": "json", "temperature": "WARM"},
        headers=api.headers,
    )
    assert r.status_code == 200, r.text
    assert [row["business_name"] for row in r.json()] == ["Spa Duna", "Estudio Bruma"]


# ------------------------------------------- POST /leads/export-to-sheets --
def test_export_to_sheets_disabled(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", False)
    r = api.client.post("/api/leads/export-to-sheets", json={"selection": "all"},
                        headers=api.headers)
    assert r.status_code == 400
    assert "no está habilitada" in r.json()["detail"]


def test_export_to_sheets_requires_spreadsheet(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "")
    r = api.client.post("/api/leads/export-to-sheets", json={}, headers=api.headers)
    assert r.status_code == 400
    assert "GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID" in r.json()["detail"]


def test_export_to_sheets_writes_filtered_rows(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "SHEET-ID-123")
    monkeypatch.setattr(settings, "google_sheets_default_sheet_name", "Leads")

    calls: list[tuple] = []

    class FakeService:
        def append_leads_to_new_tab(self, spreadsheet_id, base_name, leads):
            calls.append((spreadsheet_id, base_name, list(leads)))
            return SheetsAppendResult(
                rows_written=len(list(leads)), sheet_name=f"{base_name} (2)", sheet_gid=101
            )

    monkeypatch.setattr("app.api.routes_leads.GoogleSheetsExportService", FakeService)

    r = api.client.post(
        "/api/leads/export-to-sheets",
        json={"selection": "all", "temperature": "HOT", "has_email": True,
              "search_id": api.search.id, "min_lead_score": 90},
        headers=api.headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows_written"] == 1
    # la pestaña se nombra con la query de la búsqueda + su fecha
    assert re.match(
        rf"^{re.escape(api.search.query)} - \d{{2}}-\d{{2}}-\d{{4}}$", calls[0][1]
    ), calls[0][1]
    assert body["sheet_name"] == f"{calls[0][1]} (2)"
    # el link lleva al gid de la pestaña creada
    assert body["spreadsheet_url"] == (
        "https://docs.google.com/spreadsheets/d/SHEET-ID-123/edit#gid=101"
    )
    assert calls[0][0] == "SHEET-ID-123"
    assert [lead.business_name for lead in calls[0][2]] == ["Clínica Aurora"]


def test_export_to_sheets_without_search_uses_generic_tab(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "SHEET-ID-123")
    monkeypatch.setattr(settings, "google_sheets_default_sheet_name", "Leads")

    calls: list[str] = []

    class FakeService:
        def append_leads_to_new_tab(self, spreadsheet_id, base_name, leads):
            calls.append(base_name)
            return SheetsAppendResult(len(list(leads)), base_name, 7)

    monkeypatch.setattr("app.api.routes_leads.GoogleSheetsExportService", FakeService)

    r = api.client.post("/api/leads/export-to-sheets", json={}, headers=api.headers)
    assert r.status_code == 200, r.text
    assert re.match(r"^Leads \d{2}-\d{2}-\d{4} \d{2}\.\d{2}$", calls[0]), calls[0]
    assert r.json()["sheet_name"] == calls[0]


def test_export_to_sheets_honours_explicit_sheet_name(api, monkeypatch):
    """Un sheet_name explícito sigue anexando a esa pestaña (compat)."""
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "SHEET-ID-123")

    calls: list[tuple] = []

    class FakeService:
        def append_leads(self, spreadsheet_id, sheet_name, leads):
            calls.append((spreadsheet_id, sheet_name))
            return len(list(leads))

        def append_leads_to_new_tab(self, *a, **kw):  # pragma: no cover
            raise AssertionError("no debería crear una pestaña nueva")

    monkeypatch.setattr("app.api.routes_leads.GoogleSheetsExportService", FakeService)

    r = api.client.post(
        "/api/leads/export-to-sheets", json={"sheet_name": "Prospectos 2026"},
        headers=api.headers,
    )
    assert r.status_code == 200, r.text
    assert calls == [("SHEET-ID-123", "Prospectos 2026")]
    assert r.json()["sheet_name"] == "Prospectos 2026"
    assert r.json()["spreadsheet_url"].endswith("/edit")  # sin gid


def test_export_to_sheets_unknown_search_is_400(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "SHEET-ID-123")

    r = api.client.post(
        "/api/leads/export-to-sheets", json={"search_id": 99999}, headers=api.headers
    )
    assert r.status_code == 400
    assert "no existe" in r.json()["detail"]


def test_export_to_sheets_upstream_error_is_502(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "SHEET-ID-123")
    monkeypatch.setattr(settings, "google_sheets_service_account_json", SECRET_JSON)

    class BrokenService:
        def append_leads(self, spreadsheet_id, sheet_name, leads):
            raise GoogleSheetsError("Google rechazó el acceso a la spreadsheet (403).")

        def append_leads_to_new_tab(self, spreadsheet_id, base_name, leads):
            raise GoogleSheetsError("Google rechazó el acceso a la spreadsheet (403).")

    monkeypatch.setattr("app.api.routes_leads.GoogleSheetsExportService", BrokenService)

    r = api.client.post("/api/leads/export-to-sheets", json={}, headers=api.headers)
    assert r.status_code == 502
    assert "403" in r.json()["detail"]
    # the service-account key never leaks into a response
    assert "SUPER-SECRET-KEY" not in r.text
    assert SECRET_JSON not in r.text


def test_export_to_sheets_unconfigured_key_is_400(api, monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_enabled", True)
    monkeypatch.setattr(settings, "google_sheets_default_spreadsheet_id", "SHEET-ID-123")
    monkeypatch.setattr(settings, "google_sheets_service_account_json", "")

    r = api.client.post("/api/leads/export-to-sheets", json={}, headers=api.headers)
    assert r.status_code == 400
    assert "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON" in r.json()["detail"]


# ----------------------------------------------- GoogleSheetsExportService --
class FakeValues:
    def __init__(self, existing: list[list[str]], sink: dict) -> None:
        self.existing = existing
        self.sink = sink

    def get(self, spreadsheetId, range):  # noqa: N803 - mirrors the client API
        outer = self

        class _Req:
            def execute(self_inner):
                if not outer.existing:
                    return {"range": range, "majorDimension": "ROWS"}
                return {"range": range, "values": outer.existing}

        return _Req()

    def append(self, spreadsheetId, range, valueInputOption, insertDataOption, body):  # noqa: N803
        outer = self

        class _Req:
            def execute(self_inner):
                outer.sink["append"] = {
                    "spreadsheetId": spreadsheetId,
                    "range": range,
                    "valueInputOption": valueInputOption,
                    "insertDataOption": insertDataOption,
                    "values": body["values"],
                }
                return {"updates": {"updatedRows": len(body["values"])}}

        return _Req()


class FakeSheets:
    def __init__(
        self,
        existing: list[list[str]] | None = None,
        tabs: list[str] | None = None,
    ) -> None:
        self.sink: dict = {}
        self._values = FakeValues(existing or [], self.sink)
        self.tabs: list[str] = list(tabs or [])  # pestañas ya existentes
        self.created: list[str] = []  # pestañas creadas en este test

    def spreadsheets(self):
        return self

    def values(self):
        return self._values

    def get(self, spreadsheetId, fields=None):  # noqa: N803
        outer = self

        class _Req:
            def execute(self_inner):
                return {"sheets": [{"properties": {"title": t}} for t in outer.tabs]}

        return _Req()

    def batchUpdate(self, spreadsheetId, body):  # noqa: N803
        outer = self

        class _Req:
            def execute(self_inner):
                title = body["requests"][0]["addSheet"]["properties"]["title"]
                outer.tabs.append(title)
                outer.created.append(title)
                gid = 100 + len(outer.created)
                return {
                    "replies": [
                        {"addSheet": {"properties": {"sheetId": gid, "title": title}}}
                    ]
                }

        return _Req()


def _service_with(fake: FakeSheets) -> GoogleSheetsExportService:
    service = GoogleSheetsExportService()
    service._configured = True
    service._client = lambda: fake  # type: ignore[method-assign]
    return service


def _lead_stub(**overrides) -> Lead:
    params = dict(
        business_name="Clínica Aurora", category="Clínica estética",
        address="Av. 1", city="Montevideo", country="Uruguay", phone="+598 2 000",
        website="https://aurora.example.com", email="aurora@example.com",
        google_maps_url="https://maps.google.com/?cid=1", place_id="p-aurora",
        rating=4.6, reviews_count=120, latitude=-34.9, longitude=-56.1,
        business_status="OPERATIONAL",
    )
    params.update(overrides)
    return Lead(**params)


def test_service_is_not_configured_without_key(monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_service_account_json", "")
    assert GoogleSheetsExportService().is_configured is False
    with pytest.raises(GoogleSheetsNotConfiguredError):
        GoogleSheetsExportService().append_leads("id", "Leads", [_lead_stub()])


def test_service_rejects_malformed_json(monkeypatch):
    monkeypatch.setattr(settings, "google_sheets_service_account_json", "not-json")
    service = GoogleSheetsExportService()
    assert service.is_configured is True
    with pytest.raises(GoogleSheetsNotConfiguredError) as excinfo:
        service._get_credentials()
    assert "JSON válido" in str(excinfo.value)
    assert "not-json" not in str(excinfo.value)


def test_service_rejects_unusable_private_key(monkeypatch):
    """Valid JSON, but not a usable key → clear 400-style error, never a 500."""
    monkeypatch.setattr(
        settings,
        "google_sheets_service_account_json",
        '{"type":"service_account","client_email":"x@y.iam.gserviceaccount.com",'
        '"private_key":"-----BEGIN PRIVATE KEY-----\\nBROKEN\\n-----END PRIVATE KEY-----\\n",'
        '"token_uri":"https://oauth2.googleapis.com/token"}',
    )
    service = GoogleSheetsExportService()
    with pytest.raises(GoogleSheetsNotConfiguredError) as excinfo:
        service.append_leads("SHEET-ID", "Leads", [_lead_stub()])
    assert "BROKEN" not in str(excinfo.value)


def test_service_writes_headers_then_rows_on_empty_sheet():
    fake = FakeSheets()
    service = _service_with(fake)
    leads = [_lead_stub(), _lead_stub(place_id="p-2", business_name="Estudio Bruma",
                                      website=None, email=None)]

    written = service.append_leads("SHEET-ID", "Leads", leads)

    assert written == 2
    payload = fake.sink["append"]
    assert payload["spreadsheetId"] == "SHEET-ID"
    assert payload["range"] == "Leads!A1"
    assert payload["valueInputOption"] == "RAW"
    assert payload["insertDataOption"] == "INSERT_ROWS"
    values = payload["values"]
    assert values[0] == list(SHEET_COLUMNS)
    assert values[1] == [
        "Clínica Aurora", "Clínica estética", "Av. 1", "Montevideo", "Uruguay",
        "+598 2 000", "https://aurora.example.com", "aurora@example.com",
        "https://maps.google.com/?cid=1", "p-aurora", 4.6, 120, -34.9, -56.1,
        "OPERATIONAL", "AvaScho",
    ]
    # empty fields become empty cells, not None
    assert values[2][SHEET_COLUMNS.index("website")] == ""
    assert values[2][SHEET_COLUMNS.index("email")] == ""


def test_service_skips_headers_when_sheet_has_data():
    fake = FakeSheets(existing=[["business_name"]])
    service = _service_with(fake)

    assert service.append_leads("SHEET-ID", "Leads", [_lead_stub()]) == 1
    values = fake.sink["append"]["values"]
    assert len(values) == 1
    assert values[0][0] == "Clínica Aurora"


def test_service_returns_zero_without_calling_the_api():
    fake = FakeSheets()
    assert _service_with(fake).append_leads("SHEET-ID", "Leads", []) == 0
    assert fake.sink == {}


@pytest.mark.parametrize(
    "status_code,expected",
    [
        (403, "Editor"),
        (404, "SPREADSHEET"),
        (500, "status 500"),
    ],
)
def test_service_maps_http_errors(status_code, expected):
    from googleapiclient.errors import HttpError

    class Boom(FakeSheets):
        def spreadsheets(self):
            raise HttpError(Mock(status=status_code), b'{"error":{}}')

    service = _service_with(Boom())
    with pytest.raises(GoogleSheetsError) as excinfo:
        service.append_leads("SHEET-ID", "Leads", [_lead_stub()])
    assert expected in str(excinfo.value).upper() or expected in str(excinfo.value)


# ---------------------------------------------------------- tab naming ------
def test_sanitize_sheet_name_replaces_invalid_chars():
    assert sanitize_sheet_name('Spa: [test]/a\\b?c*d') == "Spa test a b c d"
    # comillas simples al borde y espacios de más
    assert sanitize_sheet_name("  ''Clínica   Aurora''  ") == "Clínica Aurora"
    assert sanitize_sheet_name("") == ""
    assert sanitize_sheet_name(None) == ""
    assert sanitize_sheet_name("::::") == ""


def test_sanitize_sheet_name_caps_at_100_chars():
    name = sanitize_sheet_name("Restaurante " * 30)
    assert len(name) <= 100
    assert name.startswith("Restaurante")


def test_unique_sheet_name_adds_incremental_suffix():
    base = "Restaurante, Montevideo, Uruguay - 09-09-2026"
    assert unique_sheet_name(base, []) == base
    assert unique_sheet_name(base, [base]) == f"{base} (2)"
    assert unique_sheet_name(base, [base, f"{base} (2)"]) == f"{base} (3)"
    # el sufijo entra dentro del límite de 100 caracteres
    long_base = "X" * 100
    candidate = unique_sheet_name(long_base, [long_base])
    assert candidate.endswith("(2)")
    assert len(candidate) <= 100


def test_build_search_tab_name_format():
    from datetime import datetime, timezone

    when = datetime(2026, 9, 9, 18, 30, tzinfo=timezone.utc)
    name = build_search_tab_name("Restaurante, Montevideo, Uruguay", when)
    assert re.match(r"^Restaurante, Montevideo, Uruguay - \d{2}-\d{2}-\d{4}$", name), name
    # sin query utilizable cae al nombre genérico con fecha
    assert re.match(r"^Leads \d{2}-\d{2}-\d{4}$", build_search_tab_name("::", when))
    assert re.match(r"^Leads \d{2}-\d{2}-\d{4}$", build_search_tab_name(None, when))


def test_build_generic_tab_name_uses_configured_base():
    assert re.match(r"^Prospectos \d{2}-\d{2}-\d{4} \d{2}\.\d{2}$", build_generic_tab_name("Prospectos"))
    assert re.match(r"^Leads \d{2}-\d{2}-\d{4} \d{2}\.\d{2}$", build_generic_tab_name(""))
    # ningún carácter inválido para una pestaña de Sheets puede sobrevivir
    for invalid in INVALID_SHEET_NAME_CHARS:
        assert invalid not in build_generic_tab_name("Prospectos")


# ------------------------------------- GoogleSheetsExportService: new tab ---
def test_append_leads_to_new_tab_creates_tab_with_headers_and_gid():
    fake = FakeSheets(tabs=["Leads"])
    service = _service_with(fake)

    result = service.append_leads_to_new_tab(
        "SHEET-ID", "Restaurante, Montevideo, Uruguay - 09-09-2026", [_lead_stub()]
    )

    assert result.rows_written == 1
    assert result.sheet_name == "Restaurante, Montevideo, Uruguay - 09-09-2026"
    assert result.sheet_gid == 101
    assert fake.created == ["Restaurante, Montevideo, Uruguay - 09-09-2026"]
    values = fake.sink["append"]["values"]
    assert values[0] == list(SHEET_COLUMNS)  # pestaña nueva → headers
    assert fake.sink["append"]["range"] == "Restaurante, Montevideo, Uruguay - 09-09-2026!A1"


def test_append_leads_to_new_tab_avoids_name_collision():
    base = "Clínicas estéticas, Montevideo - 09-09-2026"
    fake = FakeSheets(tabs=[base])
    service = _service_with(fake)

    result = service.append_leads_to_new_tab("SHEET-ID", base, [_lead_stub()])

    assert result.sheet_name == f"{base} (2)"
    assert fake.created == [f"{base} (2)"]


def test_append_leads_to_new_tab_sanitizes_the_requested_name():
    fake = FakeSheets()
    service = _service_with(fake)

    result = service.append_leads_to_new_tab("SHEET-ID", "Spa: [Ceniza]/Montevideo", [_lead_stub()])

    assert result.sheet_name == "Spa Ceniza Montevideo"


def test_append_leads_to_new_tab_without_leads_creates_nothing():
    fake = FakeSheets()
    result = _service_with(fake).append_leads_to_new_tab("SHEET-ID", "base", [])

    assert result.rows_written == 0
    assert result.sheet_name is None
    assert fake.created == []
    assert fake.sink == {}


def test_append_leads_to_new_tab_maps_http_errors():
    from googleapiclient.errors import HttpError

    class Boom(FakeSheets):
        def get(self, spreadsheetId, fields=None):  # noqa: N803
            raise HttpError(Mock(status=404), b'{"error":{}}')

    with pytest.raises(GoogleSheetsError) as excinfo:
        _service_with(Boom()).append_leads_to_new_tab("SHEET-ID", "base", [_lead_stub()])
    assert "404" in str(excinfo.value)
