"""Rule-based AI provider — deterministic and evidence-based.

Offline by design: audits/scoring/recommendations are produced by the local
analysis engine, so the platform works without any external AI dependency and
cannot hallucinate business facts.
"""
from __future__ import annotations

from typing import Any

from app.integrations.ai.base import AIProvider
from app.schemas.ai import AIProposal, AIScoreResult, AIWebsiteAudit
from app.services.analysis.auditor import WebsiteAuditor
from app.services.analysis.scorer import LeadScorer


class RuleBasedProvider(AIProvider):
    name = "rule_based"

    def analyze_website(self, evidence: dict[str, Any]) -> AIWebsiteAudit:
        from app.services.analysis.types import AuditResult, ExtractedWebsite

        site = ExtractedWebsite(**self._extracted_kwargs(evidence))
        result: AuditResult = WebsiteAuditor().audit(site, evidence.get("content_hash"))
        return AIWebsiteAudit(
            website_score=result.overall_score,
            subscores=result.subscores,
            strengths=[s["text"] for s in result.strengths],
            weaknesses=[
                {
                    "problem": w["text"],
                    "evidence": w["evidence"],
                    "source_url": w.get("source_url"),
                    "kind": w["kind"],
                }
                for w in result.weaknesses
            ],
            opportunities=[o["opportunity"] for o in result.opportunities],
            recommended_service=self.recommend_service(evidence),
            reason=" ".join(
                f"{w['text']}: {w['evidence']}" for w in result.weaknesses[:3]
            ),
            confidence=round(min(0.95, 0.4 + result.page_count * 0.1), 2),
        )

    def score_lead(self, evidence: dict[str, Any]) -> AIScoreResult:
        result = LeadScorer().score(**evidence)
        return AIScoreResult(
            lead_score=result["lead_score"],
            opportunity_score=result["opportunity_score"],
            temperature=result["temperature"],
            recommended_action=result["recommended_action"],
            recommended_service=result["recommended_service"],
            breakdown=result["lead_breakdown"] + result["opportunity_breakdown"],
            why_this_lead=result["why_this_lead"],
            confidence=result["confidence"],
        )

    def detect_opportunities(self, evidence: dict[str, Any]) -> list[dict[str, Any]]:
        from app.services.analysis.types import ExtractedWebsite

        site = ExtractedWebsite(**self._extracted_kwargs(evidence))
        return WebsiteAuditor().audit(site).opportunities

    def recommend_service(self, evidence: dict[str, Any]) -> str:
        from app.services.analysis.scorer import LeadScorer
        from app.services.analysis.types import ExtractedWebsite

        site = ExtractedWebsite(**self._extracted_kwargs(evidence))
        audit = WebsiteAuditor().audit(site)
        return LeadScorer._recommend_service(audit)

    def generate_proposal(self, context: dict[str, Any]) -> AIProposal:
        from app.services.emailing.proposal import ProposalWriter

        return ProposalWriter().build(context, provider=self.name)

    generate_email = generate_proposal

    @staticmethod
    def _extracted_kwargs(evidence: dict[str, Any]) -> dict[str, Any]:
        """Extract only ExtractedWebsite-compatible keys."""
        from app.services.analysis.types import ExtractedWebsite

        allowed = set(ExtractedWebsite.__dataclass_fields__.keys())
        kwargs = {k: v for k, v in evidence.items() if k in allowed}
        return kwargs
