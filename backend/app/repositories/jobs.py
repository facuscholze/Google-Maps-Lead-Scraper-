"""Job repository with progress updates."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.core.enums import JobStatus, JobType
from app.models.jobs import Job
from app.repositories.base import BaseRepository
from app.utils.text import utcnow


class JobRepository(BaseRepository[Job]):
    model = Job

    def create_job(
        self,
        workspace_id: int,
        job_type: JobType | str,
        search_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Job:
        return self.create(
            workspace_id=workspace_id,
            search_id=search_id,
            job_type=job_type.value if isinstance(job_type, JobType) else job_type,
            status=JobStatus.RUNNING.value,
            started_at=utcnow(),
            payload=payload or {},
        )

    def progress(
        self,
        job: Job,
        current_step: str,
        done: int | None = None,
        total: int | None = None,
        progress_pct: int | None = None,
    ) -> None:
        job.current_step = current_step
        if done is not None:
            job.done = done
        if total is not None:
            job.total = total
        if progress_pct is not None:
            job.progress = progress_pct
        elif job.total > 0:
            job.progress = min(99, round(job.done * 100 / job.total))
        self.db.add(job)
        self.db.flush()

    def complete(self, job: Job) -> None:
        job.status = JobStatus.COMPLETED.value
        job.progress = 100
        job.completed_at = utcnow()
        self.db.add(job)
        self.db.flush()

    def fail(self, job: Job, error: str) -> None:
        job.status = JobStatus.FAILED.value
        job.error_message = error[:2000]
        job.completed_at = utcnow()
        self.db.add(job)
        self.db.flush()

    def list_for_workspace(
        self, workspace_id: int, search_id: int | None = None, limit: int = 100
    ) -> list[Job]:
        stmt = select(Job).where(Job.workspace_id == workspace_id)
        if search_id is not None:
            stmt = stmt.where(Job.search_id == search_id)
        stmt = stmt.order_by(Job.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def running_count(self, workspace_id: int) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.workspace_id == workspace_id,
                    Job.status == JobStatus.RUNNING.value,
                )
            )
            or 0
        )
