"""Saved lead-table views (Fase 4 · D4.1): name → filter/column config."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.lead import LeadView
from app.models.user import User
from app.schemas.api import LeadViewIn, LeadViewOut

router = APIRouter(prefix="/lead-views", tags=["lead-views"])


def _get_for_ws(db: Session, workspace_id: int, view_id: int) -> LeadView | None:
    return db.scalar(
        select(LeadView).where(LeadView.id == view_id, LeadView.workspace_id == workspace_id)
    )


@router.get("", response_model=list[LeadViewOut])
def list_views(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LeadViewOut]:
    views = db.scalars(
        select(LeadView)
        .where(LeadView.workspace_id == user.workspace_id)
        .order_by(LeadView.name.asc())
    ).all()
    return [LeadViewOut.model_validate(v) for v in views]


@router.post("", response_model=LeadViewOut, status_code=status.HTTP_201_CREATED)
def create_view(
    payload: LeadViewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadViewOut:
    name = payload.name.strip()
    exists = db.scalar(
        select(LeadView).where(
            LeadView.workspace_id == user.workspace_id, LeadView.name == name
        )
    )
    if exists is not None:  # un nombre, una vista: actualizar es la intención natural
        exists.config_json = payload.config
        db.add(exists)
        db.commit()
        db.refresh(exists)
        return LeadViewOut.model_validate(exists)
    view = LeadView(workspace_id=user.workspace_id, name=name, config_json=payload.config)
    db.add(view)
    db.commit()
    db.refresh(view)
    return LeadViewOut.model_validate(view)


@router.put("/{view_id}", response_model=LeadViewOut)
def update_view(
    view_id: int,
    payload: LeadViewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadViewOut:
    view = _get_for_ws(db, user.workspace_id, view_id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vista no encontrada")
    view.name = payload.name.strip()
    view.config_json = payload.config
    db.add(view)
    db.commit()
    db.refresh(view)
    return LeadViewOut.model_validate(view)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_view(
    view_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    view = _get_for_ws(db, user.workspace_id, view_id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vista no encontrada")
    db.delete(view)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
