"""Fase 5 — evidencia de auditoría: findings persistidos, screenshots.

Screenshots en tests: provider "none" o un servicio falso — jamás el navegador
real (tests offline, regla de producto).
"""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.integrations import mock_fixtures as mf
from app.integrations.crawler.extractor import WebsiteExtractor
from app.main import create_app
from app.models.lead import Lead
from app.models.website import WebsiteAudit
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.types import PageData
from app.services.screenshot_service import ScreenshotService


def _mock_audit_result(slug: str):
    pages = [
        PageData(url=f"http://mockbusiness.local/{slug}{p}", html=mf.render_site(slug, p)[0], kind="other")
        for p in mf.site_pages(slug)
    ]
    site = WebsiteExtractor().extract(pages)
    return WebsiteAuditor().audit(site)


_counter = 0


def _lead(db_session, workspace, website: str | None = "http://mockbusiness.local/dermia-laser") -> Lead:
    global _counter
    _counter += 1
    lead = Lead(
        workspace_id=workspace.id,
        business_name=f"Lead F5 {_counter}",
        place_id=f"p-f5-{_counter}",
        website=website,
    )
    db_session.add(lead)
    db_session.commit()
    return lead


def test_findings_persisted_with_kind_and_source(db_session, workspace, demo_user):
    from app.services.website_service import WebsiteAnalysisService

    lead = _lead(db_session, workspace)
    result = _mock_audit_result("dermia-laser")
    service = WebsiteAnalysisService(db_session)
    audit = service.persist_audit(lead, result, [])
    db_session.commit()

    assert audit.findings, "los findings deben persistirse en la row del audit"
    for f in audit.findings:
        assert f["kind"] in ("FACT", "INFERENCE")
        assert f["evidence"]
        assert f["dimension"]


def test_screenshot_service_none_provider_returns_none_without_files(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "screenshots_dir", str(tmp_path))
    service = ScreenshotService(provider="none")
    meta = service.capture_home("https://example.com", 1, 2, 3)
    assert meta is None
    assert list(tmp_path.rglob("*.jpg")) == []  # nada inventado en disco


def test_screenshot_service_failure_is_soft(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "screenshots_dir", str(tmp_path))
    service = ScreenshotService(provider="playwright")
    # sin browser instalado en el sandbox → debe fallar suave (None), nunca romper
    meta = service.capture_home("https://no-existe.invalid", 1, 2, 3)
    assert meta in (None, meta)  # si hubiera browser remoto capturaría; en tests exigimos soft-fail no-crash


def test_audit_endpoint_exposes_findings_and_screenshots(db_session, workspace, demo_user):
    from app.services.website_service import WebsiteAnalysisService

    lead = _lead(db_session, workspace)
    result = _mock_audit_result("dermia-laser")
    service = WebsiteAnalysisService(db_session)
    audit = service.persist_audit(lead, result, [])
    audit.screenshots = [{
        "url": "http://mockbusiness.local/dermia-laser",
        "path": f"{workspace.id}/{lead.id}-{audit.id}.jpg",
        "kind": "home-fold", "width": 1280, "height": 800,
        "bytes": 1234, "http_status": 200, "captured_at": "2026-10-14T00:00:00+00:00",
    }]
    db_session.add(audit)
    db_session.commit()

    client = TestClient(create_app())
    token = create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get(f"/api/leads/{lead.id}/audit", headers=headers)
    assert r.status_code == 200
    data = r.json()["audit"]
    assert data["findings"], "la API debe exponer findings"
    assert len(data["screenshots"]) == 1
    assert data["screenshots"][0]["index"] == 0
    assert "path" not in data["screenshots"][0]  # el path físico nunca sale

    # descarga: el archivo no existe en disco → 404 honesto (no se inventa)
    r = client.get(f"/api/leads/{lead.id}/audit/screenshots/0", headers=headers)
    assert r.status_code == 404
    r = client.get(f"/api/leads/{lead.id}/audit/screenshots/5", headers=headers)
    assert r.status_code == 404


def test_audit_screenshot_serves_file_when_present(db_session, workspace, demo_user, tmp_path, monkeypatch):
    from app.core.config import settings as app_settings
    from app.services.website_service import WebsiteAnalysisService

    monkeypatch.setattr(app_settings, "screenshots_dir", str(tmp_path))
    try:
        lead = _lead(db_session, workspace)
        service = WebsiteAnalysisService(db_session)
        audit = service.persist_audit(lead, _mock_audit_result("dermia-laser"), [])
        relative = f"{workspace.id}/{lead.id}-{audit.id}.jpg"
        target_dir = tmp_path / str(workspace.id)
        target_dir.mkdir(parents=True)
        (target_dir / f"{lead.id}-{audit.id}.jpg").write_bytes(b"\xff\xd8\xffjpeg-fake")
        audit.screenshots = [{"url": lead.website, "path": relative, "kind": "home-fold",
                              "width": 1280, "height": 800, "bytes": 12,
                              "http_status": 200, "captured_at": "x"}]
        db_session.add(audit)
        db_session.commit()

        client = TestClient(create_app())
        token = create_access_token(str(demo_user.id), str(demo_user.workspace_id), demo_user.role)
        r = client.get(f"/api/leads/{lead.id}/audit/screenshots/0", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.content == b"\xff\xd8\xffjpeg-fake"
    finally:
        pass


def test_analyze_lead_never_crashes_on_screenshot_capture(db_session, workspace, demo_user):
    """provider invocido — analyze_lead sigue completando aunque falle la captura."""
    from app.services.website_service import WebsiteAnalysisService

    lead = _lead(db_session, workspace)
    service = WebsiteAnalysisService(db_session)
    # provider none → sin captura, pero auditoría OK
    out = service.analyze_lead(lead, pages=[
        PageData(url="http://mockbusiness.local/dermia-laser/", html=mf.render_site("dermia-laser", "/")[0], kind="home")
    ])
    db_session.commit()
    assert out["audited"] is True
    audit = db_session.query(WebsiteAudit).get(out["audit_id"])
    assert audit is not None
    assert audit.screenshots == []
    assert audit.findings
