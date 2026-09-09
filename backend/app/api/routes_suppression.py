"""Suppression list endpoints (spec §48, §87)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.logging import log_event
from app.models.user import User
from app.repositories.emailing import SuppressionRepository, mark_lead_suppressed
from app.schemas.api import SuppressionImport, SuppressionIn, SuppressionOut

router = APIRouter(prefix="/suppression", tags=["suppression"])


@router.get("", response_model=list[SuppressionOut])
def list_suppression(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    q: str | None = None,
) -> list[SuppressionOut]:
    entries = SuppressionRepository(db).list_for_workspace(user.workspace_id, search=q)
    return [SuppressionOut.model_validate(e) for e in entries]


@router.post("", response_model=SuppressionOut, status_code=status.HTTP_201_CREATED)
def add_suppression(
    payload: SuppressionIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuppressionOut:
    repo = SuppressionRepository(db)
    if repo.is_suppressed(user.workspace_id, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "El email ya está en la lista")
    entry = repo.add(user.workspace_id, payload.email, payload.reason, payload.note)
    mark_lead_suppressed(db, user.workspace_id, payload.email)
    db.commit()
    log_event("opt_out", email=payload.email.lower(), workspace_id=user.workspace_id)
    return SuppressionOut.model_validate(entry)


@router.post("/import", response_model=dict)
def import_suppression(
    payload: SuppressionImport,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    repo = SuppressionRepository(db)
    valid = [e for e in payload.emails if e and "@" in e]
    added = repo.import_emails(user.workspace_id, valid, payload.reason)
    for email in valid:
        mark_lead_suppressed(db, user.workspace_id, email)
    db.commit()
    return {"added": added, "skipped": len(valid) - added}


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_suppression(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    removed = SuppressionRepository(db).remove(user.workspace_id, entry_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entrada no encontrada")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
