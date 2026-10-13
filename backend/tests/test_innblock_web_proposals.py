"""Regression coverage for Innblock rendering and web-only sales positioning."""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.integrations.ai.openai_compatible import OpenAICompatibleProvider
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.scorer import LeadScorer
from app.services.analysis.types import ExtractedWebsite
from app.services.catalog import AVA_SCHO_SERVICES
from app.services.emailing.email_html import _TEMPLATE_PATH, render_proposal_email
from app.services.emailing.proposal import ProposalWriter
from app.services.emailing.proposal_service import ProposalService


def test_packaged_template_matches_source():
    source = (Path(__file__).resolve().parents[2] / 'nuevo html innblock.html').read_text()
    inner = re.search(r'<script type="text/plain" id="plantilla">\s*(.*?)\s*</script>', source, re.S)[1]
    assert _TEMPLATE_PATH.read_text().strip() == inner


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
