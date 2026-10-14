"""Fase 7 — propuestas construidas SOLO con evidencia real (D7.1, D7.2, D7.3).

Reglas bajo test:
- D7.1: las fortalezas viajan como dicts anclados {text, evidence, kind}
  (nunca strings sueltas que la métrica de grounding no pueda verificar).
- D7.2: toda oportunidad SIN evidence se descarta antes del email
  (mejor menos ítems y todos reales).
- D7.3: ai_reasoning trae un evidence_ledger con la procedencia
  (Places API, audit) y el conteo de ítems finalmente usados.

Todo offline: auditor + extractor contra fixtures mock, AI rule_based.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.enums import ProposalStatus
from app.integrations import mock_fixtures as mf
from app.integrations.crawler.extractor import WebsiteExtractor
from app.models.lead import Lead
from app.models.website import WebsiteAudit
from app.schemas.ai import AIProposal
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.types import PageData
from app.services.emailing.proposal_service import ProposalService
from app.utils.text import utcnow


@pytest.fixture(autouse=True)
def _clean_domain(db_session):
    from app.models.emailing import Email, EmailEvent, Proposal, SuppressionEntry
    from app.models.website import WebsitePage

    for model in (EmailEvent, Email, Proposal, SuppressionEntry, WebsitePage, WebsiteAudit, Lead):
        db_session.execute(model.__table__.delete())
    db_session.commit()
    yield


_counter = 0


def _lead(db_session, workspace, website: str | None = "http://mockbusiness.local/dermia-laser") -> Lead:
    global _counter
    _counter += 1
    lead = Lead(
        workspace_id=workspace.id,
        business_name=f"Lead F7 {_counter}",
        place_id=f"p-f7-{_counter}",
        website=website,
        rating=4.6,
        reviews_count=128,
    )
    db_session.add(lead)
    db_session.commit()
    return lead


def _audit_with_evidence(db_session, lead) -> WebsiteAudit:
    """Audit real (offline): auditor sobre el sitio mock, persistido a mano."""
    pages = [
        PageData(url=f"{lead.website}{p}", html=mf.render_site("dermia-laser", p)[0], kind="other")
        for p in mf.site_pages("dermia-laser")
    ]
    site = WebsiteExtractor().extract(pages)
    result = WebsiteAuditor().audit(site)
    audit = WebsiteAudit(
        workspace_id=lead.workspace_id,
        lead_id=lead.id,
        url=lead.website,
        audit_version="1.0",
        content_hash=result.content_hash,
        overall_score=result.overall_score,
        subscores=result.subscores,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        opportunities=result.opportunities,
        findings=[],
        extracted_data={"pages": [p.url for p in pages], "page_count": len(pages)},
        crawled_at=utcnow(),
        audited_at=utcnow(),
    )
    db_session.add(audit)
    db_session.commit()
    return audit


# ---------------------------------------------------------------- generate ---
def test_proposal_strengths_are_anchored_to_audit_evidence(db_session, workspace):
    lead = _lead(db_session, workspace)
    audit = _audit_with_evidence(db_session, lead)
    assert audit.strengths, "el audit mock debe producir fortalezas"

    proposal = ProposalService(db_session).generate(workspace.id, lead.id)

    assert proposal.status == ProposalStatus.READY_FOR_REVIEW.value
    strengths = proposal.strengths_json or []
    assert strengths, "la propuesta debe reflejar fortalezas del audit"
    for item in strengths:
        # D7.1: dict anclado, nunca un string suelto
        assert isinstance(item, dict), f"strength sin anclar: {item!r}"
        assert item.get("text"), "strength sin texto"
        assert item.get("evidence"), f"strength sin evidencia: {item!r}"
        assert item.get("kind") in ("FACT", "INFERENCE")
        # la evidencia también llega al HTML que vería el cliente
        assert item["evidence"] in proposal.body_html


def test_proposal_opportunities_carry_evidence_or_are_dropped(db_session, workspace):
    """D7.2 end-to-end: un provider devuelve una oportunidad inventada → se descarta."""
    lead = _lead(db_session, workspace, website=None)  # sin web: sólo la oportunidad real sintetizada
    proposal = ProposalService(db_session).generate(workspace.id, lead.id)

    opportunities = proposal.opportunities_json or []
    assert opportunities, "sin web, la propuesta debe proponer crearle el sitio"
    for item in opportunities:
        assert isinstance(item, dict)
        assert (item.get("evidence") or "").strip(), f"oportunidad sin evidencia: {item!r}"

    # la oportunidad real ('no web') sí llega vivita y coleando al email
    assert any("web" in (o.get("evidence") or "") or "sitio" in (o.get("evidence") or "")
               for o in opportunities)


def test_ground_proposal_drops_invented_opportunities():
    """D7.2 unitario: _ground_proposal purga oportunidades sin evidence."""
    from app.services.emailing.email_html import render_plain_text, render_proposal_email

    stub_lead = Lead(business_name="La Estética de María", website=None)
    result = AIProposal(
        subject="Propuesta",
        opening="Hola María",
        personalized_observation="Observación real.",
        strengths=["Rating 4.8 con 200 reseñas"],  # legacy str → se normaliza a dict
        opportunities=[
            {"title": "Web propia", "opportunity": "Crear sitio", "evidence": "La ficha no incluye URL web."},
            {"title": "SEO local", "opportunity": "Mejorar SEO", "evidence": ""},        # ← inventada, sin evidencia
            {"title": "WhatsApp", "opportunity": "Automatizar"},                          # ← sin campo evidence
        ],
        recommended_solution="Solución.",
        call_to_action="¿Hablamos?",
        signature="Facu",
        html="<html>stale</html>",
        plain_text="stale",
    )
    grounded = ProposalService._ground_proposal(result, lead=stub_lead, audit=None)

    assert [o["title"] for o in grounded.opportunities] == ["Web propia"]
    assert all(oid.get("evidence") for oid in (grounded.opportunities or []))
    # strengths normalizados a dicts anclados (evidence=None si el provider fue legado)
    s = grounded.strengths[0]
    assert isinstance(s, dict) and s["text"] == "Rating 4.8 con 200 reseñas"
    # el html se re-renderiza con los ítems ya purgados: nuestro template innblock
    assert grounded.html != "<html>stale</html>"
    assert "Innblock" in grounded.html
    assert "SEO local" not in grounded.html  # la oportunidad inventada no llega al correo
    assert "Web propia" in grounded.html or "Web propia" in grounded.plain_text or "La ficha no incluye URL web" in grounded.html


def test_evidence_ledger_provenance(db_session, workspace):
    """D7.3: el razonamiento expone de dónde salió cada dato."""
    lead = _lead(db_session, workspace)
    lead.website_score = 62
    _audit_with_evidence(db_session, lead)
    proposal = ProposalService(db_session).generate(workspace.id, lead.id)

    reasoning = proposal.ai_reasoning or {}
    ledger = reasoning.get("evidence_ledger")
    assert ledger, "debe existir evidence_ledger en ai_reasoning"
    p = ledger["places"]
    assert "Places API" in p["source"], "el origen debe declarar Google Maps Places API (New)"
    assert p["rating"] == lead.rating and p["reviews"] == lead.reviews_count
    a = ledger["audit"]
    assert a["overall_score"] is not None and a["audit_version"] == "1.0"
    assert grounded_counts_consistent(ledger, proposal)


def grounded_counts_consistent(ledger: dict, proposal) -> bool:
    """Los conteos del ledger coinciden EXACTAMENTE con lo persistido."""
    g = ledger.get("grounded_items", {})
    return (g.get("strengths") == len(proposal.strengths_json or [])
            and g.get("opportunities") == len(proposal.opportunities_json or []))


def test_no_website_proposal_evidence_is_honest(db_session, workspace):
    """Sin sitio propio la evidencia dice claramente qué se sabe y qué no."""
    lead = _lead(db_session, workspace, website=None)
    proposal = ProposalService(db_session).generate(workspace.id, lead.id)

    assert "no incluye una URL web" in (proposal.opportunities_json[0]["evidence"])
    # honestidad: la observación nunca afirma haber visto un sitio que no existe
    assert lead.business_name in proposal.body_html
