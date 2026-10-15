"""Regression coverage for Innblock rendering and web-only sales positioning."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.integrations.ai.openai_compatible import OpenAICompatibleProvider
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.scorer import LeadScorer
from app.services.analysis.types import ExtractedWebsite
from app.services.catalog import AVA_SCHO_SERVICES
from app.services.emailing.email_html import _TEMPLATE_PATH, render_plain_text, render_proposal_email
from app.services.emailing.proposal import ProposalWriter
from app.services.emailing.proposal_service import ProposalService


# --------------------------------------------------------------- Fase 8 -----

_ROOT = Path(__file__).resolve().parents[2]
_ORIGINAL = _ROOT / 'nuevo html mail.html'
_ORIGINAL_COPY = (_TEMPLATE_PATH.parent / 'email' / 'innblock_original.html')


def test_original_preserved_byte_identical():
    """D8.5: el original del usuario queda intacto dentro del paquete —
    la comparación es byte a byte (sin normalizaciones que escondan drift)."""
    assert _ORIGINAL_COPY.read_bytes() == _ORIGINAL.read_bytes()


def test_design_invariants_preserved():
    """El template de trabajo diverge del original SÓLO en slots dinámicos y
    en el copy de venta web (decisión F2/F7); el sistema de diseño de marca
    y los textos fijos quedan exactamente como los escribió el usuario."""
    tpl = _TEMPLATE_PATH.read_text()
    # sistema de diseño: portal animado, paleta y fuentes del original
    for css in ('portalIn', 'breathe', 'wave', 'coreBeat',
                'class="ring1"', 'class="ring2"', 'class="ring3"', 'class="ring4"',
                'class="core"', '#f5c2c2', '#ec8a8a', '#e24a4a'):
        assert css in tpl, f"falta pieza de diseño: {css}"
    for brand in ('{{rojo}}', '{{negro}}', 'Archivo', 'Instrument Serif', 'Martian Mono'):
        assert brand in tpl
    # robustez técnica F8 (los únicos cambios de head permitidos)
    for head_bit in ('width=device-width, initial-scale=1.0',
                     'name="color-scheme" content="light"',
                     'name="supported-color-schemes" content="light"',
                     'prefers-reduced-motion', 'max-width: 480px',
                     'width="600"'):
        assert head_bit in tpl
    # textos fijos que NO se tocan (estructura del original)
    for fixed in ('Qué hacemos',
                  '¿Lo que necesitás no está en la lista? Contanos igual. Lo vemos juntos.',
                  'Todo proyecto arrancó con un mensaje.',
                  'No hace falta que esté prolijo.',
                  'Sin promesas de resultados garantizados.',
                  'respondé con la palabra "BAJA"',
                  'Hablemos de tu web →'):
        assert fixed in tpl, f"falta texto fijo de marca: {fixed}"
    # y el footer sigue siendo negro con borde rojo
    assert 'border-top:4px solid {{rojo}}' in tpl


def test_firma_socios_exacta_siempre_presente():
    """D8.2: la firma de los socios es fija (nombres, roles, teléfonos, wa.me)
    — ni la IA ni la edición humana pueden tocarla; solo se edita la
    línea de despedida que la precede."""
    from app.services.emailing.email_html import SOCIOS, _wa_link

    result = render_proposal_email({
        'business_name': 'Negocio Real S.A.',
        'signature': 'Quedo atento, gracias.',  # despedida editada por humano
    })
    assert 'Quedo atento, gracias.' in result  # la despedida sí es editable
    for socio in SOCIOS:
        assert socio['nombre'] in result
        assert f"{socio['rol'].upper()} ·" in result.upper()
        assert socio['telefono'] in result
        assert _wa_link(socio['telefono']) in result
    assert 'border-left:3px solid #d90000' in result  # borde rojo del original
    assert 'class="col"' in result  # columnas apilables en mobile


def test_default_signature_is_closing_line_only():
    """Sin edición ni firma del provider: despedida "Saludos," + socios fijos.
    El viejo default 'Equipo Innblock' no debe reaparecer (duplicaba firma)."""
    result = render_proposal_email({'business_name': 'Test'})
    assert 'Saludos,' in result
    assert 'Equipo Innblock' not in result


def test_opt_out_mandatorio_en_html_y_plain():
    """D8.4: baja obligatoria en ambas representaciones con el texto del pie
    original — y el plain incluye el bloque de socios (paridad de firmas)."""
    content = {'business_name': 'Test', 'opening': 'Hola'}
    html_out = render_proposal_email(content)
    plain = render_plain_text(content)
    assert 'respondé con la palabra "BAJA"' in html_out
    assert 'respondé con la palabra "BAJA"' in plain
    for nombre in ('Facundo Scholze', 'Yamall Avalos'):
        assert nombre in plain


def test_list_unsubscribe_header_en_mime():
    """D8.3: el MIME real lleva List-Unsubscribe (mailto BAJA) — opt-out
    técnico nativo en Gmail, además del pie de marca."""
    import base64
    from app.integrations.gmail.sender import build_raw_message

    raw = build_raw_message(
        to_email='lead@example.com', from_email='hola@innblock.dev',
        subject='Test', body_html='<p>hola</p>', body_plain='hola',
        unsubscribe_email='hola@innblock.dev',
    )
    mime = base64.urlsafe_b64decode(raw.encode()).decode('utf-8')
    assert 'List-Unsubscribe: <mailto:hola@innblock.dev?subject=BAJA>' in mime
    assert 'List-Unsubscribe-Post: List-Unsubscribe=One-Click' in mime
    # sin configuración de contacto: NO se inventa el header
    raw2 = build_raw_message(
        to_email='lead@example.com', from_email='hola@innblock.dev',
        subject='Test', body_html=None, body_plain='hola',
    )
    mime2 = base64.urlsafe_b64decode(raw2.encode()).decode('utf-8')
    assert 'List-Unsubscribe' not in mime2


def test_special_chars_end_to_end():
    """Nombres con comillas, ampersands, emojis y unicode extremo no rompen
    ni el markup ni la sustitución estricta de slots."""
    result = render_proposal_email({
        'business_name': 'Mario & "Hijos" <Pelu> 💇‍♂️',
        'opening': 'Hola — "ustedes" & cía.\nSegunda línea con <b>html</b>',
        'personalized_observation': 'Vi ★★★★★ reseñas (100% reales).',
    })
    assert '{{' not in result and '}}' not in result
    assert '&amp;' in result and '&lt;b&gt;html&lt;/b&gt;' in result
    assert '<b>html</b>' not in result
    assert '💇' in result and '★★★★★' in result
    # la despedida y los socios siguen intactos pese a input hostil
    assert 'Facundo Scholze' in result


def test_innblock_render_is_personalized_and_safe():
    result = render_proposal_email({
        'business_name': '<script>alert(1)</script>',
        'opening': 'Hola <negocio>',
        'opportunities': [{'title': '<img src=x>', 'evidence': 'Dato real', 'opportunity': 'Una landing'}],
        'strengths': ['HTTPS'], 'recommended_solution': 'Solución propia',
    })
    assert 'class="ring1"' in result and '#d90000' in result
    assert '&lt;script&gt;' in result and '&lt;img src=x&gt;' in result
    assert 'Solución propia' in result and 'Dato real' in result
    assert '{{' not in result and '<script' not in result and '<iframe' not in result
    assert 'Panadería La Espiga' not in result and 'hola@tudominio' not in result
    assert '6–10' not in result and '100 %' not in result


def test_contact_url_validation(monkeypatch):
    monkeypatch.setattr(settings, 'proposal_contact_url', 'javascript:alert(1)')
    with pytest.raises(ValueError):
        render_proposal_email({})


@pytest.mark.parametrize('website,score,expected', [
    (None, None, 'Sitio web institucional'),
    ('https://example.com', 4, 'Rediseño web'),
    ('https://example.com', 9, 'Landing page'),
])
def test_web_service_and_legacy_context(website, score, expected):
    lead = SimpleNamespace(website=website, website_score=score,
        business_name='Negocio real', rating=3.1, reviews_count=20,
        detected_opportunities=[{'service': 'AI WhatsApp Agent', 'title': 'Agente IA'}],
        recommended_service='AI WhatsApp Agent', confidence=.8, lead_score=50,
        opportunity_score=50, why_this_lead='')
    context = ProposalService(None).build_context(lead, None)
    assert context['recommended_service'] == expected
    proposal = ProposalWriter().build(context)
    assert expected in proposal.subject and expected in proposal.html
    assert 'Agente IA' not in proposal.html and 'AI WhatsApp Agent' not in proposal.plain_text
    assert 'muy buena reputación' not in proposal.plain_text
    if not website:
        assert 'conviene confirmar' in proposal.plain_text


def test_llm_success_uses_innblock_not_model_html(monkeypatch):
    generated = ProposalWriter().build({'business_name': 'Test', 'recommended_service': 'Landing page'})
    payload = generated.model_dump()
    payload['html'] = '<script>untrusted</script>'
    payload['plain_text'] = 'stale plain text'
    monkeypatch.setattr(OpenAICompatibleProvider, '_chat_json', lambda *args, **kwargs: payload)
    result = OpenAICompatibleProvider().generate_proposal({'business_name': 'Test', 'recommended_service': 'Landing page'})
    assert 'class="ring1"' in result.html
    assert '<script>' not in result.html
    assert result.plain_text != 'stale plain text'
    assert result.opening in result.plain_text


def test_web_audit_absences_have_evidence():
    audit = WebsiteAuditor().audit(ExtractedWebsite(url='https://example.com', page_count=1))
    assert audit.opportunities
    assert all(o['service'] in AVA_SCHO_SERVICES and o['evidence'] for o in audit.opportunities)
    assert not WebsiteAuditor().audit(ExtractedWebsite()).opportunities


def test_no_website_is_sales_opportunity_and_breakdown_adds_up():
    result = LeadScorer().score(rating=4.7, reviews=100, website_score=None, audit=None,
        has_email=False, email_confidence=None, has_phone=True, has_website=False, business_name='Test')
    assert result['recommended_service'] == 'Sitio web institucional'
    assert result['opportunity_score'] >= 30
    assert result['opportunity_score'] == min(100, sum(x['delta'] for x in result['opportunity_breakdown']))
