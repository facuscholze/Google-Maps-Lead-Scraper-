"""Website audit & evidence tests (spec §20-24)."""
from app.integrations import mock_fixtures as mf
from app.integrations.crawler.extractor import WebsiteExtractor
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.types import PageData


def _audit(slug: str):
    pages = [
        PageData(url=f"http://mockbusiness.local/{slug}{p}", html=mf.render_site(slug, p)[0], kind="other")
        for p in mf.site_pages(slug)
    ]
    site = WebsiteExtractor().extract(pages)
    return WebsiteAuditor().audit(site)


def test_score_range():
    for p in mf.site_profiles():
        audit = _audit(p["slug"])
        assert 0.0 <= audit.overall_score <= 10.0
        for sub in audit.subscores.values():
            assert 0.0 <= sub <= 10.0


def test_weaknesses_have_evidence():
    audit = _audit("dermia-laser")  # weak site
    assert audit.weaknesses
    for weakness in audit.weaknesses:
        assert weakness["evidence"]
        assert weakness["kind"] in ("FACT", "INFERENCE")


def test_no_booking_opportunity_detected():
    audit = _audit("renovarte")  # no booking, no whatsapp
    titles = [o["title"] for o in audit.opportunities]
    assert any("reserva" in t.lower() for t in titles)


def test_booking_present_no_false_booking_problem():
    audit = _audit("clinica-aurora")  # booking + whatsapp + email
    problems = [w["text"] for w in audit.weaknesses]
    assert not any("reserv" in p.lower() and "no se detect" in p.lower() for p in problems)


def test_strengths_grounded():
    audit = _audit("estetica-vittoria")
    assert audit.strengths
    assert audit.strengths[0]["kind"] == "FACT"


def test_evidence_is_real_not_invented():
    audit = _audit("lucerna-estetica")
    for weakness in audit.weaknesses:
        assert weakness["evidence"]
        assert len(weakness["evidence"]) < 300
