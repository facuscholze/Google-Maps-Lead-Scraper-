"""OpenAI-compatible AI provider.

Sends the gathered *evidence* (never business logic) to a chat-completions
endpoint, validates the JSON answer against Pydantic models, and falls back to
the deterministic rule-based provider on any error or invalid output.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.integrations.ai.prompts import PROPOSAL_SYSTEM, WEBSITE_AUDIT_SYSTEM
from app.integrations.ai.rule_based import RuleBasedProvider
from app.schemas.ai import AIProposal, AIScoreResult, AIWebsiteAudit

logger = logging.getLogger("avascho.ai")


class OpenAICompatibleProvider(RuleBasedProvider):
    """Extends the rule-based provider (deterministic fallback) with LLM calls."""

    name = "openai_compatible"

    def __init__(self) -> None:
        super().__init__()
        self._model = settings.ai_model
        self._api_key = settings.ai_api_key
        self._url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"

    # ------------------------------------------------------------------
    def _chat_json(self, system: str, user: str, timeout: float = 60.0) -> dict[str, Any]:
        if not self._api_key:
            raise ValueError("AI_API_KEY not configured")
        response = httpx.post(
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return json.loads(text)

    def analyze_website(self, evidence: dict[str, Any]) -> AIWebsiteAudit:
        try:
            payload = self._chat_json(WEBSITE_AUDIT_SYSTEM, json.dumps(evidence, ensure_ascii=False)[:12000])
            return AIWebsiteAudit.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM analyze_website failed (%s) -> rule-based fallback", exc)
            return super().analyze_website(evidence)

    def generate_proposal(self, context: dict[str, Any]) -> AIProposal:
        try:
            payload = self._chat_json(PROPOSAL_SYSTEM, json.dumps(context, ensure_ascii=False)[:12000])
            result = AIProposal.model_validate(payload)
            # Always render our own brand HTML so the visual identity stays consistent.
            from app.services.emailing.email_html import render_proposal_email

            content = {
                "business_name": context.get("business_name"),
                "website_score": context.get("website_score"),
                "opening": result.opening,
                "personalized_observation": result.personalized_observation,
                "strengths": result.strengths,
                "opportunities": result.opportunities,
                "recommended_service": result.recommended_service,
                "recommended_solution": result.recommended_solution,
                "call_to_action": result.call_to_action,
                "signature": result.signature,
            }
            result.html = render_proposal_email(content)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM generate_proposal failed (%s) -> rule-based fallback", exc)
            return super().generate_proposal(context)

    def score_lead(self, evidence: dict[str, Any]) -> AIScoreResult:
        # Scoring stays rule-based on purpose: it must remain fully explainable.
        return super().score_lead(evidence)
