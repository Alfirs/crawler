from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from core.models import GenerationStatus, SubTask, Task
from services.sora_client import SoraClient
from services.task_manager import TaskManager


class SoraJobService:
    """Utility that syncs Kie.ai Sora jobs with local metadata and files."""

    def __init__(self, task_manager: TaskManager, sora_client: SoraClient) -> None:
        self.task_manager = task_manager
        self.sora_client = sora_client

    async def sync_subtask(
        self,
        task: Task,
        subtask: SubTask,
        subtask_index: int,
    ) -> dict[str, Any]:
        if not subtask.job_id:
            return {"state": "no_job", "downloaded": []}

        try:
            response = await self.sora_client.get_task_details(subtask.job_id, subtask.record_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await self.task_manager.update_subtask(
                    task.id,
                    subtask.id,
                    status=GenerationStatus.FAILED,
                    last_error="Sora job not found (404)",
                )
                return {"state": "fail", "downloaded": []}
            raise

        if response.get("code") != 200:
            raise RuntimeError(response.get("message") or response.get("msg") or "Sora API returned an error.")

        data = response.get("data") or {}
        state = (data.get("state") or "").lower()
        if state == "success":
            result_urls = self._extract_result_urls(data)
            all_paths, new_paths = await self._download_results(
                task.id,
                subtask_index,
                result_urls,
                subtask.downloaded_files,
            )
            await self.task_manager.update_subtask(
                task.id,
                subtask.id,
                status=GenerationStatus.DONE,
                result_payload=data,
                downloaded_files=[str(path) for path in all_paths],
                last_error=None,
            )
            return {"state": "success", "downloaded": new_paths, "result_urls": result_urls}

        if state == "fail":
            await self.task_manager.update_subtask(
                task.id,
                subtask.id,
                status=GenerationStatus.FAILED,
                last_error=data.get("failMsg") or response.get("message") or "Sora job failed",
            )
            return {"state": "fail", "downloaded": []}

        await self.task_manager.update_subtask(
            task.id,
            subtask.id,
            status=GenerationStatus.VIDEO_GENERATING,
            last_error=None,
        )
        return {"state": state or "pending", "downloaded": []}

    def _extract_result_urls(self, data: dict[str, Any]) -> list[str]:
        """
        Kie.ai returns result URLs either as JSON string in resultUrls or nested resultJson.
        """
        sources = []
        result_urls_field = data.get("resultUrls")
        if isinstance(result_urls_field, str):
            sources.append(result_urls_field)
        result_json = data.get("resultJson")
        if isinstance(result_json, str):
            sources.append(result_json)

        for raw in sources:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                urls = parsed.get("resultUrls")
                if isinstance(urls, list):
                    return [str(url) for url in urls if isinstance(url, str)]
            if isinstance(parsed, list):
                return [str(url) for url in parsed if isinstance(url, str)]
        return []

    async def _download_results(
        self,
        task_id: str,
        subtask_index: int,
        result_urls: list[str],
        existing_files: list[str] | None,
    ) -> tuple[list[Path], list[Path]]:
        if not result_urls:
            return ([], [])

        task_dir = self.task_manager.get_task_dir(task_id)
        all_paths: list[Path] = []
        new_paths: list[Path] = []
        existing_set = {Path(path) for path in existing_files or []}

        for idx, url in enumerate(result_urls, start=1):
            target_path = self._build_target_path(task_dir, subtask_index, idx, url)
            all_paths.append(target_path)
            if target_path.exists() or target_path in existing_set:
                continue
            await self.sora_client.download_file(url, target_path)
            new_paths.append(target_path)

        return all_paths, new_paths

    def _build_target_path(
        self,
        task_dir: Path,
        subtask_index: int,
        result_index: int,
        url: str,
    ) -> Path:
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix or ".mp4"
        filename = f"video_{subtask_index + 1}_{result_index}{suffix}"
        return task_dir / filename
