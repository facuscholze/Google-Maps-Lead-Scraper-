"""Scoring config resolution per workspace (Fase 6, D6.1).

Sin fila en `scoring_configs` se aplican los defaults — la configuración es
OPT-IN. El rescore es siempre una acción explícita del usuario (D6.4); cambiar
la config nunca reescribe scores silenciosamente.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead import ScoringConfig
from app.services.analysis.scorer import DEFAULT_THRESHOLDS, resolve_weights


@dataclass(frozen=True)
class ResolvedScoringConfig:
    weights: dict[str, float]
    thresholds: tuple[int, int, int]  # hot, warm, cold
    config_id: int | None = None  # None = defaults (sin fila persistida)


DEFAULT = ResolvedScoringConfig(weights=resolve_weights(None), thresholds=DEFAULT_THRESHOLDS)


def load_scoring_config(db: Session, workspace_id: int) -> ResolvedScoringConfig:
    row = db.scalar(
        select(ScoringConfig).where(ScoringConfig.workspace_id == workspace_id)
    )
    if row is None:
        return DEFAULT
    return ResolvedScoringConfig(
        weights=resolve_weights(row.weights_json),
        thresholds=(row.hot_min, row.warm_min, row.cold_min),
        config_id=row.id,
    )
