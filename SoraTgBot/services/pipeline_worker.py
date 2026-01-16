from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiogram import Bot
from aiogram.types import FSInputFile

from core.models import GenerationStatus, Product, SubTask, Task, TaskStatus
from services.app_settings import AppSettingsService, RuntimeSettings
from services.neuroapi_client import NeuroAPIClient
from services.sora_client import SoraClient
from services.sora_processor import SoraJobService
from services.user_config import UserConfigService
from services.task_exporter import TaskExporter
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RetryPolicy:
    attempts: int
    base_delay: float
    backoff_factor: float = 2.0


class PipelineWorker:
    """Background worker that executes the GPT → Sora pipeline."""

    def __init__(
        self,
        task_manager: TaskManager,
        bot: Bot,
        settings_service: AppSettingsService,
        task_exporter: TaskExporter,
        user_config_service: UserConfigService,
    ) -> None:
        self.task_manager = task_manager
        self.bot = bot
        self.settings_service = settings_service
        self.task_exporter = task_exporter
        self.user_config_service = user_config_service
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._runner: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self.script_retry_policy = RetryPolicy(attempts=3, base_delay=5.0, backoff_factor=1.5)
        self.video_retry_policy = RetryPolicy(attempts=4, base_delay=10.0, backoff_factor=2.0)
        self.poll_interval = 5.0
        self.max_poll_attempts = 360  # ~30 minutes by default
        self._stage_marks: set[str] = set()

    def start(self) -> None:
        if self._runner is None:
            self._runner = asyncio.create_task(self._run(), name="pipeline-worker")

    async def stop(self) -> None:
        self._stop.set()
        if self._runner:
            await self._runner

    async def enqueue(self, task_id: str) -> None:
        await self.task_manager.register_worker_task(task_id)
        self._queue.put_nowait(task_id)

    async def _run(self) -> None:
        await self._enqueue_existing_tasks()
        while not self._stop.is_set():
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                await self.task_manager.mark_worker_task_running(task_id)
                completed = await self._process(task_id)
            except Exception:
                logger.exception("Pipeline failed for task %s", task_id)
                # Requeue the task for another attempt.
                await self.task_manager.register_worker_task(task_id)
                self._queue.put_nowait(task_id)
            else:
                if completed:
                    await self.task_manager.clear_worker_task(task_id)
                else:
                    await self.task_manager.register_worker_task(task_id)
                    self._queue.put_nowait(task_id)

    async def _enqueue_existing_tasks(self) -> None:
        task_ids = await self.task_manager.list_worker_queue(include_in_progress=True)
        if not task_ids:
            task_ids = await self.task_manager.list_active_task_ids()
            for task_id in task_ids:
                await self.task_manager.register_worker_task(task_id)
        for task_id in task_ids:
            self._queue.put_nowait(task_id)

    async def _process(self, task_id: str) -> bool:
        task = await self.task_manager.load_task(task_id)
        if task is None:
            logger.warning("Task %s not found; skipping", task_id)
            return True

        if task.status is TaskStatus.CANCELLED:
            logger.info("Task %s cancelled before processing; skipping", task.id)
            await self.task_manager.clear_worker_task(task.id)
            return True

        owner_id = task.owner_user_id
        if owner_id:
            await self.bot.send_message(owner_id, f"Задача {task.id} отправлена в обработку.")
        await self.task_manager.record_event(task.id, "task_processing_started", "Задача передана воркеру.")
        await self.task_manager.update_task_status(task.id, TaskStatus.PROCESSING)

        runtime_settings = await self.settings_service.get_runtime_settings()
        neuro_cfg = await self.user_config_service.get_neuro_config(owner_id)
        sora_cfg = await self.user_config_service.get_sora_config(owner_id)
        neuro_client = NeuroAPIClient(
            api_key=neuro_cfg.api_key,
            base_url=neuro_cfg.base_url,
            model=neuro_cfg.model,
        )
        sora_client = SoraClient(
            api_key=sora_cfg.api_key,
            base_url=sora_cfg.base_url,
            model=sora_cfg.model,
        )
        job_service = SoraJobService(self.task_manager, sora_client)

        for index, subtask in enumerate(list(task.subtasks)):
            fresh_task = await self.task_manager.load_task(task_id)
            if fresh_task is None:
                break
            current_subtask = next((st for st in fresh_task.subtasks if st.id == subtask.id), subtask)
            await self._process_subtask(
                fresh_task,
                current_subtask,
                index,
                neuro_client,
                sora_client,
                job_service,
                runtime_settings,
            )

        progress = await self.task_manager.get_task_progress(task.id)
        pending = progress["total"] - progress["done"] - progress["failed"] - progress.get("cancelled", 0)
        if pending > 0:
            logger.info("Task %s still has %s pending subtasks, re-enqueueing", task.id, pending)
            await self.task_manager.register_worker_task(task.id)
            self._queue.put_nowait(task.id)
            return False
        has_failures = progress["failed"] > 0
        final_status = TaskStatus.COMPLETED if not has_failures else TaskStatus.FAILED
        if progress.get("cancelled", 0) and not has_failures and progress["done"] < progress["total"]:
            final_status = TaskStatus.CANCELLED
        await self.task_manager.update_task_status(task.id, final_status)
        final_task = await self.task_manager.load_task(task.id) or task
        archive_path = await self.task_exporter.ensure_archive(final_task)
        done = progress["done"]
        failed = progress["failed"]
        cancelled = progress.get("cancelled", 0)
        if owner_id:
            if final_status is TaskStatus.COMPLETED:
                status_text = f"Задача {task.id} завершена: {done}/{progress['total']} готово."
            elif final_status is TaskStatus.CANCELLED:
                status_text = f"Задача {task.id} отменена. Выполнено {done}, отменено {cancelled}."
            else:
                status_text = (
                    f"Задача {task.id} завершена с ошибками: "
                    f"{done}/{progress['total']} готово, {failed} ошибок, {cancelled} отменено."
                )
            await self.bot.send_message(owner_id, status_text)
            await self._send_archive(owner_id, final_task, archive_path)
        await self.task_manager.record_event(
            task.id,
            f"task_{final_status.value}",
            f"Итог: готово {done}/{progress['total']}, ошибок {failed}, отменено {cancelled}.",
        )
        await self.task_manager.record_event(
            task.id,
            "task_archive_ready",
            f"Архив подготовлен: {archive_path.name}",
        )
        self._reset_stage_marks(task.id)
        return True

    async def _process_subtask(
        self,
        task: Task,
        subtask: SubTask,
        subtask_index: int,
        neuro_client: NeuroAPIClient,
        sora_client: SoraClient,
        job_service: SoraJobService,
        runtime_settings: RuntimeSettings,
    ) -> None:
        context = "task=%s subtask=%s" % (task.id, subtask.id)
        if subtask.status in {GenerationStatus.DONE, GenerationStatus.FAILED, GenerationStatus.CANCELLED}:
            logger.info("%s already finished (%s), skipping", context, subtask.status.value)
            return
        if subtask.job_id and subtask.status in {
            GenerationStatus.VIDEO_GENERATING,
            GenerationStatus.SCRIPT_GENERATING,
        }:
            logger.info("%s resuming polling for Sora job %s", context, subtask.job_id)
            await self._notify_stage(task, "video", "Видео генерируются в Sora…")
            await self._wait_for_sora_job(task, subtask, subtask_index, sora_client, job_service)
            return

        script_text = subtask.script_text
        if not script_text:
            await self.task_manager.update_subtask(
                task.id,
                subtask.id,
                status=GenerationStatus.SCRIPT_GENERATING,
            )
            await self._notify_stage(task, "script", "Сценарии генерируются…")
            try:
                script_text = await self._execute_with_retry(
                    stage="script",
                    task=task,
                    subtask=subtask,
                    func=lambda: neuro_client.generate_script(subtask.product, subtask.idea),
                    policy=self.script_retry_policy,
                )
            except Exception:
                logger.exception("Failed to generate script (%s)", context)
                await self.task_manager.update_subtask(
                    task.id,
                    subtask.id,
                    status=GenerationStatus.FAILED,
                )
                await self.task_manager.record_event(
                    task.id,
                    "subtask_script_failed",
                    f"{self._subtask_label(subtask)}: ошибка генерации сценария.",
                )
                await self._notify_progress(task)
                return
            await self.task_manager.update_subtask(
                task.id,
                subtask.id,
                script_text=script_text,
                last_error=None,
            )
            subtask.script_text = script_text
        else:
            logger.info("%s reusing cached script", context)

        if subtask.job_id:
            await self._notify_stage(task, "video", "Видео генерируются в Sora…")
            await self._wait_for_sora_job(task, subtask, subtask_index, sora_client, job_service)
            return

        try:
            image_url = await self._build_image_url(subtask.product)
            response = await self._execute_with_retry(
                stage="video",
                task=task,
                subtask=subtask,
                func=lambda: sora_client.generate_video(
                    storyboard=script_text,
                    image_url=image_url,
                    aspect_ratio=runtime_settings.sora_aspect_ratio,
                    n_frames=runtime_settings.sora_n_frames,
                    remove_watermark=runtime_settings.sora_remove_watermark,
                ),
                policy=self.video_retry_policy,
            )
            job_payload = response.get("data") or {}
            job_id = job_payload.get("taskId")
            record_id = job_payload.get("recordId")
            if not job_id:
                raise RuntimeError("Sora API did not return taskId")
        except Exception:
            logger.exception("Failed to submit Sora job for subtask %s", subtask.id)
            await self.task_manager.update_subtask(
                task.id,
                subtask.id,
                status=GenerationStatus.FAILED,
                last_error="Sora job submission failed",
            )
            await self.task_manager.record_event(
                task.id,
                "subtask_video_failed",
                f"{self._subtask_label(subtask)}: ошибка отправки задачи в Sora.",
            )
            await self._notify_progress(task)
            return

        await self.task_manager.update_subtask(
            task.id,
            subtask.id,
            status=GenerationStatus.VIDEO_GENERATING,
            job_id=job_id,
            record_id=record_id,
            result_payload=response,
            last_error=None,
        )
        await self._notify_stage(task, "video", "Видео генерируются в Sora…")

        subtask.job_id = job_id
        subtask.record_id = record_id
        await self._wait_for_sora_job(task, subtask, subtask_index, sora_client, job_service)

    async def _wait_for_sora_job(
        self,
        task: Task,
        subtask: SubTask,
        subtask_index: int,
        sora_client: SoraClient,
        job_service: SoraJobService,
    ) -> None:
        context = "task=%s subtask=%s job=%s" % (task.id, subtask.id, subtask.job_id)
        for attempt in range(self.max_poll_attempts):
            try:
                logger.debug("Polling Sora job (%s) attempt %s", context, attempt + 1)
                response = await sora_client.get_task_details(subtask.job_id, subtask.record_id)
            except Exception as exc:
                logger.warning("Polling Sora job failed (%s): %s", context, exc)
                await asyncio.sleep(self.poll_interval)
                continue

            data = response.get("data") or {}
            state = (data.get("state") or "").lower()
            if state == "success":
                await job_service.sync_subtask(
                    await self.task_manager.load_task(task.id) or task,
                    subtask,
                    subtask_index,
                )
                await self._send_videos(task, subtask)
                await self._notify_progress(task)
                await self.task_manager.record_event(
                    task.id,
                    "subtask_completed",
                    f"{self._subtask_label(subtask)}: видео готово.",
                )
                return
            if state == "fail":
                await self.task_manager.update_subtask(
                    task.id,
                    subtask.id,
                    status=GenerationStatus.FAILED,
                    last_error=data.get("failMsg") or "Sora job failed",
                )
                await self.task_manager.record_event(
                    task.id,
                    "subtask_failed",
                    f"{self._subtask_label(subtask)}: Sora вернула ошибку.",
                )
                await self._notify_progress(task)
                return
            await asyncio.sleep(self.poll_interval)

        await self.task_manager.update_subtask(
            task.id,
            subtask.id,
            status=GenerationStatus.FAILED,
            last_error="Timeout while waiting for Sora job",
        )
        await self.task_manager.record_event(
            task.id,
            "subtask_failed",
            f"{self._subtask_label(subtask)}: не удалось дождаться ответа от Sora.",
        )
        await self._notify_progress(task)

    async def _send_videos(self, task: Task, subtask: SubTask) -> None:
        updated_task = await self.task_manager.load_task(task.id) or task
        updated_subtask = next((st for st in updated_task.subtasks if st.id == subtask.id), subtask)
        owner_id = updated_task.owner_user_id
        if not owner_id:
            return
        for path_str in updated_subtask.downloaded_files:
            path = Path(path_str)
            if not path.exists():
                continue
            caption = (
                f"Task {task.id}\n"
                f"Product: {subtask.product.title}\n"
                f"Idea: {subtask.idea.text}"
            )
            try:
                await self.bot.send_video(owner_id, FSInputFile(path, filename=path.name), caption=caption)
            except Exception:
                logger.exception("Failed to send video %s", path)

    async def _build_image_url(self, product: Product) -> str:
        if product.image_file_id:
            file = await self.bot.get_file(product.image_file_id)
            return f"https://api.telegram.org/file/bot{self.bot.token}/{file.file_path}"
        raise RuntimeError("Product does not have an attached Telegram image.")

    async def _notify_progress(self, task: Task) -> None:
        progress = await self.task_manager.get_task_progress(task.id)
        owner_id = task.owner_user_id
        if owner_id:
            await self.bot.send_message(
                owner_id,
                f"Задача {task.id}: готово {progress['done']}/{progress['total']}, "
                f"ошибок {progress['failed']}, отменено {progress.get('cancelled', 0)}",
            )

    async def _send_archive(self, owner_id: int | str, task: Task, archive_path: Path) -> None:
        if not archive_path.exists():
            return
        caption = (
            f"Архив задачи {task.id}. Можно запросить позже командой /download_task {task.id}."
        )
        try:
            await self.bot.send_document(
                owner_id,
                FSInputFile(archive_path, filename=archive_path.name),
                caption=caption,
            )
            await self.task_manager.record_event(
                task.id,
                "task_archive_sent",
                "Архив отправлен пользователю.",
            )
        except Exception:
            logger.exception("Failed to send archive %s", archive_path)
            await self.bot.send_message(
                owner_id,
                f"Архив задачи {task.id} готов: {archive_path}. Скачайте вручную или введите /download_task {task.id}.",
            )

    async def _notify_stage(self, task: Task, stage: str, text: str) -> None:
        owner_id = task.owner_user_id
        key = f"{task.id}:{stage}"
        if key in self._stage_marks:
            return
        self._stage_marks.add(key)
        if owner_id:
            await self.bot.send_message(owner_id, f"Задача {task.id}: {text}")
        await self.task_manager.record_event(task.id, f"stage_{stage}", text)

    def _reset_stage_marks(self, task_id: str) -> None:
        prefix = f"{task_id}:"
        old_marks = self._stage_marks
        self._stage_marks = {mark for mark in old_marks if not mark.startswith(prefix)}

    async def _execute_with_retry(
        self,
        *,
        stage: str,
        task: Task,
        subtask: SubTask,
        func: Callable[[], Awaitable[Any]],
        policy: RetryPolicy,
    ) -> Any:
        delay = policy.base_delay
        for attempt in range(1, policy.attempts + 1):
            try:
                logger.info(
                    "%s stage attempt %s/%s (task=%s subtask=%s)",
                    stage,
                    attempt,
                    policy.attempts,
                    task.id,
                    subtask.id,
                )
                result = await func()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "%s stage failed (task=%s subtask=%s attempt=%s/%s): %s",
                    stage,
                    task.id,
                    subtask.id,
                    attempt,
                    policy.attempts,
                    exc,
                )
                await self.task_manager.update_subtask(
                    task.id,
                    subtask.id,
                    last_error=str(exc)[:500],
                    **self._attempts_kwargs(stage, attempt),
                )
                if attempt >= policy.attempts:
                    raise
                await asyncio.sleep(delay)
                delay *= policy.backoff_factor
            else:
                await self.task_manager.update_subtask(
                    task.id,
                    subtask.id,
                    last_error=None,
                    **self._attempts_kwargs(stage, attempt),
                )
                return result
        raise RuntimeError("Retry loop exited unexpectedly")

    @staticmethod
    def _attempts_kwargs(stage: str, attempt: int) -> dict[str, int]:
        if stage == "script":
            return {"script_attempts": attempt}
        if stage == "video":
            return {"video_attempts": attempt}
        return {}

    @staticmethod
    def _subtask_label(subtask: SubTask) -> str:
        return f"{subtask.product.title} × «{subtask.idea.text}»"
