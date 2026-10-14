"""Search endpoints (spec §57): CRUD, preview, run, status, presets, SSE events."""
from __future__ import annotations

import json
import math
import time
from collections.abc import Generator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import _validate_payload, get_current_user, get_current_user_optional
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.enums import SearchStatus
from app.core.logging import log_event
from app.core.security import decode_access_token
from app.utils.text import utcnow
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
from app.services import geo_grid
from app.services.field_mask import PLACES_FIELD_MASK
from app.services.pipeline import SearchPipeline
from app.services.places_pricing import cost_per_call_usd, estimate_cost_usd, sku_for_field_mask
from app.services.query_builder import build_search_query

router = APIRouter(prefix="/searches", tags=["searches"])

TERMINAL_STATUSES = {
    SearchStatus.COMPLETED.value,
    SearchStatus.FAILED.value,
    SearchStatus.CANCELLED.value,
}

MAX_SSE_SECONDS = 30 * 60  # guard: no streams left open forever


def _to_out(search: Search) -> SearchOut:
    out = SearchOut.model_validate(search)
    if search.started_at and search.completed_at:
        out.duration_seconds = round((search.completed_at - search.started_at).total_seconds(), 1)
    return out


def _search_plan(payload: SearchCreate) -> dict:
    """Estimate API calls & cost (worst-case, SKU-priced — see places_pricing)."""
    sku = sku_for_field_mask(PLACES_FIELD_MASK, settings.places_price_per_1k_usd)
    per_call = cost_per_call_usd(sku)
    query = build_search_query(payload.category, payload.location)
    warnings: list[str] = []

    if payload.geo is not None:
        cells = geo_grid.cells_from_geo(payload.geo.to_spec(), settings.grid_cell_km)
        warnings_extra = []
        if len(cells) > settings.grid_max_cells:
            warnings_extra.append(
                f"El área requiere {len(cells)} celdas y el máximo por búsqueda es "
                f"{settings.grid_max_cells}: acotá el área o aumentá el tamaño de celda."
            )
        # 1 page per cell (60-result cap); worst case 3 pages.
        calls_min = len(cells)
        calls_max = len(cells) * 3
        return {
            "query": query,
            "mode": "grid",
            "grid_cells": len(cells),
            "estimated_api_calls": calls_min,
            "estimated_api_calls_max": calls_max,
            "estimated_cost_usd": estimate_cost_usd(calls_min, sku),
            "estimated_cost_max_usd": estimate_cost_usd(calls_max, sku),
            "warnings": warnings + warnings_extra,
        }

    # Text mode: official Text Search (New) returns max 60 results per query.
    effective = min(payload.max_results, 60)
    pages = math.ceil(effective / 20)
    if payload.max_results > 60:
        warnings.append(
            "Text Search (New) devuelve como máximo 60 resultados por consulta: "
            f"se devolverán hasta {effective} de {payload.max_results}. "
            "Usá una búsqueda por mapa (grilla) para cubrir más negocios."
        )
    return {
        "query": query,
        "mode": "text",
        "grid_cells": 0,
        "estimated_api_calls": pages,
        "estimated_api_calls_max": pages,
        "estimated_cost_usd": estimate_cost_usd(pages, sku),
        "estimated_cost_max_usd": estimate_cost_usd(pages, sku),
        "warnings": warnings,
    }


@router.post("/preview", response_model=SearchPreview)
def preview_search(payload: SearchCreate) -> SearchPreview:
    plan = _search_plan(payload)
    return SearchPreview(
        query=plan["query"],
        location=payload.location,
        mode=plan["mode"],
        max_results=payload.max_results,
        min_reviews=payload.min_reviews,
        max_reviews=payload.max_reviews,
        min_rating=payload.min_rating,
        estimated_api_calls=plan["estimated_api_calls"],
        estimated_api_calls_max=plan["estimated_api_calls_max"],
        estimated_cost_usd=plan["estimated_cost_usd"],
        estimated_cost_max_usd=plan["estimated_cost_max_usd"],
        grid_cells=plan["grid_cells"],
        budget_cap_usd=payload.budget_cap_usd,
        warnings=plan["warnings"],
    )


