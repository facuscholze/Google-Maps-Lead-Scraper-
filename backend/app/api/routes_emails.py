"""Email queue endpoints (spec §46)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.emailing import EmailRepository
from app.schemas.api import EmailOut

router = APIRouter(prefix="/emails", tags=["emails"])


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


@router.get("/{email_id}", response_model=EmailOut)
def get_email(
    email_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailOut:
    email = EmailRepository(db).get_for_workspace(user.workspace_id, email_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Email no encontrado")
    return EmailOut.model_validate(email)


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
