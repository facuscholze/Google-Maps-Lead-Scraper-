"""Celery task implementations (spec §5, §46, §89).

Each task opens its own DB session. Only used when EXECUTION_MODE=celery.
"""
from __future__ import annotations

from app.core.logging import log_event
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_search_task", bind=True, max_retries=0)
def run_search_task(self, search_id: int) -> str:
    from app.core.database import SessionLocal
    from app.services.pipeline import SearchPipeline

    db = SessionLocal()
    try:
        SearchPipeline(db).run(search_id)
        return f"search {search_id} done"
    except Exception as exc:  # noqa: BLE001
        log_event("search_task_failed", search_id=search_id, error=str(exc)[:500])
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.process_email_queue")
def process_email_queue() -> int:
    """Send due emails for every workspace (scheduler beat task)."""
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.user import Workspace
    from app.services.emailing.queue import EmailQueueService

    total = 0
    db = SessionLocal()
    try:
        workspace_ids = db.scalars(select(Workspace.id)).all()
        for workspace_id in workspace_ids:
            total += EmailQueueService(db).send_due(workspace_id)
    finally:
        db.close()
    return total
