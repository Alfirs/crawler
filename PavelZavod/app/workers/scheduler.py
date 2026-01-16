from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any

from app.config import get_settings
from app.workers import jobs

JobCallable = Callable[..., None]


class JobScheduler:
    """Simple asyncio-based job manager for ad-hoc and periodic tasks."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[tuple[JobCallable, tuple[Any, ...], dict[str, Any]]] = (
            asyncio.Queue()
        )
        self._runner: asyncio.Task | None = None
        self._periodic_tasks: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._runner = asyncio.create_task(self._worker())
        settings = get_settings()
        self._periodic_tasks = [
            asyncio.create_task(
                self._run_periodic(
                    jobs.sync_threads_top,
                    settings.sync_interval_seconds,
                    settings.threads_topics[0] if settings.threads_topics else "ai",
                )
            ),
            asyncio.create_task(
                self._run_periodic(
                    jobs.publish_approved_posts,
                    settings.publish_interval_seconds,
                )
            ),
        ]

    async def stop(self) -> None:
        if not self._started:
            return
        if self._runner:
            self._runner.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._runner
        for task in self._periodic_tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._periodic_tasks.clear()
        self._started = False

    def enqueue(self, func: JobCallable, *args: Any, **kwargs: Any) -> None:
        """Schedule a job to run in the background."""

        self._queue.put_nowait((func, args, kwargs))

    async def _worker(self) -> None:
        while True:
            func, args, kwargs = await self._queue.get()
            try:
                await asyncio.to_thread(func, *args, **kwargs)
            finally:
                self._queue.task_done()

    async def _run_periodic(self, func: JobCallable, interval: int, *args: Any, **kwargs: Any) -> None:
        while True:
            self.enqueue(func, *args, **kwargs)
            await asyncio.sleep(interval)


_scheduler: JobScheduler | None = None


def get_scheduler() -> JobScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler
