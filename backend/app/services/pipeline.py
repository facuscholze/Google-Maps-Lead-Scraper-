"""Search pipeline orchestrator (spec §5, §52-53, §89).

Runs the stages as discrete tracked jobs:
  GOOGLE_PLACES (or GRID_SWEEP) → FILTER/INGEST → WEBSITE_CRAWL
  → WEBSITE_ANALYSIS → LEAD_SCORING → CONTACT_DISCOVERY → DONE

- In `inline` mode it executes synchronously in-process (dev/tests); in
  `celery` mode the API dispatches the whole search to a worker — the stages
  are identical (a search never completes without audit+scoring).
- Area searches (`mode="grid"`) fan out into rectangular cells, one text query
  per cell with `locationRestriction`, deduping by place_id across cells.
- Cost guardrails: estimated cost is written before running; each API call
  accrues `api_cost_usd`; a `budget_cap_usd` stops the sweep cooperatively.
- Cancellation is cooperative: the pipeline checks `cancel_requested` between
  units of work and finishes as CANCELLED, never mid-DB-transaction.

Progress is written to Job rows so the UI can poll or stream via SSE.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import JobType, SearchStatus
from app.core.logging import log_event
from app.integrations.google.places import search_places
from app.models.lead import Lead
from app.models.search import Search, SearchLead
from app.repositories.jobs import JobRepository
from app.services import geo_grid
from app.services.field_mask import PLACES_FIELD_MASK
from app.services.lead_dedupe import normalize_domain, normalize_phone
from app.services.lead_service import score_lead
from app.services.place_mapper import lead_matches_filters, map_place
from app.services.places_pricing import cost_per_call_usd, sku_for_field_mask
from app.services.website_service import WebsiteAnalysisService
from app.utils.text import utcnow

logger = logging.getLogger("avascho.pipeline")

# Candidate registry: place_id -> mapped dict for the current run
State = dict[str, Any]


class SearchCancelled(Exception):
    """Cooperative cancellation raised between units of work."""


class SearchPipeline:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self._sku = sku_for_field_mask(PLACES_FIELD_MASK, settings.places_price_per_1k_usd)

    # ------------------------------------------------------------------ run ---
    def run(self, search_id: int) -> None:
        search = self.db.get(Search, search_id)
        if search is None:
            raise ValueError(f"Search {search_id} not found")
        if search.status == SearchStatus.RUNNING.value:
            return
        search.status = SearchStatus.RUNNING.value
        search.started_at = utcnow()
        self.db.add(search)
        self.db.commit()
        log_event("search_started", search_id=search.id, query=search.query, mode=search.mode)

        state: State = {
            "candidates": [],
            "qualified": [],
            "pages_by_lead": {},
            "seen_place_ids": set(),
            "phone_index": {},
            "domain_index": {},
        }
        try:
            if search.mode == "grid":
                self._stage_grid_sweep(search, state)
            else:
                self._stage_google_places(search, state)
            self._stage_filter_ingest(search, state)
            # Stages 3-6 run in every execution mode (inline AND celery) — a
            # search without audit/scoring is a bug, not an optimization.
            self._stage_website_intelligence(search, state)
            self._stage_scoring(search, state)
            self._stage_contact_discovery(search, state)
            search.status = SearchStatus.COMPLETED.value
            search.completed_at = utcnow()
            self._refresh_search_totals(search)
            self.db.add(search)
            self.db.commit()
            log_event(
                "search_completed", search_id=search.id,
                found=search.results_total, qualified=search.results_qualified,
                api_calls=search.api_calls, cost_usd=search.api_cost_usd,
            )
        except SearchCancelled:
            self.db.rollback()
            search = self.db.get(Search, search_id)
            search.status = SearchStatus.CANCELLED.value
            search.completed_at = utcnow()
            search.cancel_requested = False
            self.db.add(search)
            self._fail_running_jobs(search, "Cancelada por el usuario")
            self.db.commit()
            log_event("search_cancelled", search_id=search.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            search.status = SearchStatus.FAILED.value
            search.error_message = str(exc)[:1000]
            search.completed_at = utcnow()
            self.db.add(search)
            self.db.commit()
            log_event("search_failed", search_id=search.id, error=str(exc)[:500])

    # ----------------------------------------------------------- guardrails ---
    def _check_cancelled(self, search: Search) -> None:
        self.db.refresh(search)
        if search.cancel_requested:
            raise SearchCancelled()

    def _accrue_call(self, search: Search, calls: int = 1) -> None:
        search.api_calls += calls
        search.api_cost_usd = round(search.api_cost_usd + calls * cost_per_call_usd(self._sku), 4)

    def _budget_allows(self, search: Search) -> bool:
        if search.budget_cap_usd is None:
            return True
        next_cost = search.api_cost_usd + cost_per_call_usd(self._sku)
        if next_cost > search.budget_cap_usd:
            search.budget_exhausted = True
            self.db.add(search)
            return False
        return True

    # ----------------------------------------------------------------- stage 1
    def _stage_google_places(self, search: Search, state: State) -> None:
        job = self.jobs.create_job(
            search.workspace_id, JobType.GOOGLE_PLACES, search.id,
            payload={"query": search.query},
        )
        self.db.commit()
        log_event("google_request_start", search_id=search.id)
        provider_name, result = None, None
        try:
            if not self._budget_allows(search):
                self.jobs.complete(job)
                self.db.commit()
                state["candidates"] = []
                return
            provider_name, result = _search_places_sync(search.query, search.max_results)
            self._accrue_call(search, result.api_calls)
        except Exception as exc:  # noqa: BLE001
            self.jobs.fail(job, str(exc))
            self.db.commit()
            raise
        state["candidates"] = result.places
        self.jobs.progress(
            job,
            current_step=f"Buscando en Google Places… {len(result.places)} encontrados",
            done=len(result.places),
            total=search.max_results,
        )
        self.jobs.complete(job)
        search.google_pages = result.pages_fetched
        self.db.add(search)
        self.db.commit()
        log_event(
            "results_received", search_id=search.id, provider=provider_name,
            count=len(result.places), pages=result.pages_fetched, truncated=result.truncated,
        )

    # ------------------------------------------------------------ grid sweep --
    def _stage_grid_sweep(self, search: Search, state: State) -> None:
        """Fan the query out over grid cells; each cell is one text search with
        ``locationRestriction.rectangle`` (officially supported — see geo_grid)."""
        cells = geo_grid.cells_from_geo(search.geo_json or {}, settings.grid_cell_km)
        if len(cells) > settings.grid_max_cells:
            raise ValueError(
                f"El área requiere {len(cells)} celdas y el máximo es "
                f"{settings.grid_max_cells}. Acotá el área o subí GRID_CELL_KM."
            )
        search.grid_total_cells = len(cells)
        job = self.jobs.create_job(
            search.workspace_id, JobType.GOOGLE_PLACES, search.id,
            payload={"query": search.query, "cells": len(cells), "mode": "grid"},
        )
        self.db.commit()

        seen: set[str] = state["seen_place_ids"]
        all_places: list[dict[str, Any]] = []
        pending = list(cells)
        capped_count = 0

        while pending:
            cell = pending.pop(0)
            self._check_cancelled(search)
            if not self._budget_allows(search):
                log_event("grid_budget_exhausted", search_id=search.id,
                          done=search.grid_done_cells, total=search.grid_total_cells)
                break
            try:
                _provider, result = _search_places_sync(
                    search.query, geo_grid.CELL_RESULT_CAP, cell.to_restriction()
                )
            except Exception as exc:  # noqa: BLE001
                # One bad cell does not sink the sweep.
                logger.warning("grid cell failed (search %s): %s", search.id, exc)
                search.grid_done_cells += 1
                continue
            self._accrue_call(search, result.api_calls)

            new_in_cell = 0
            for place in result.places:
                pid = place.get("id")
                if not pid or pid in seen:
                    continue  # solapamiento de celdas — ya lo tenemos
                seen.add(pid)
                all_places.append(place)
                new_in_cell += 1

            search.grid_done_cells += 1
            if len(result.places) >= geo_grid.CELL_RESULT_CAP:
                if settings.grid_subdivide and geo_grid.can_subdivide(
                    cell, settings.grid_max_subdivision_depth
                ):
                    children = geo_grid.subdivide(cell)
                    pending.extend(children)
                    search.grid_total_cells += len(children)
                else:
                    capped_count += 1
                    search.grid_capped_cells = capped_count

            self.jobs.progress(
                job,
                current_step=(
                    f"Celda {search.grid_done_cells}/{search.grid_total_cells} · "
                    f"{len(all_places)} negocios · ~USD {search.api_cost_usd:.2f}"
                ),
                done=search.grid_done_cells,
                total=search.grid_total_cells,
            )
            self._refresh_search_totals(search)
            self.db.add(search)
            self.db.commit()

        state["candidates"] = all_places
        self.jobs.progress(
            job,
            f"Barrido completo: {len(all_places)} negocios únicos "
            f"({capped_count} celdas al tope)",
            search.grid_done_cells,
            search.grid_total_cells,
        )
        self.jobs.complete(job)
        search.google_pages = search.api_calls
        self.db.add(search)
        self.db.commit()
        log_event(
            "grid_completed", search_id=search.id, places=len(all_places),
            cells=search.grid_done_cells, capped=capped_count,
            calls=search.api_calls, cost=search.api_cost_usd,
        )

    # ----------------------------------------------------------------- stage 2
    def _load_dedupe_indexes(self, search: Search, state: State) -> None:
        """Preload phone/domain → lead_id maps of the workspace (secondary
        dedupe signals for chains & duplicated listings)."""
        if state["phone_index"] or state["domain_index"]:
            return
        rows = self.db.scalars(
            select(Lead).where(Lead.workspace_id == search.workspace_id)
        ).all()
        for lead in rows:
            for phone in (lead.phone, lead.international_phone):
                norm = normalize_phone(phone)
                if norm:
                    state["phone_index"].setdefault(norm, lead.id)
            domain = normalize_domain(lead.website)
            if domain:
                state["domain_index"].setdefault(domain, lead.id)

    def _find_existing_lead(
        self, search: Search, state: State, mapped: dict[str, Any]
    ) -> tuple[Lead | None, str | None]:
        """Locate an existing lead by place_id → phone → domain (in that order)."""
        existing = self.db.scalar(
            select(Lead).where(
                Lead.workspace_id == search.workspace_id,
                Lead.place_id == mapped["place_id"],
            )
        )
        if existing is not None:
            return existing, "place_id"
        for phone in (mapped.get("phone"), mapped.get("international_phone")):
            norm = normalize_phone(phone)
            if norm and norm in state["phone_index"]:
                lead = self.db.get(Lead, state["phone_index"][norm])
                if lead is not None:
                    return lead, "phone"
        domain = normalize_domain(mapped.get("website"))
        if domain and domain in state["domain_index"]:
            lead = self.db.get(Lead, state["domain_index"][domain])
            if lead is not None:
                return lead, "domain"
        return None, None

    def _register_dedupe_indexes(self, state: State, lead_id: int, mapped: dict[str, Any]) -> None:
        for phone in (mapped.get("phone"), mapped.get("international_phone")):
            norm = normalize_phone(phone)
            if norm:
                state["phone_index"].setdefault(norm, lead_id)
        domain = normalize_domain(mapped.get("website"))
        if domain:
            state["domain_index"].setdefault(domain, lead_id)

    def _stage_filter_ingest(self, search: Search, state: State) -> None:
        job = self.jobs.create_job(
            search.workspace_id, JobType.FILTER, search.id,
            payload={"min_reviews": search.min_reviews, "max_reviews": search.max_reviews,
                     "min_rating": search.min_rating},
        )
        self.db.commit()
        self._load_dedupe_indexes(search, state)
        mapped_all: list[dict[str, Any]] = []
        for candidate in state["candidates"]:
            mapped = map_place(candidate)
            if mapped.get("place_id"):
                mapped_all.append(mapped)
        qualified: list[dict[str, Any]] = []
        seen_link: set[tuple[int, int]] = set()
        deduped = 0

        for idx, mapped in enumerate(mapped_all):
            matches = lead_matches_filters(mapped, search)
            existing, reason = self._find_existing_lead(search, state, mapped)
            lead_id = existing.id if existing else None
            if reason in ("phone", "domain"):
                deduped += 1
                log_event(
                    "lead_deduped", search_id=search.id, by=reason,
                    lead_id=lead_id, place_id=mapped["place_id"],
                )
            if not lead_id:
                lead = Lead(workspace_id=search.workspace_id, **mapped)
                self.db.add(lead)
                self.db.flush()
                lead_id = lead.id
                log_event("lead_created", lead_id=lead_id, search_id=search.id,
                          place_id=mapped["place_id"], matched=matches)
            self._register_dedupe_indexes(state, lead_id, mapped)
            if matches:
                key = (search.id, lead_id)
                if key not in seen_link:
                    seen_link.add(key)
                    self.db.add(SearchLead(search_id=search.id, lead_id=lead_id,
                                           matched=True, created_at=utcnow()))
                qualified.append(mapped)
                state.setdefault("lead_ids", []).append(lead_id)
            if (idx + 1) % 10 == 0 or idx == len(mapped_all) - 1:
                self.jobs.progress(job, f"Filtrando… {len(qualified)} califican", idx + 1, len(mapped_all))
                self.db.commit()

        search.results_total = len(mapped_all)
        search.results_qualified = len(qualified)
        search.deduped_count = deduped
        self.db.add(search)
        self.jobs.progress(job, f"{len(qualified)} leads califican", len(mapped_all), len(mapped_all))
        self.jobs.complete(job)
        self.db.commit()
        log_event("leads_qualified", search_id=search.id, qualified=len(qualified), deduped=deduped)

    # ------------------------------------------------------------ stage 3 & 4
    def _stage_website_intelligence(self, search: Search, state: State) -> None:
        lead_ids = list(dict.fromkeys(state.get("lead_ids", [])))
        leads = list(
            self.db.scalars(
                select(Lead).where(
                    Lead.workspace_id == search.workspace_id,
                    Lead.id.in_(lead_ids),
                )
            ).all()
        ) if lead_ids else []
        leads = [l for l in leads if l.website]
        if not leads:
            return

        crawl_job = self.jobs.create_job(
            search.workspace_id, JobType.WEBSITE_CRAWL, search.id,
            payload={"total_leads": len(leads)},
        )
        analysis_job = self.jobs.create_job(
            search.workspace_id, JobType.WEBSITE_ANALYSIS, search.id,
            payload={"total_leads": len(leads)},
        )
        self.db.commit()

        service = WebsiteAnalysisService(self.db)
        crawls_done = 0
        analysis_done = 0
        for lead in leads:
            self._check_cancelled(search)
            cached = service.reusable_audit(lead)
            if cached is not None:
                crawls_done += 1
                analysis_done += 1
                self.jobs.progress(crawl_job, "Reusando auditoría vigente…", crawls_done, len(leads))
                self.jobs.progress(analysis_job, "Auditoría vigente (reutilizada).", analysis_done, len(leads))
                continue
            try:
                pages = service.crawl_lead(lead)
                crawls_done += 1
                state.setdefault("pages_by_lead", {})[lead.id] = pages
                self.jobs.progress(
                    crawl_job,
                    f"Crawleando {lead.business_name[:40]}… {len(pages)} páginas",
                    crawls_done, len(leads),
                )
                outcome = service.analyze_lead(lead, pages)
                if outcome.get("audited"):
                    log_event("audit_completed", lead_id=lead.id, score=outcome.get("audit_id"))
            except Exception as exc:  # noqa: BLE001
                logger.warning("analysis failed for lead %s: %s", lead.id, exc)
            finally:
                analysis_done += 1
                self.jobs.progress(
                    analysis_job,
                    f"Analizando websites… {analysis_done} / {len(leads)}",
                    analysis_done, len(leads),
                )
                if analysis_done % 5 == 0:
                    self.db.commit()

        self.jobs.complete(crawl_job)
        self.jobs.complete(analysis_job)
        search.websites_analyzed = sum(
            1 for l in leads if l.website_status == "ANALYZED"
        )
        self.db.add(search)
        self.db.commit()

    # ----------------------------------------------------------------- stage 5
    def _stage_scoring(self, search: Search, state: State) -> None:
        lead_ids = list(dict.fromkeys(state.get("lead_ids", [])))
        if not lead_ids:
            return
        job = self.jobs.create_job(
            search.workspace_id, JobType.LEAD_SCORING, search.id,
            payload={"leads": len(lead_ids)},
        )
        self.db.commit()
        leads = list(
            self.db.scalars(
                select(Lead).where(
                    Lead.workspace_id == search.workspace_id,
                    Lead.id.in_(lead_ids),
                )
            ).all()
        )
        for idx, lead in enumerate(leads):
            score_lead(self.db, lead)
            if (idx + 1) % 5 == 0 or idx == len(leads) - 1:
                self.jobs.progress(
                    job, f"Puntuando leads… {idx + 1} / {len(leads)}", idx + 1, len(leads)
                )
                self.db.commit()
        self.jobs.complete(job)
        self.db.commit()
        log_event("leads_scored", search_id=search.id, count=len(leads))

    # ---------------------------------------------------------------- stage 6
    def _stage_contact_discovery(self, search: Search, state: State) -> None:
        """Final pass: ensure email fields reflect *found* public data only."""
        lead_ids = list(dict.fromkeys(state.get("lead_ids", [])))
        if not lead_ids:
            return
        job = self.jobs.create_job(
            search.workspace_id, JobType.CONTACT_DISCOVERY, search.id
        )
        self.db.commit()
        leads = list(
            self.db.scalars(
                select(Lead).where(Lead.id.in_(lead_ids))
            ).all()
        )
        emails_found = 0
        for lead in leads:
            if lead.email:
                emails_found += 1
            # LOW-confidence emails never auto-send (enforced at queue time too)
            if lead.email_confidence == "LOW":
                lead.recommended_action = "REVIEW_FIRST"
                self.db.add(lead)
        self.jobs.complete(job)
        search.emails_found = emails_found
        self._refresh_search_totals(search)
        self.db.commit()
        log_event("contact_discovery_done", search_id=search.id, emails=emails_found)

    # ----------------------------------------------------------------- utils --
    def _refresh_search_totals(self, search: Search) -> None:
        from app.repositories.searches import SearchRepository

        SearchRepository(self.db).update_totals(search)

    def _fail_running_jobs(self, search: Search, message: str) -> None:
        from app.core.enums import JobStatus

        for job in self.jobs.list_for_workspace(search.workspace_id, search_id=search.id):
            if job.status == JobStatus.RUNNING.value:
                job.status = JobStatus.CANCELLED.value
                job.error_message = message[:2000]
                job.completed_at = utcnow()
                self.db.add(job)


def _search_places_sync(
    query: str,
    max_results: int,
    location_restriction: dict[str, Any] | None = None,
):
    """Small synchronous wrapper around the async provider search."""

    return asyncio.run(search_places(query, max_results, location_restriction))
