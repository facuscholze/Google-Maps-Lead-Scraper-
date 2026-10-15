"""Email queue endpoints (spec §46)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.emailing import EmailRepository
from app.schemas.api import EmailDetailOut, EmailOut

router = APIRouter(prefix="/emails", tags=["emails"])

# epoch aware para ordenar eventos (SQLite puede devolver datetimes naives)
EV_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


@router.get("", response_model=list[EmailOut])
def list_emails(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status_filter: str | None = None,
) -> list[EmailOut]:
    return [
        EmailOut.model_validate(e)
        for e in EmailRepository(db).list_for_workspace(user.workspace_id, status_filter)
    ]


@router.get("/{email_id}", response_model=EmailDetailOut)
def get_email(
    email_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailDetailOut:
    email = EmailRepository(db).get_for_workspace(user.workspace_id, email_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email no encontrado")
    # F10: timeline cronológico (SENT→RETRY→FAILED, mock fallback explícito)
    email.events.sort(key=lambda ev: ev.occurred_at or EV_EPOCH)
    return EmailDetailOut.model_validate(email)


@router.post("/{email_id}/cancel", response_model=EmailOut)
def cancel_email(
    email_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailOut:
    email = EmailRepository(db).get_for_workspace(user.workspace_id, email_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email no encontrado")
    if email.status == "QUEUED":
        email.status = "CANCELLED"
        db.add(email)
        db.commit()
    return EmailOut.model_validate(email)