@router.post("", response_model=SearchOut, status_code=status.HTTP_201_CREATED)
def create_search(
    payload: SearchCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    plan = _search_plan(payload)
    blocking = [w for w in plan["warnings"] if "máximo por búsqueda" in w]
    if blocking:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(blocking))
    geo_spec = payload.geo.to_spec() if payload.geo else None
    search = Search(
        workspace_id=user.workspace_id,
        query=plan["query"],
        location=payload.location,
        category=payload.category,
        mode=plan["mode"],
        geo_json=geo_spec,
        budget_cap_usd=payload.budget_cap_usd,
        estimated_api_calls=plan["estimated_api_calls"],
        estimated_cost_usd=plan["estimated_cost_usd"],
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
    log_event(
        "search_created", search_id=search.id, query=plan["query"],
        mode=plan["mode"], est_calls=plan["estimated_api_calls"],
        est_cost=plan["estimated_cost_usd"],
    )
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
    if settings.execution_mode == "celery":
        from app.workers.tasks import run_search_task

        run_search_task.delay(search_id)
    else:
        background_tasks.add_task(_run_in_thread, search_id)
    db.refresh(search)
    return _to_out(search)


def _run_in_thread(search_id: int) -> None:
    db = SessionLocal()
    try:
        SearchPipeline(db).run(search_id)
    finally:
        db.close()


@router.post("/{search_id}/cancel", response_model=SearchOut)
def cancel_search(
    search_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchOut:
    """Cooperative cancellation: the pipeline stops between cells/leads and
    lands on CANCELLED — never mid-transaction. Already-terminal searches 409."""
    search = SearchRepository(db).get_for_workspace(user.workspace_id, search_id)
    if search is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Búsqueda no encontrada")
    if search.status in TERMINAL_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "La búsqueda ya terminó")
    if search.status == SearchStatus.RUNNING.value:
        search.cancel_requested = True
    else:  # PENDING: cancel immediately
        search.status = SearchStatus.CANCELLED.value
        search.completed_at = utcnow()
    db.add(search)
    db.commit()
    db.refresh(search)
    log_event("search_cancel_requested", search_id=search.id)
    return _to_out(search)


# ---------------------------------------------------------------- SSE stream --
def _sse_user_from_token(token: str | None, db: Session) -> User | None:
    if not token:
        return None
    try:
        claims = decode_access_token(token)
    except Exception:  # noqa: BLE001
        return None
    return _validate_payload(claims, db)


def _event_stream(workspace_id: int, search_id: int) -> Generator[str, None, None]:
    """Emit `search` + `jobs` snapshots every second until terminal state."""
    started = time.monotonic()
    last_heartbeat = started
    last_payload = ""
    with SessionLocal() as db:  # own session: the request session is closed
        while True:
            search = SearchRepository(db).get_for_workspace(workspace_id, search_id)
            if search is None:
                yield "event: error\ndata: {\"detail\": \"not found\"}\n\n"
                return
            jobs = JobRepository(db).list_for_workspace(workspace_id, search_id=search_id)
            payload = json.dumps(
                {
                    "search": _to_out(search).model_dump(mode="json"),
                    "jobs": [JobOut.model_validate(j).model_dump(mode="json") for j in jobs],
                },
                ensure_ascii=False,
            )
            if payload != last_payload:
                last_payload = payload
                yield f"event: snapshot\ndata: {payload}\n\n"
            db.expire_all()
            if search.status in TERMINAL_STATUSES:
                yield "event: done\ndata: {}\n\n"
                return
            now = time.monotonic()
            if now - last_heartbeat >= 15:
                last_heartbeat = now
                yield ": heartbeat\n\n"
            if now - started > MAX_SSE_SECONDS:
                yield "event: timeout\ndata: {}\n\n"
                return
            time.sleep(1.0)


@router.get("/{search_id}/events")
def search_events(
    search_id: int,
    token: str | None = Query(default=None),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Server-Sent Events stream of search progress.

    Browsers' EventSource can't send Authorization headers, so the access token
    is accepted as `?token=` (short-lived, standard practice). `Authorization:
    Bearer` keeps working for curl/clients.
    """
    if user is None:
        user = _sse_user_from_token(token, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    search = SearchRepository(db).get_for_workspace(user.workspace_id, search_id)
    if search is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Búsqueda no encontrada")
    return StreamingResponse(
        _event_stream(user.workspace_id, search_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # keep nginx/uvicorn from buffering SSE
        },
    )


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
