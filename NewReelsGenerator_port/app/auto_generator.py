from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from .templates_manager.models import TemplateMetadata
from .templates_manager.service import TemplateService


class AutoGenerator:
    """Simple background scheduler that produces carousels for templates marked for auto-generation."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._worker(), name="carousel-auto-generator")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def trigger_template(self, template: TemplateMetadata, count: int = 5) -> None:
        async with self._lock:
            TemplateService.generate_batch_from_template(template, count=count)

    async def _worker(self) -> None:
        while self._running:
            try:
                await self._process_due_templates()
            except Exception:
                # We swallow exceptions to keep the scheduler alive; real logging can be added here.
                pass
            await asyncio.sleep(3600)  # check every hour

    async def _process_due_templates(self) -> None:
        templates = TemplateService.list_templates()
        if not templates:
            return

        for template in templates:
            if not TemplateService.needs_generation_today(template):
                continue
            async with self._lock:
                TemplateService.generate_batch_from_template(template, count=5)


auto_generator = AutoGenerator()

