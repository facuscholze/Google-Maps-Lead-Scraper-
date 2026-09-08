"""Search endpoints (spec §57): CRUD, preview, run, status, presets."""
from __future__ import annotations

import math

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.enums import SearchStatus
from app.core.logging import log_event
from app.models.search import Search, SearchPreset
from app.models.user import User
from app.repositories.jobs import JobRepository
from app.repositories.searches import SearchRepository
from app.schemas.api import (
    JobOut,
    PresetCreate,
    PresetOut,
    SearchCreate,
    SearchOut,
    SearchPreview,
    SearchStatusOut,
)
from app.services.pipeline import SearchPipeline
from app.services.query_builder import build_search_query

router = APIRouter(prefix="/searches", tags=["searches"])


def _to_out(search: Search) -> SearchOut:
    out = SearchOut.model_validate(search)
    if search.started_at and search.completed_at:
        out.duration_seconds = round((search.completed_at - search.started_at).total_seconds(), 1)
    return out


@router.post("/preview", response_model=SearchPreview)
def preview_search(payload: SearchCreate) -> SearchPreview:
    query = build_search_query(payload.category, payload.location)
    pages = math.ceil(min(payload.max_results, 100) / 20)
    return SearchPreview(
        query=query,
        location=payload.location,
        max_results=payload.max_results,
        min_reviews=payload.min_reviews,
        max_reviews=payload.max_reviews,
        min_rating=payload.min_rating,
        estimated_api_calls=pages,
    )


@router.post("", response_model=SearchOut, status_code=status.HTTP_201_CREATED)
def create_search(
    payload: SearchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    query = build_search_query(payload.category, payload.location)
    search = Search(
        workspace_id=user.workspace_id,
        query=query,
        location=payload.location,
        category=payload.category,
        max_results=payload.max_results,
        min_reviews=payload.min_reviews,
        max_reviews=payload.max_reviews,
        min_rating=payload.min_rating,
        only_with_website=payload.only_with_website,
        only_with_phone=payload.only_with_phone,
        try_find_email=payload.try_find_email,
        status=SearchStatus.PENDING.value,
    )
    db.add(search)
    db.commit()
    db.refresh(search)
    log_event("search_created", search_id=search.id, query=query)
    return _to_out(search)


@router.get("", response_model=list[SearchOut])
def list_searches(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SearchOut]:
    searches = SearchRepository(db).list_for_workspace(user.workspace_id)
    return [_to_out(s) for s in searches]


@router.get("/{search_id}", response_model=SearchOut)
def get_search(
    search_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    search = SearchRepository(db).get_for_workspace(user.workspace_id, search_id)
    if search is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Búsqueda no encontrada")
    return _to_out(search)


@router.post("/{search_id}/run", response_model=SearchOut)
def run_search(
    search_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    search = SearchRepository(db).get_for_workspace(user.workspace_id, search_id)
    if search is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Búsqueda no encontrada")
    if search.status == SearchStatus.RUNNING.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La búsqueda ya está en ejecución")
    from app.core.config import settings

    if settings.execution_mode == "celery":
        from app.workers.tasks import run_search_task

        run_search_task.delay(search_id)
    else:
        background_tasks.add_task(_run_in_thread, search_id)
    db.refresh(search)
    return _to_out(search)


def _run_in_thread(search_id: int) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        SearchPipeline(db).run(search_id)
    finally:
        db.close()


@router.get("/{search_id}/status", response_model=SearchStatusOut)
def search_status(
    search_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchStatusOut:
    search = SearchRepository(db).get_for_workspace(user.workspace_id, search_id)
    if search is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Búsqueda no encontrada")
    jobs = JobRepository(db).list_for_workspace(user.workspace_id, search_id=search_id)
    return SearchStatusOut(
        search=_to_out(search),
        jobs=[JobOut.model_validate(j) for j in jobs],
        running=search.status == SearchStatus.RUNNING.value,
    )


@router.get("/presets", response_model=list[PresetOut])
def list_presets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PresetOut]:
    presets = list(
        db.scalars(
            select(SearchPreset)
            .where(SearchPreset.workspace_id == user.workspace_id)
            .order_by(SearchPreset.id.desc())
        ).all()
    )
    return [PresetOut.model_validate(p) for p in presets]


@router.post("/presets", response_model=PresetOut, status_code=status.HTTP_201_CREATED)
def create_preset(
    payload: PresetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PresetOut:
    preset = SearchPreset(
        workspace_id=user.workspace_id,
        name=payload.name,
        config_json=payload.config,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return PresetOut.model_validate(preset)


@router.delete("/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_preset(
    preset_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    preset = db.scalar(
        select(SearchPreset).where(
            SearchPreset.id == preset_id,
            SearchPreset.workspace_id == user.workspace_id,
        )
    )
    if preset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Preset no encontrado")
    db.delete(preset)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
