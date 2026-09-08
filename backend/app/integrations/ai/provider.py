"""AI provider factory (spec §60, §90)."""
from __future__ import annotations

from app.core.config import settings
from app.integrations.ai.base import AIProvider
from app.integrations.ai.openai_compatible import OpenAICompatibleProvider
from app.integrations.ai.rule_based import RuleBasedProvider


def get_ai_provider() -> AIProvider:
    mode = (settings.ai_provider or "rule_based").lower()
    if mode == "openai_compatible":
        if settings.ai_api_key:
            return OpenAICompatibleProvider()
        # no key configured → fall back silently to deterministic engine
        return RuleBasedProvider()
    if mode == "mock":
        return RuleBasedProvider()
    return RuleBasedProvider()
