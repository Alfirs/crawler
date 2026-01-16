from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from core.models import Task
from services.task_manager import TaskManager


class TaskExporter:
    """Generates metadata and archives for completed tasks."""

    def __init__(self, task_manager: TaskManager) -> None:
        self.task_manager = task_manager

    def _metadata_path(self, task_id: str) -> Path:
        task_dir = self.task_manager.get_task_dir(task_id)
        return task_dir / "metadata.json"

    def _archive_path(self, task_id: str) -> Path:
        task_dir = self.task_manager.get_task_dir(task_id)
        return task_dir / f"{task_id}.zip"

    async def ensure_metadata(self, task: Task) -> Path:
        metadata = await self._build_metadata(task)
        path = self._metadata_path(task.id)
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    async def ensure_archive(self, task: Task) -> Path:
        metadata_path = await self.ensure_metadata(task)
        archive_path = self._archive_path(task.id)
        files = self._collect_files(task)
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zip_file:
            zip_file.write(metadata_path, arcname=metadata_path.name)
            for file_path in files:
                if file_path.exists():
                    zip_file.write(file_path, arcname=file_path.name)
        return archive_path

    async def _build_metadata(self, task: Task) -> dict:
        progress = await self.task_manager.get_task_progress(task.id)
        subtasks_meta: list[dict] = []
        for subtask in task.subtasks:
            subtasks_meta.append(
                {
                    "id": subtask.id,
                    "status": subtask.status.value,
                    "product": {
                        "id": subtask.product.id,
                        "title": subtask.product.title,
                        "description": subtask.product.short_description,
                        "image_path": str(subtask.product.image_path) if subtask.product.image_path else None,
                        "image_file_id": subtask.product.image_file_id,
                    },
                    "idea": subtask.idea.text,
                    "job_id": subtask.job_id,
                    "record_id": subtask.record_id,
                    "result_urls": subtask.result_urls,
                    "downloaded_files": subtask.downloaded_files,
                }
            )

        return {
            "task_id": task.id,
            "owner_user_id": task.owner_user_id,
            "status": task.status.value,
            "created_at": task.created_at.astimezone(timezone.utc).isoformat(),
            "updated_at": task.updated_at.astimezone(timezone.utc).isoformat(),
            "progress": progress,
            "subtasks": subtasks_meta,
        }

    def _collect_files(self, task: Task) -> list[Path]:
        files: list[Path] = []
        for subtask in task.subtasks:
            for file_str in subtask.downloaded_files:
                path = Path(file_str)
                if path.exists():
                    files.append(path)
        return files
