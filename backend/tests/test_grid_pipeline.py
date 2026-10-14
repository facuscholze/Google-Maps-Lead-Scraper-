"""Grid-sweep pipeline: dedupe across cells, cost accounting, budget & cancel
guardrails (Fase 2, offline mock provider)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.enums import SearchStatus
from app.core.seed import seed_demo
from app.models.lead import Lead
from app.models.search import Search
from app.services import geo_grid
from app.services.field_mask import PLACES_FIELD_MASK
from app.services.pipeline import SearchPipeline
from app.services.places_pricing import cost_per_call_usd, sku_for_field_mask


@pytest.fixture(autouse=True)
def _clean_domain(db_session):
    from app.models.jobs import Job
    from app.models.search import SearchLead

    for model in (Job, SearchLead, Lead, Search):
        db_session.execute(model.__table__.delete())
    db_session.commit()
    yield


# Rectangle covering the whole mock fixture lattice (Montevideo).
GEO = {
    "type": "rect",
    "sw": [-34.96, -56.20],
    "ne": [-34.87, -56.13],
}


def _make_grid_search(db_session, workspace, budget_cap_usd=None, max_results=100):
    seed_demo(db_session)
    cells = geo_grid.cells_from_geo(GEO, settings.grid_cell_km)
    sku = sku_for_field_mask(PLACES_FIELD_MASK, settings.places_price_per_1k_usd)
    search = Search(
        workspace_id=workspace.id,
        query="Clínicas, Montevideo",
        category="Clínicas",
        location="Montevideo",
        mode="grid",
        geo_json=GEO,
        budget_cap_usd=budget_cap_usd,
        estimated_api_calls=len(cells),
        estimated_cost_usd=round(len(cells) * cost_per_call_usd(sku), 4),
        max_results=max_results,
        status=SearchStatus.PENDING.value,
    )
    db_session.add(search)
    db_session.commit()
    db_session.refresh(search)
    return search


def test_grid_sweep_runs_and_dedupes(db_session, workspace):
    search = _make_grid_search(db_session, workspace)
    SearchPipeline(db_session).run(search.id)
    db_session.refresh(search)

    assert search.status == SearchStatus.COMPLETED.value, search.error_message
    assert search.grid_done_cells == search.grid_total_cells
    planned = len(geo_grid.cells_from_geo(GEO, settings.grid_cell_km))
    assert search.grid_done_cells >= planned, "subdivisions only add cells"
    assert search.api_calls >= 1
    # cost accounting: every call accrues at the configured SKU price
    sku = sku_for_field_mask(PLACES_FIELD_MASK, settings.places_price_per_1k_usd)
    expected = round(search.api_calls * cost_per_call_usd(sku), 4)
    assert search.api_cost_usd == pytest.approx(expected, abs=0.001)
    # overlapping cells legitimately re-return the same places; place_id dedupe
    # must keep exactly one lead per unique place
    leads = db_session.scalars(select(Lead).where(Lead.workspace_id == workspace.id)).all()
    place_ids = [l.place_id for l in leads]
    assert len(place_ids) == len(set(place_ids))
    assert search.results_total == len(leads)


def test_grid_budget_cap_stops_sweep(db_session, workspace):
    sku = sku_for_field_mask(PLACES_FIELD_MASK, settings.places_price_per_1k_usd)
    planned = len(geo_grid.cells_from_geo(GEO, settings.grid_cell_km))
    two_calls = cost_per_call_usd(sku) * 2
    search = _make_grid_search(db_session, workspace, budget_cap_usd=round(two_calls, 4))
    SearchPipeline(db_session).run(search.id)
    db_session.refresh(search)

    assert search.status == SearchStatus.COMPLETED.value
    assert search.budget_exhausted is True
    assert planned >= 4, "fixture bbox should require several cells"
    assert search.grid_done_cells < planned, "budget must stop the sweep before the last cells"
    assert search.api_cost_usd <= search.budget_cap_usd + 1e-9
    # partial cell results are kept and still ingested consistently
    leads = db_session.scalars(select(Lead).where(Lead.workspace_id == workspace.id)).all()
    assert search.results_total == len(leads)


def test_grid_cancel_is_cooperative(db_session, workspace):
    search = _make_grid_search(db_session, workspace)
    search.cancel_requested = True
    db_session.add(search)
    db_session.commit()
    SearchPipeline(db_session).run(search.id)
    db_session.refresh(search)
    assert search.status == SearchStatus.CANCELLED.value
    assert search.completed_at is not None


def test_text_mode_unaffected(db_session, workspace):
    seed_demo(db_session)
    search = Search(
        workspace_id=workspace.id, query="Clínicas, Montevideo", category="Clínicas",
        location="Montevideo", max_results=40, status=SearchStatus.PENDING.value,
    )
    db_session.add(search)
    db_session.commit()
    SearchPipeline(db_session).run(search.id)
    db_session.refresh(search)
    assert search.status == SearchStatus.COMPLETED.value
    assert search.mode == "text"
    assert search.api_calls >= 1
    assert search.api_cost_usd > 0
    assert search.grid_total_cells == 0
