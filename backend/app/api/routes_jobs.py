"""Job monitor endpoints (spec §52)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.jobs import JobRepository
from app.schemas.api import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search_id: int | None = None,
) -> list[JobOut]:
    jobs = JobRepository(db).list_for_workspace(user.workspace_id, search_id=search_id)
    return [JobOut.model_validate(j) for j in jobs]
