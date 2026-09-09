"""Proposal endpoints (spec §41-42, §57, §84)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import ProposalStatus
from app.models.emailing import Email
from app.models.lead import Lead
from app.models.user import User
from app.repositories.emailing import ProposalRepository
from app.schemas.api import ProposalOut, ProposalUpdate, SendRequest
from app.services.emailing.proposal_service import ProposalService
from app.services.emailing.queue import EmailQueueService, QueueValidationError

router = APIRouter(prefix="/proposals", tags=["proposals"])


def _to_out(proposal) -> ProposalOut:
    out = ProposalOut.model_validate(proposal)
    out.lead_name = proposal.lead.business_name if proposal.lead else None
    out.strengths = proposal.strengths_json
    out.opportunities = proposal.opportunities_json
    return out


@router.get("", response_model=list[ProposalOut])
def list_proposals(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lead_id: int | None = None,
    status_filter: str | None = None,
) -> list[ProposalOut]:
    proposals = ProposalRepository(db).list_for_workspace(user.workspace_id, lead_id)
    if status_filter:
        proposals = [p for p in proposals if p.status == status_filter]
    return [_to_out(p) for p in proposals]


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(
    proposal_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = ProposalRepository(db).get_for_workspace(user.workspace_id, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Propuesta no encontrada")
    return _to_out(proposal)


@router.put("/{proposal_id}", response_model=ProposalOut)
def update_proposal(
    proposal_id: int,
    payload: ProposalUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = ProposalRepository(db).get_for_workspace(user.workspace_id, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Propuesta no encontrada")
    if proposal.status == ProposalStatus.SENT.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede editar una propuesta ya enviada")
    updated = ProposalService(db).update_from_editor(proposal, payload.model_dump(exclude_unset=True))
    db.commit()
    return _to_out(updated)


@router.post("/{proposal_id}/regenerate", response_model=ProposalOut)
def regenerate_proposal(
    proposal_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = ProposalRepository(db).get_for_workspace(user.workspace_id, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Propuesta no encontrada")
    service = ProposalService(db)
    updated = service.generate(user.workspace_id, proposal.lead_id)
    db.commit()
    return _to_out(updated)


@router.post("/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(
    proposal_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = ProposalRepository(db).get_for_workspace(user.workspace_id, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Propuesta no encontrada")
    if proposal.status == ProposalStatus.SENT.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La propuesta ya fue enviada")
    approved = ProposalService(db).approve(proposal, user.id)
    db.commit()
    return _to_out(approved)


@router.post("/{proposal_id}/discard", response_model=ProposalOut)
def discard_proposal(
    proposal_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    proposal = ProposalRepository(db).get_for_workspace(user.workspace_id, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Propuesta no encontrada")
    discarded = ProposalService(db).discard(proposal)
    db.commit()
    return _to_out(discarded)


@router.post("/{proposal_id}/send", response_model=dict)
def send_proposal(
    proposal_id: int,
    payload: SendRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    proposal = ProposalRepository(db).get_for_workspace(user.workspace_id, proposal_id)
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Propuesta no encontrada")
    if proposal.status != ProposalStatus.APPROVED.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La propuesta debe estar APPROVED antes de enviarse (aprobación humana requerida)",
        )
    queue = EmailQueueService(db)
    from app.utils.text import utcnow

    scheduled = utcnow() if payload.send_now else payload.scheduled_at
    try:
        email = queue.queue_for_lead(
            workspace_id=user.workspace_id,
            lead_id=proposal.lead_id,
            proposal_id=proposal.id,
            account_id=payload.account_id,
            strategy=payload.strategy,
            scheduled_at=scheduled,
        )
    except QueueValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()

    if payload.send_now:
        # dispatch immediately in background (still respects account limits)
        background_tasks.add_task(_dispatch_now, user.workspace_id)
    return {"email_id": email.id, "status": email.status, "scheduled_at": email.scheduled_at}


def _dispatch_now(workspace_id: int) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        EmailQueueService(db).send_due(workspace_id)
    finally:
        db.close()
