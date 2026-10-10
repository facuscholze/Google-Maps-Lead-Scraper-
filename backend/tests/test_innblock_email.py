"""innblock mail design: rendering, escaping, real-data-only sections, and the
raw RFC-822 message used by the Gmail sender (multipart/alternative)."""
from __future__ import annotations

import base64
import email
from email import policy

import pytest

from app.integrations.gmail.sender import build_raw_message
from app.services.emailing.email_html import (
    TemplateRenderError,
    render_plain_text,
    render_proposal_email,
)
from app.services.emailing import email_html


def _content(**overrides):
    base = {
        "business_name": "Panadería <b>La Espiga</b>",
        "opening": "Hola, equipo de Panadería <b>La Espiga</b>,",
        "personalized_observation": "Estuvimos revisando su web.\nVimos un formulario sin respuesta.",
        "opportunities": [
            {"title": "Consultas sin respuesta", "opportunity": "Responder automáticamente", "evidence": "Formulario <script>x</script>"},
        ],
        "recommended_solution": "Desde innblock trabajamos en automatización.",
        "call_to_action": "Si te interesa, lo vemos.",
        "signature": "",
        "reviews": 128,
        "rating": 4.6,
        "website_score": 5.5,
    }
    base.update(overrides)
    return base


def test_renders_brand_design_without_leftover_placeholders():
    html = render_proposal_email(_content())
    assert "{{" not in html and "}}" not in html
    assert "innblock" in html
    assert "Lo convertimos en software." in html
    assert "Qué hacemos" in html
    assert "BAJA" in html
    assert "wa.me/543755629953" in html  # socio phone -> wa.me link (digits only)


def test_lead_data_is_escaped():
    html = render_proposal_email(_content())
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "Panadería &lt;b&gt;La Espiga&lt;/b&gt;" in html
    assert "<b>La Espiga</b>" not in html


def test_evidence_uses_real_lead_values():
    html = render_proposal_email(_content(reviews=128, rating=4.6, website_score=5.5))
    assert ">128<" in html
    assert "4.6 ⭐" in html
    assert "5.5/10" in html


def test_evidence_and_diagnostico_omitted_without_data():
    html = render_proposal_email(
        _content(reviews=None, rating=None, website_score=None, opportunities=[], recommended_solution="")
    )
    assert "05 · Evidencia" not in html
    assert "01 · Diagnóstico" not in html
    assert "{{" not in html


def test_missing_evidence_cell_shows_dash_not_invented_number():
    html = render_proposal_email(_content(reviews=None, rating=4.2, website_score=None))
    assert "05 · Evidencia" in html
    assert "4.2 ⭐" in html
    assert ">—<" in html


def test_unknown_placeholder_raises(monkeypatch):
    monkeypatch.setattr(
        email_html, "_template_values", lambda content: {"saludo": "Hola"}
    )
    with pytest.raises(TemplateRenderError):
        render_proposal_email(_content())


def test_plain_text_mirrors_content_and_has_unsubscribe():
    text = render_plain_text(_content())
    assert "Consultas sin respuesta" in text
    assert "Si te interesa, lo vemos." in text
    assert "BAJA" in text
    assert "<" not in text or "<b>" in text  # plain text is not HTML-escaped


def test_raw_message_is_multipart_alternative_utf8():
    raw = build_raw_message(
        to_email="lead@example.com",
        from_email="ventas@example.com",
        subject="Una idea para Panadería La Espiga: ¿qué se hace a mano?",
        body_html=render_proposal_email(_content()),
        body_plain=render_plain_text(_content()),
    )
    decoded = base64.urlsafe_b64decode(raw.encode())
    msg = email.message_from_bytes(decoded, policy=policy.default)
    assert msg.get_content_type() == "multipart/alternative"
    parts = [p.get_content_type() for p in msg.iter_parts()]
    assert parts == ["text/plain", "text/html"]  # plain first, html preferred last
    assert msg["Subject"] == "Una idea para Panadería La Espiga: ¿qué se hace a mano?"
    html_part = msg.get_body(preferencelist=("html",)).get_content()
    assert "innblock" in html_part


def test_ascii_subject_stays_plain_header():
    raw = build_raw_message("a@b.com", "c@d.com", "Hola simple", "<p>x</p>", "x")
    decoded = base64.urlsafe_b64decode(raw.encode()).decode()
    assert "Subject: Hola simple" in decoded
