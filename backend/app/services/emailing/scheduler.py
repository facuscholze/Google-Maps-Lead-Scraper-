"""Inline email-queue scheduler (BUG-09 fix).

In `inline` execution mode there is no Celery beat, so due emails would sit
QUEUED forever unless someone drains manually. This asyncio task — started
from the FastAPI lifespan — drains every workspace's queue every
``queue_scheduler_interval_seconds``.

In `celery` mode the worker runs with ``celery worker -B`` and this task is
NOT started (single drainer, no double sends).

The scheduler is deliberately thin: all send rules (quota, working hours,
random delays, DNC) stay inside ``EmailQueueService``.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import log_event
from app.models.user import Workspace
from app.services.emailing.queue import EmailQueueService

logger = logging.getLogger("avascho.scheduler")


def drain_once() -> dict[int, int]:
    """One drain pass over all workspaces. Returns {workspace_id: sent}."""
    sent: dict[int, int] = {}
    with SessionLocal() as db:
        ws_ids = list(db.scalars(select(Workspace.id)).all())
    for ws_id in ws_ids:
        try:
            with SessionLocal() as db:
                n = EmailQueueService(db).send_due(ws_id)
                db.commit()
                if n:
                    sent[ws_id] = n
                    log_event("queue_drained", workspace_id=ws_id, sent=n)
        except Exception as exc:  # noqa: BLE001
            logger.exception("queue drain failed for workspace %s: %s", ws_id, exc)
    return sent


async def queue_scheduler_loop() -> None:
    interval = max(5, settings.queue_scheduler_interval_seconds)
    log_event("queue_scheduler_started", interval=interval, mode=settings.execution_mode)
    while True:
        try:
            await asyncio.to_thread(drain_once)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("queue scheduler tick failed: %s", exc)
        await asyncio.sleep(interval)
