from __future__ import annotations

from app.workers import jobs
from app.workers.scheduler import get_scheduler


def enqueue_sync_job(topic: str, limit: int) -> None:
    """Enqueue job for syncing Threads posts."""

    scheduler = get_scheduler()
    scheduler.enqueue(jobs.sync_threads_top, topic, limit)


def enqueue_publish_job(draft_id: int | None = None) -> None:
    """Enqueue publishing job (single draft or batch)."""

    scheduler = get_scheduler()
    if draft_id is not None:
        scheduler.enqueue(jobs.publish_draft, draft_id)
    else:
        scheduler.enqueue(jobs.publish_approved_posts)
