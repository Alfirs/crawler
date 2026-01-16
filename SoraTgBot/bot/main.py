from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Tuple

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import FSInputFile, Message

from bot.config import get_settings
from bot.handlers import settings_panel, user_tasks
from bot.keyboards import main_menu_keyboard
from core.models import GenerationStatus, Idea, Product
from services.app_settings import AppSettingsService
from services.neuroapi_client import NeuroAPIClient
from services.pipeline_worker import PipelineWorker
from services.sora_client import SoraClient
from services.sora_processor import SoraJobService
from services.task_exporter import TaskExporter
from services.task_manager import TaskManager
from services.sqlite_storage import SQLiteStorage
from services.session_storage import create_session_storage, UserSessionStorage
from services.user_config import UserConfigService
from services.user_settings import UserSettingsRepository

DEMO_IMAGE_URL = "https://file.aiquickdraw.com/custom-page/akr/section-images/17594315607644506ltpf.jpg"

router = Router(name=__name__)
_task_manager: TaskManager | None = None
_pipeline_worker: PipelineWorker | None = None
_sqlite_storage: SQLiteStorage | None = None
_session_storage: UserSessionStorage | None = None
_app_settings: AppSettingsService | None = None
_task_exporter: TaskExporter | None = None
_user_settings_repo: UserSettingsRepository | None = None
_user_config_service: UserConfigService | None = None


def get_task_manager() -> TaskManager:
    if _task_manager is None:
        raise RuntimeError("TaskManager is not initialized")
    return _task_manager


def get_app_settings_service() -> AppSettingsService:
    if _app_settings is None:
        raise RuntimeError("AppSettingsService is not initialized")
    return _app_settings


def get_task_exporter() -> TaskExporter:
    if _task_exporter is None:
        raise RuntimeError("TaskExporter is not initialized")
    return _task_exporter


def get_user_config_service() -> UserConfigService:
    if _user_config_service is None:
        raise RuntimeError("UserConfigService is not initialized")
    return _user_config_service


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    greeting = (
        "Привет! Я помогу собрать серию видео через SORA по твоим товарам. "
        "Загрузи фото, добавь описания и идеи роликов, затем запусти задачу — "
        "я сгенерирую сценарии через GPT и верну готовые видео."
    )
    await message.answer(greeting, reply_markup=main_menu_keyboard())


@router.message(Command("test_script"))
async def handle_test_script(message: Message) -> None:
    neuro_cfg = await get_user_config_service().get_neuro_config(message.from_user.id)
    client = NeuroAPIClient(
        api_key=neuro_cfg.api_key,
        base_url=neuro_cfg.base_url,
        model=neuro_cfg.model,
    )
    product = Product(
        id="demo-product",
        title="Demo Smart Bottle",
        short_description="Self-cleaning stainless bottle with LED temperature indicator.",
    )
    idea = Idea(id="demo-idea", text="Quick lifestyle showcase during morning routine.")
    try:
        script = await client.generate_script(product, idea)
    except Exception:
        logging.exception("Failed to generate script via NeuroAPI")
        await message.answer("Произошла ошибка при генерации сценария. Проверь API-ключ и попробуй ещё раз.")
        return

    await message.answer(f"Сценарий:\n{script}")


