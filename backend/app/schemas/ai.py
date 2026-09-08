"""Pydantic models for AI structured output (spec §61)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AIFindingItem(BaseModel):
    problem: str
    evidence: str
    source_url: str | None = None
    kind: str = "INFERENCE"  # FACT | INFERENCE


class AIWebsiteAudit(BaseModel):
    website_score: float = Field(ge=0, le=10)
    subscores: dict[str, float]
    strengths: list[str] = []
    weaknesses: list[AIFindingItem] = []
    opportunities: list[str] = []
    recommended_service: str | None = None
    reason: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class AIScoreResult(BaseModel):
    lead_score: int = Field(ge=0, le=100)
    opportunity_score: int = Field(ge=0, le=100)
    temperature: str
    recommended_action: str
    recommended_service: str
    breakdown: list[dict] = []
    why_this_lead: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class AIProposal(BaseModel):
    subject: str
    opening: str
    personalized_observation: str
    strengths: list[str] = []
    opportunities: list[dict] = []
    recommended_solution: str
    call_to_action: str
    signature: str
    plain_text: str
    html: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    model_note: str | None = None
