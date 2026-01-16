from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from core.dto import ProductDraft
from core.models import GenerationStatus, Idea, Product, SubTask, Task, TaskStatus
from services.sqlite_storage import SQLiteStorage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskManager:
    """Co-ordinates task metadata (SQLite) and video storage (filesystem)."""

    def __init__(self, sqlite_storage: SQLiteStorage, tasks_root: str | Path | None = None) -> None:
        self.sqlite = sqlite_storage
        self.tasks_root = Path(tasks_root or Path("storage") / "tasks")
        self.tasks_root.mkdir(parents=True, exist_ok=True)

    def get_task_dir(self, task_id: str) -> Path:
        path = self.tasks_root / f"task_{task_id}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def create_task(
        self,
        products: Sequence[Product],
        ideas: Sequence[Idea],
        n_generations: int,
        owner_user_id: int | str | None = None,
    ) -> Task:
        task_id = uuid4().hex
        created_at = _utcnow()
        subtasks: list[SubTask] = []

        for product in products:
            for idea in ideas:
                for gen_index in range(max(1, n_generations)):
                    subtasks.append(
                        SubTask(
                            id=uuid4().hex,
                            product=product,
                            idea=idea,
                            n_generations=gen_index,
                            status=GenerationStatus.PENDING,
                        )
                    )

        task = Task(
            id=task_id,
            subtasks=subtasks,
            created_at=created_at,
            updated_at=created_at,
            owner_user_id=owner_user_id,
            status=TaskStatus.PENDING,
        )
        await self.sqlite.save_task(task)
        return task

    async def enqueue_task(self, task: Task) -> None:
        task.updated_at = _utcnow()
        task.status = TaskStatus.PENDING
        await self.sqlite.save_task(task)
        await self.sqlite.add_worker_task(task.id)

    async def create_task_from_drafts(
        self,
        drafts: Sequence[ProductDraft],
        ideas: Sequence[str] | None,
        generation_count: int,
        owner_user_id: int | str | None = None,
    ) -> Task:
        idea_texts = [idea.strip() for idea in (ideas or []) if idea.strip()]
        if not idea_texts:
            idea_texts = ["Общий сценарий"]
        generation_count = max(1, generation_count)

        products: list[Product] = []
        for index, draft in enumerate(drafts, start=1):
            title = (draft.description or f"Товар {index}").strip()
            products.append(
                Product(
                    id=uuid4().hex,
                    title=title[:80] or f"Product {index}",
                    short_description=draft.description,
                    image_path=draft.image_path,
                    image_file_id=draft.image_file_id,
                )
            )

        idea_models = [Idea(id=uuid4().hex, text=text) for text in idea_texts]
        return await self.create_task(
            products=products,
            ideas=idea_models,
            n_generations=generation_count,
            owner_user_id=owner_user_id,
        )

    async def load_task(self, task_id: str) -> Task | None:
        return await self.sqlite.load_task(task_id)

    async def update_subtask(
        self,
        task_id: str,
        subtask_id: str,
        *,
        status: GenerationStatus | None = None,
        job_id: str | None = None,
        record_id: str | None = None,
        result_payload: dict | None = None,
        downloaded_files: list[str] | None = None,
        script_text: str | None = None,
        last_error: str | None = None,
        script_attempts: int | None = None,
        video_attempts: int | None = None,
    ) -> None:
        await self.sqlite.update_subtask(
            task_id,
            subtask_id,
            status=status,
            job_id=job_id,
            record_id=record_id,
            result_payload=result_payload,
            downloaded_files=downloaded_files,
            script_text=script_text,
            last_error=last_error,
            script_attempts=script_attempts,
            video_attempts=video_attempts,
        )

    async def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        await self.sqlite.update_task_status(task_id, status)

    async def list_active_task_ids(self) -> list[str]:
        return await self.sqlite.list_active_task_ids()

    async def get_task_progress(self, task_id: str) -> dict[str, int]:
        return await self.sqlite.get_task_progress(task_id)

    async def register_worker_task(self, task_id: str) -> None:
        await self.sqlite.add_worker_task(task_id)

    async def mark_worker_task_running(self, task_id: str) -> None:
        await self.sqlite.update_worker_task_state(task_id, "in_progress")

    async def clear_worker_task(self, task_id: str) -> None:
        await self.sqlite.delete_worker_task(task_id)

    async def list_worker_queue(self, include_in_progress: bool = True) -> list[str]:
        states = ["pending"]
        if include_in_progress:
            states.append("in_progress")
        return await self.sqlite.list_worker_tasks(states)

    async def list_tasks_for_user(
        self,
        user_id: int | str,
        *,
        limit: int = 10,
        offset: int = 0,
    ):
        return await self.sqlite.list_tasks(user_id, limit, offset)

    async def record_event(self, task_id: str, event_type: str, message: str) -> None:
        await self.sqlite.add_task_event(task_id, event_type, message)

    async def get_task_events(
        self,
        task_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        return await self.sqlite.list_task_events(task_id, limit, offset)

    async def cancel_task(self, task_id: str) -> bool:
        task = await self.load_task(task_id)
        if task is None:
            return False
        for subtask in task.subtasks:
            if subtask.status not in {
                GenerationStatus.DONE,
                GenerationStatus.FAILED,
                GenerationStatus.CANCELLED,
            }:
                await self.update_subtask(
                    task.id,
                    subtask.id,
                    status=GenerationStatus.CANCELLED,
                )
        await self.update_task_status(task.id, TaskStatus.CANCELLED)
        await self.record_event(task.id, "task_cancelled", "Задача отменена пользователем.")
        await self.clear_worker_task(task.id)
        return True

    async def repeat_task(self, original_task_id: str, owner_user_id: int | str | None = None) -> Task | None:
        original = await self.load_task(original_task_id)
        if original is None:
            return None
        product_map: dict[tuple[str, str | None, str | None, str | None], Product] = {}
        idea_texts: list[str] = []
        combo_counts: dict[tuple[tuple[str, str | None, str | None, str | None], str], int] = {}

        for subtask in original.subtasks:
            product = subtask.product
            key = (
                product.title,
                product.short_description,
                str(product.image_path) if product.image_path else None,
                product.image_file_id,
            )
            if key not in product_map:
                product_map[key] = Product(
                    id=uuid4().hex,
                    title=product.title,
                    short_description=product.short_description,
                    image_path=product.image_path,
                    image_file_id=product.image_file_id,
                )
            idea_text = subtask.idea.text
            if idea_text not in idea_texts:
                idea_texts.append(idea_text)
            combo_key = (key, idea_text)
            combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1

        if not product_map or not idea_texts:
            return None

        generation_count = max(combo_counts.values(), default=1)
        new_task = await self.create_task(
            products=list(product_map.values()),
            ideas=[Idea(id=uuid4().hex, text=text) for text in idea_texts],
            n_generations=generation_count,
            owner_user_id=owner_user_id or original.owner_user_id,
        )
        await self.record_event(new_task.id, "task_repeated", f"Создана копия задачи {original_task_id}.")
        return new_task
