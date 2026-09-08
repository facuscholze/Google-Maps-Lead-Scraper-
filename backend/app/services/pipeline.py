"""Search pipeline orchestrator (spec §5, §52-53, §89).

Runs the stages as discrete tracked jobs:
  GOOGLE_PLACES → FILTER/INGEST → WEBSITE_CRAWL → WEBSITE_ANALYSIS
  → LEAD_SCORING → CONTACT_DISCOVERY → DONE

In `inline` mode it executes synchronously in-process (dev/tests); in `celery`
mode the API dispatches the whole search to a worker (see workers/tasks.py).
Progress is written to Job rows so the UI can poll without long-lived sockets.
"""
from __future__ import annotations

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
from app.services.lead_service import score_lead
from app.services.place_mapper import lead_matches_filters, map_place
from app.services.website_service import WebsiteAnalysisService
from app.utils.text import utcnow

logger = logging.getLogger("avascho.pipeline")

# Candidate registry: place_id -> mapped dict for the current run
State = dict[str, Any]


class SearchPipeline:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = JobRepository(db)

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
        log_event("search_started", search_id=search.id, query=search.query)

        state: State = {"candidates": [], "qualified": [], "pages_by_lead": {}}
        try:
            self._stage_google_places(search, state)
            self._stage_filter_ingest(search, state)
            if settings.execution_mode != "celery":
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
            )
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            search.status = SearchStatus.FAILED.value
            search.error_message = str(exc)[:1000]
            search.completed_at = utcnow()
            self.db.add(search)
            self.db.commit()
            log_event("search_failed", search_id=search.id, error=str(exc)[:500])

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
            provider_name, result = _search_places_sync(search)
        except Exception as exc:  # noqa: BLE001
            self.jobs.fail(job, str(exc))
            self.db.commit()
            raise
        state["candidates"] = result.places
        self.jobs.progress(
            job,
            current_step=f"Searching Google Places… {len(result.places)} encontrados",
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

    # ----------------------------------------------------------------- stage 2
    def _stage_filter_ingest(self, search: Search, state: State) -> None:
        job = self.jobs.create_job(
            search.workspace_id, JobType.FILTER, search.id,
            payload={"min_reviews": search.min_reviews, "max_reviews": search.max_reviews,
                     "min_rating": search.min_rating},
        )
        self.db.commit()
        mapped_all: list[dict[str, Any]] = [map_place(p) for p in state["candidates"] if map_place(p).get("place_id")]
        qualified: list[dict[str, Any]] = []
        seen_link: set[tuple[int, int]] = set()

        for idx, mapped in enumerate(mapped_all):
            matches = lead_matches_filters(mapped, search)
            existing = self.db.scalar(
                select(Lead).where(
                    Lead.workspace_id == search.workspace_id,
                    Lead.place_id == mapped["place_id"],
                )
            )
            lead_id = existing.id if existing else None
            if not lead_id:
                lead = Lead(workspace_id=search.workspace_id, **mapped)
                self.db.add(lead)
                self.db.flush()
                lead_id = lead.id
                log_event("lead_created", lead_id=lead_id, search_id=search.id,
                          place_id=mapped["place_id"], matched=matches)
            if matches:
                key = (search.id, lead_id)
                if key not in seen_link:
                    seen_link.add(key)
                    self.db.add(SearchLead(search_id=search.id, lead_id=lead_id,
                                           matched=True, created_at=utcnow()))
                qualified.append(mapped)
                state.setdefault("lead_ids", []).append(lead_id)
            if (idx + 1) % 10 == 0 or idx == len(mapped_all) - 1:
                self.jobs.progress(job, f"Filtering… {len(qualified)} qualified", idx + 1, len(mapped_all))
                self.db.commit()

        search.results_total = len(mapped_all)
        search.results_qualified = len(qualified)
        self.db.add(search)
        self.jobs.progress(job, f"{len(qualified)} leads qualified", len(mapped_all), len(mapped_all))
        self.jobs.complete(job)
        self.db.commit()
        log_event("leads_qualified", search_id=search.id, qualified=len(qualified))

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
            cached = service.reusable_audit(lead)
            if cached is not None:
                crawls_done += 1
                analysis_done += 1
                self.jobs.progress(crawl_job, "Using cached website data…", crawls_done, len(leads))
                self.jobs.progress(analysis_job, "Audit up to date (reused).", analysis_done, len(leads))
                continue
            try:
                pages = service.crawl_lead(lead)
                crawls_done += 1
                state.setdefault("pages_by_lead", {})[lead.id] = pages
                self.jobs.progress(
                    crawl_job,
                    f"Crawling {lead.business_name[:40]}… {len(pages)} páginas",
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
                    job, f"Scoring leads… {idx + 1} / {len(leads)}", idx + 1, len(leads)
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


def _search_places_sync(search: Search):
    """Small synchronous wrapper around the async provider search."""
    import asyncio

    return asyncio.run(search_places(search.query, search.max_results))
