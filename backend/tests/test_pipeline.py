"""Pipeline integration tests: search → filters → crawler → audit → scoring."""
from sqlalchemy import func, select

from app.core.enums import SearchStatus
from app.core.seed import seed_demo
from app.models.emailing import Email, EmailAccount, EmailEvent, Proposal, SuppressionEntry
from app.models.jobs import Job
from app.models.lead import Lead
from app.models.search import Search, SearchLead, SearchPreset
from app.models.website import WebsiteAudit, WebsitePage
from app.services.pipeline import SearchPipeline

TABLES = (
    EmailEvent, Email, EmailAccount, Proposal, SuppressionEntry,
    WebsitePage, WebsiteAudit, Job, SearchLead, Lead, Search, SearchPreset,
)


def wipe_domain(db_session) -> None:
    for model in TABLES:
        db_session.execute(model.__table__.delete())
    db_session.commit()


def _make_search(db, workspace, **overrides) -> Search:
    params = dict(
        workspace_id=workspace.id,
        query="Clínicas estéticas, Montevideo, Uruguay",
        category="Clínicas estéticas",
        location="Montevideo, Uruguay",
        min_reviews=50,
        max_reviews=500,
        min_rating=4.0,
        max_results=40,
        try_find_email=True,
    )
    params.update(overrides)
    search = Search(**params)
    db.add(search)
    db.commit()
    return search


def test_full_pipeline(db_session, workspace):
    wipe_domain(db_session)
    seed_demo(db_session)
    search = _make_search(db_session, workspace, max_results=40)
    SearchPipeline(db_session).run(search.id)

    db_session.refresh(search)
    assert search.status == SearchStatus.COMPLETED.value
    assert search.results_total == 40
    assert 0 < search.results_qualified <= 40
    assert search.websites_analyzed >= 1
    assert search.emails_found >= 1
    assert search.hot_count + search.warm_count + search.cold_count == search.results_qualified

    # every qualified lead has audit + score
    qualified_ids = db_session.scalars(
        select(SearchLead.lead_id).where(SearchLead.search_id == search.id)
    ).all()
    leads = db_session.scalars(select(Lead).where(Lead.id.in_(qualified_ids))).all()
    for lead in leads:
        assert lead.lead_score is not None
        assert lead.lead_temperature is not None
        if lead.website:
            audit = db_session.scalar(select(WebsiteAudit).where(WebsiteAudit.lead_id == lead.id))
            assert audit is not None
            assert audit.overall_score > 0


def test_deduplication_across_searches(db_session, workspace):
    wipe_domain(db_session)
    seed_demo(db_session)
    a = _make_search(db_session, workspace, max_results=30)
    b = _make_search(db_session, workspace, max_results=30)  # same seed → same places
    SearchPipeline(db_session).run(a.id)
    SearchPipeline(db_session).run(b.id)

    total_leads = db_session.scalar(select(func.count()).select_from(Lead)) or 0
    assert total_leads == 30  # reuse instead of duplicating (spec §14)


def test_filters_respected(db_session, workspace):
    wipe_domain(db_session)
    seed_demo(db_session)
    search = _make_search(db_session, workspace, max_results=100, only_with_phone=True, only_with_website=True)
    SearchPipeline(db_session).run(search.id)
    db_session.refresh(search)
    qualified_ids = db_session.scalars(
        select(SearchLead.lead_id).where(SearchLead.search_id == search.id)
    ).all()
    leads = db_session.scalars(select(Lead).where(Lead.id.in_(qualified_ids))).all()
    assert leads
    for lead in leads:
        assert lead.website is not None
        assert lead.phone or lead.international_phone


def test_website_cache_reuse(db_session, workspace):
    """Second run on the same data should reuse audits (no duplicate rows)."""
    wipe_domain(db_session)
    seed_demo(db_session)
    search = _make_search(db_session, workspace, max_results=15)
    SearchPipeline(db_session).run(search.id)
    audits_before = db_session.scalar(select(func.count()).select_from(WebsiteAudit))
    # run again: same leads already analyzed → reused
    SearchPipeline(db_session).run(search.id)
    audits_after = db_session.scalar(select(func.count()).select_from(WebsiteAudit))
    assert audits_before == audits_after
