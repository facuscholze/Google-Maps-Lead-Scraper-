"""AIProvider protocol (spec §60)."""
from __future__ import annotations

from typing import Any, Protocol

from app.schemas.ai import AIProposal, AIScoreResult, AIWebsiteAudit


class AIProvider(Protocol):
    name: str

    def analyze_website(self, evidence: dict[str, Any]) -> AIWebsiteAudit: ...

    def score_lead(self, evidence: dict[str, Any]) -> AIScoreResult: ...

    def detect_opportunities(self, evidence: dict[str, Any]) -> list[dict[str, Any]]: ...

    def recommend_service(self, evidence: dict[str, Any]) -> str: ...

    def generate_proposal(self, context: dict[str, Any]) -> AIProposal: ...

    def generate_email(self, context: dict[str, Any]) -> AIProposal: ...
