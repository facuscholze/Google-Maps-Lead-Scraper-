"""Website extraction & email confidence tests (spec §17-19)."""
from app.integrations import mock_fixtures as mf
from app.integrations.crawler.extractor import WebsiteExtractor
from app.services.analysis.types import PageData


def _extract(slug: str):
    pages = [
        PageData(url=f"http://mockbusiness.local/{slug}{p}", html=mf.render_site(slug, p)[0], kind="other")
        for p in mf.site_pages(slug)
    ]
    return WebsiteExtractor().extract(pages)


def test_email_on_contact_page_high_confidence():
    site = _extract("clinica-aurora")  # email on contact page
    assert site.emails
    assert site.best_email[1] == "HIGH"


def test_email_in_footer_detected():
    site = _extract("studio-derma")  # footer email
    assert site.best_email[0] == "contacto@studio-derma.com.uy"


def test_no_email_when_absent():
    site = _extract("vital-derma")  # no public email
    assert site.emails == []
    assert site.best_email == (None, None, None)


def test_whatsapp_detected():
    assert bool(_extract("clinica-aurora").whatsapp_numbers)


def test_booking_signals():
    site = _extract("clinica-aurora")
    assert site.has_booking_page is True
    no_booking = _extract("renovarte")
    assert no_booking.has_booking_page is False


def test_form_detection():
    assert _extract("pulso-skin").has_form is True
    assert _extract("estetica-oliva").has_form is False


def test_services_extracted():
    site = _extract("clinica-aurora")
    assert any("facial" in s.lower() for s in site.services)


def test_no_invented_emails():
    """Every found email must appear in the source HTML."""
    for p in mf.site_profiles()[:20]:
        site = _extract(p["slug"])
        html_blob = "".join(mf.render_site(p["slug"], path)[0] for path in mf.site_pages(p["slug"]))
        for item in site.emails:
            assert item["email"] in html_blob