@router.message(Command("test_sora"))
async def handle_test_sora(message: Message) -> None:
    """Test end-to-end flow: GPT script + Sora task creation."""
    runtime_settings = await get_app_settings_service().get_runtime_settings()
    neuro_cfg = await get_user_config_service().get_neuro_config(message.from_user.id)
    sora_cfg = await get_user_config_service().get_sora_config(message.from_user.id)
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
    task_manager = get_task_manager()
    product = Product(
        id="demo-product",
        title="Demo Smart Bottle",
        short_description="Self-cleaning stainless bottle with LED temperature indicator.",
    )
    idea = Idea(id="demo-idea", text="Quick lifestyle showcase during morning routine.")

    task = await task_manager.create_task(
        products=[product],
        ideas=[idea],
        n_generations=1,
        owner_user_id=message.from_user.id,
    )
    await task_manager.enqueue_task(task)
    subtask = task.subtasks[0]

    try:
        storyboard = await neuro_client.generate_script(product, idea)
        await message.answer(f"Сценарий:\n{storyboard}")
        sora_response = await sora_client.generate_video(
            storyboard=storyboard,
            image_url=DEMO_IMAGE_URL,
            aspect_ratio=runtime_settings.sora_aspect_ratio,
            n_frames=runtime_settings.sora_n_frames,
            remove_watermark=runtime_settings.sora_remove_watermark,
        )
    except Exception:
        logging.exception("Failed to call Sora API")
        await message.answer("Произошла ошибка при обращении к Sora API. Проверь KIE_API_KEY и попробуй ещё раз.")
        return

    job_payload = sora_response.get("data") or {}
    job_id = job_payload.get("taskId")
    record_id = job_payload.get("recordId")
    if not job_id:
        await message.answer("Sora API вернул неожиданный ответ без taskId.")
        return

    await task_manager.update_subtask(
        task.id,
        subtask.id,
        status=GenerationStatus.VIDEO_GENERATING,
        job_id=job_id,
        record_id=record_id,
    )

    await message.answer(
        "Видео поставлено в очередь.\n"
        f"ID задачи в боте (используй его в /check_sora): {task.id}\n"
        f"Sora taskId: {job_id}\n\n"
        "Когда видео будет готово, вызови:\n"
        f"/check_sora {task.id}\n"
        "чтобы обновить статус и получить файлы."
    )


@router.message(Command("check_sora"))
async def handle_check_sora(message: Message, command: CommandObject) -> None:
    task_id = (command.args or "").strip()
    if not task_id:
        await message.answer("Укажи ID задачи: /check_sora <task_id>")
        return

    task_manager = get_task_manager()
    task = await task_manager.load_task(task_id)
    if task is None:
        await message.answer("Задача с таким ID не найдена.")
        return

    settings = get_settings()
    sora_client = SoraClient(
        api_key=settings.KIE_API_KEY,
        base_url=settings.KIE_API_BASE_URL,
    )
    job_service = SoraJobService(task_manager, sora_client)

    status_lines: List[str] = [f"Задача {task.id}:"]
    downloaded_files: List[Tuple[str, Path]] = []

    for index, subtask in enumerate(task.subtasks):
        if not subtask.job_id:
            status_lines.append(f"• Подзадача {index + 1}: job_id не задан.")
            continue
        try:
            result = await job_service.sync_subtask(task, subtask, index)
        except Exception:
            logging.exception("Failed to sync Sora job")
            status_lines.append(f"• Подзадача {index + 1}: ошибка при запросе статуса.")
            continue

        state = result.get("state", "unknown")
        status_lines.append(f"• Подзадача {index + 1}: {state}")
        for path in result.get("downloaded", []):
            downloaded_files.append((subtask.id, path))

    await message.answer("\n".join(status_lines))

    for subtask_id, path in downloaded_files:
        try:
            await message.answer_video(
                FSInputFile(path, filename=path.name),
                caption=f"Задача {task.id}, подзадача {subtask_id}",
            )
        except Exception:
            logging.exception("Failed to send video %s", path)
            await message.answer(f"Видео сохранено по пути: {path}")


async def main() -> None:
    global _task_manager, _pipeline_worker, _sqlite_storage, _session_storage
    global _app_settings, _task_exporter, _user_settings_repo, _user_config_service
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    _sqlite_storage = SQLiteStorage()
    await _sqlite_storage.init()
    _app_settings = AppSettingsService(_sqlite_storage, settings)
    _task_manager = TaskManager(_sqlite_storage)
    _task_exporter = TaskExporter(_task_manager)
    _user_settings_repo = UserSettingsRepository(_sqlite_storage)
    await _user_settings_repo.init()
    _user_config_service = UserConfigService(_user_settings_repo, settings)
    _session_storage = create_session_storage(_sqlite_storage, _app_settings)
    _pipeline_worker = PipelineWorker(
        _task_manager,
        bot,
        _app_settings,
        _task_exporter,
        _user_config_service,
    )
    _pipeline_worker.start()
    user_tasks.setup_handlers(_task_manager, _session_storage, _pipeline_worker, _task_exporter)
    settings_panel.setup_handlers(_user_settings_repo, _user_config_service)
    dp = Dispatcher()
    dp.include_router(user_tasks.router)
    dp.include_router(settings_panel.router)
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await _pipeline_worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
