"""Scoring configuración por workspace + rescore explícito (Fase 6, D6.1-D6.4).

Regla de producto: el re-score es siempre una acción explícita del usuario —
guardar la config NUNCA reescribe scores en segundo plano. El rescore es
determinista: recompute local sobre datos que ya tenemos (sin llamadas a
Places, sin invento).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import log_event
from app.models.lead import ScoringConfig
from app.models.user import User
from app.repositories.leads import LeadRepository
from app.schemas.api import (
    LeadsRescoreRequest,
    LeadsRescoreResponse,
    ScoringConfigIn,
    ScoringConfigOut,
)
from app.services.analysis.scorer import DEFAULT_THRESHOLDS, SCORE_CATEGORIES, resolve_weights
from app.services.lead_service import score_lead
from app.services.scoring_config_service import load_scoring_config

router = APIRouter(prefix="/scoring-config", tags=["scoring"])


def _out(row: ScoringConfig | None) -> ScoringConfigOut:
    if row is None:
        hot, warm, cold = DEFAULT_THRESHOLDS
        return ScoringConfigOut(
            id=None, weights=resolve_weights(None),
            hot_min=hot, warm_min=warm, cold_min=cold, is_default=True,
        )
    return ScoringConfigOut(
        id=row.id,
        weights=resolve_weights(row.weights_json),
        hot_min=row.hot_min,
        warm_min=row.warm_min,
        cold_min=row.cold_min,
        is_default=False,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _validate_thresholds(hot: int, warm: int, cold: int) -> None:
    if not (hot > warm > cold):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Los umbrales deben ser estrictamente hot({hot}) > warm({warm}) > cold({cold}).",
        )


@router.get("", response_model=ScoringConfigOut)
def get_scoring_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScoringConfigOut:
    row = db.scalar(
        select(ScoringConfig).where(ScoringConfig.workspace_id == user.workspace_id)
    )
    return _out(row)


@router.put("", response_model=ScoringConfigOut)
def put_scoring_config(
    payload: ScoringConfigIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScoringConfigOut:
    row = db.scalar(
        select(ScoringConfig).where(ScoringConfig.workspace_id == user.workspace_id)
    )
    if row is None:
        row = ScoringConfig(
            workspace_id=user.workspace_id,
            weights_json={},
            hot_min=80, warm_min=60, cold_min=40,
        )
        db.add(row)

    current = resolve_weights(row.weights_json)
    if payload.weights is not None:
        provided = {
            k: v for k, v in payload.weights.model_dump().items()
            if v is not None and k in SCORE_CATEGORIES
        }
        current.update(provided)
        row.weights_json = current

    hot = payload.hot_min if payload.hot_min is not None else row.hot_min
    warm = payload.warm_min if payload.warm_min is not None else row.warm_min
    cold = payload.cold_min if payload.cold_min is not None else row.cold_min
    _validate_thresholds(hot, warm, cold)
    row.hot_min, row.warm_min, row.cold_min = hot, warm, cold

    db.add(row)
    db.commit()
    db.refresh(row)
    log_event("scoring_config_updated", workspace_id=user.workspace_id, weights=current,
              thresholds=[hot, warm, cold])
    return _out(row)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_scoring_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.scalar(
        select(ScoringConfig).where(ScoringConfig.workspace_id == user.workspace_id)
    )
    if row is not None:
        db.delete(row)
        db.commit()
        log_event("scoring_config_reset", workspace_id=user.workspace_id)
    return None


@router.post("/rescore", response_model=LeadsRescoreResponse)
def rescore_leads(
    payload: LeadsRescoreRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadsRescoreResponse:
    """Recalcula lead/opportunity/temperature con la config vigente.

    Determinista y local: recomputa sobre datos persistidos, sin llamadas a
    Places. Excluye leads archivados — su puntuación es irrelevante igual."""
    from app.models.lead import Lead

    scoring_cfg = load_scoring_config(db, user.workspace_id)
    repo = LeadRepository(db)

    if payload.ids is not None:
        leads = [
            lead for lead_id in payload.ids
            if (lead := repo.get_for_workspace(user.workspace_id, lead_id)) is not None
        ]
        skipped = sorted(set(payload.ids) - {l.id for l in leads})
    else:
        leads = list(
            db.scalars(
                select(Lead).where(
                    Lead.workspace_id == user.workspace_id,
                    Lead.status != "ARCHIVED",
                )
            ).all()
        )
        skipped = []

    for lead in leads:
        score_lead(db, lead, config=scoring_cfg)
    db.commit()
    log_event("leads_rescored", workspace_id=user.workspace_id, count=len(leads),
              thresholds=list(scoring_cfg.thresholds))
    return LeadsRescoreResponse(rescored=len(leads), skipped=skipped)


@router.get("/categories")
def list_categories():
    """Metadatos para la UI (descripciones es-AR)."""
    return {
        "categories": [
            {"key": "reputation", "label": "Reputación", "description": "Rating de Google (estrellas)."},
            {"key": "reviews", "label": "Reseñas", "description": "Volumen de reseñas públicas."},
            {"key": "website_presence", "label": "Presencia web", "description": "Tener website y que esté operativo / potencial de web nueva."},
            {"key": "website_quality", "label": "Calidad web", "description": "Qué tan bien resuelto está el sitio (auditoría)."},
            {"key": "opportunities", "label": "Oportunidades", "description": "Mejoras concretas detectadas (CTA, mobile, conversión…)."},
            {"key": "phone", "label": "Teléfono", "description": "Contacto telefónico público."},
            {"key": "email", "label": "Email", "description": "Email público y su confianza."},
        ],
        "threshold_labels": [
            {"key": "hot_min", "label": "HOT desde"},
            {"key": "warm_min", "label": "WARM desde"},
            {"key": "cold_min", "label": "COLD desde"},
        ],
    }
