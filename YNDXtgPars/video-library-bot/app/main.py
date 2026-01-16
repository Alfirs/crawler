from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramConflictError, TelegramRetryAfter, TelegramServerError
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    FSInputFile,
)
from aiogram.client.session.aiohttp import AiohttpSession

import httpx

from app.config import Settings
from app.db import db_session, init_db, utc_now_iso
from app.jobs.scan_job import ScanJob, scan_yandex_disk_and_update_db
from app.jobs.transcription_job import run_transcription_loop
from app.logging import setup_logging
from app.models import Fingerprint, SearchResponse, StorageEntry, VideoMeta, VideoStatus
from app.services.catalog_service import CatalogService
from app.services.fingerprint import build_fingerprint_payload
from app.services.index_service import IndexService
from app.services.seed_demo import seed_demo
from app.services.telegram_cache import TelegramCacheService
from app.services.yandex_disk_storage import YandexDiskStorage
from app.utils import (
    acquire_run_lock,
    join_disk_path,
    normalize_disk_path,
    release_run_lock,
    safe_filename,
    slugify,
)


router = Router()

# Global references (set during startup)
_settings: Optional[Settings] = None
_index_service: Optional[IndexService] = None
_catalog: Optional[CatalogService] = None
_storage: Optional[YandexDiskStorage] = None
_telegram_cache: Optional[TelegramCacheService] = None
_logger: Optional[logging.Logger] = None
_last_search_results: dict[int, SearchResponse] = {}
_last_scan_error: Optional[str] = None
_last_index_error: Optional[str] = None
_last_scan_time: Optional[str] = None
_last_index_time: Optional[str] = None
_last_error_time: Optional[str] = None
_last_request_at: dict[int, float] = {}
_last_scan_duration: Optional[str] = None
_last_index_duration: Optional[str] = None
_scan_lock = asyncio.Lock()
_index_lock = asyncio.Lock()
_download_semaphore = asyncio.Semaphore(2)


# --- Telegram Retry Helper ---
async def _telegram_retry_send(coro_func, *args, max_retries: int = 3, **kwargs):
    """Retry Telegram API calls on rate limit or server errors."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_func(*args, **kwargs)
        except TelegramRetryAfter as exc:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(exc.retry_after + 0.5)
            last_exc = exc
        except TelegramServerError as exc:
            if attempt >= max_retries:
                raise
            await asyncio.sleep(1.0 * attempt)
            last_exc = exc
    raise last_exc


# --- Callback Token Management ---
async def _create_callback_token(video_id: str) -> str:
    """Generate a short token and store video_id mapping in DB."""
    if _settings is None:
        raise RuntimeError("settings not initialized")
    token = secrets.token_urlsafe(8)  # 11 chars, fits in 64 byte limit
    async with db_session(_settings.db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO callback_tokens (token, video_id, created_at) VALUES (?, ?, ?)",
            (token, video_id, utc_now_iso()),
        )
        await db.commit()
    return token


async def _resolve_callback_token(token: str) -> str | None:
    """Lookup video_id by token. Returns None if not found."""
    if _settings is None:
        return None
    async with db_session(_settings.db_path) as db:
        cursor = await db.execute(
            "SELECT video_id FROM callback_tokens WHERE token = ?",
            (token,),
        )
        row = await cursor.fetchone()
        return row["video_id"] if row else None


async def _cleanup_old_tokens() -> int:
    """Delete tokens older than 24 hours. Returns count of deleted rows."""
    if _settings is None:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    async with db_session(_settings.db_path) as db:
        cursor = await db.execute(
            "DELETE FROM callback_tokens WHERE created_at < ?",
            (cutoff,),
        )
        await db.commit()
        return cursor.rowcount


def _is_admin(user_id: int) -> bool:
    if _settings is None:
        return False
    return user_id in _settings.admin_user_ids


class AddVideoStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_video = State()


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv"}


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    await message.answer(
        "Привет! Я бот видеотеки.\n\n"
        "Отправьте текстовый запрос, и я найду подходящие видео.\n\n"
        "Команды:\n"
        "/help - справка\n"
        "/admin_status - статус библиотеки (для админов)\n"
        "/health - готовность сервисов (для админов)\n"
        "/add_video - добавить видео (для админов)\n"
        "/selftest - проверка поиска (для админов)\n"
        "/seed_demo - демо-наполнение (для админов)"
    )


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(
        "Как пользоваться:\n"
        "1) Отправьте текстовый запрос, например: инструмент перо в фотошопе\n"
        "2) Я предложу лучшее видео и кнопки для отправки.\n\n"
        "Команды для админов:\n"
        "/admin_status - статистика библиотеки\n"
        "/health - готовность сервисов\n"
        "/reindex - переиндексировать все\n"
        "/reindex <video_id> - переиндексировать одно видео\n"
        "/add_video - загрузить видео в библиотеку\n"
        "/selftest - прогон тестовых запросов\n"
        "/seed_demo - создать демо-библиотеку и прогнать selftest"
    )


@router.message(Command("admin_status"))
async def admin_status_handler(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    if _catalog is None or _settings is None:
        await message.answer("Сервис не инициализирован.")
        return

    counts = await _catalog.get_status_counts()
    last_scan = await _get_last_scan_time(_settings)
    last_index = await _get_last_index_time(_settings)
    index_size = await _index_service.index_size() if _index_service else 0

    last_scan_error = _last_scan_error or "нет"
    last_index_error = _last_index_error or "нет"
    recent_errors = await _catalog.list_recent_errors(limit=5)

    status_text = _build_admin_status(
        counts=counts,
        index_size=index_size,
        last_scan=last_scan,
        last_index=last_index,
        last_error=_last_error_time or "нет",
        last_scan_duration=_last_scan_duration,
        last_index_duration=_last_index_duration,
        last_scan_error=last_scan_error,
        last_index_error=last_index_error,
        recent_errors=recent_errors,
    )
    await message.answer(status_text)


@router.message(Command("reindex"))
async def reindex_handler(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    if _index_service is None:
        await message.answer("Сервис индексации не инициализирован.")
        return

    args = message.text.split(maxsplit=1) if message.text else []
    if len(args) > 1:
        video_id = args[1].strip()
        await message.answer(f"Переиндексирую видео: {video_id}...")
        try:
            async with _index_lock:
                await _index_service.index_video(video_id)
            await message.answer(f"Видео {video_id} переиндексировано.")
        except Exception as exc:
            await message.answer(f"Ошибка: {exc}")
        return

    await message.answer("Запускаю полную переиндексацию...")
    try:
        async with _index_lock:
            await _index_service.build_or_update_index(force=True)
        index_size = await _index_service.index_size()
        await message.answer(f"Переиндексация завершена. Чанков: {index_size}")
    except Exception as exc:
        await message.answer(f"Ошибка переиндексации: {exc}")


@router.message(Command("health"))
async def health_handler(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    if _catalog is None or _settings is None:
        await message.answer("Сервис не инициализирован.")
        return
    report = await _build_health_report()
    await message.answer(report)


@router.message(Command("selftest"))
async def selftest_handler(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    await message.answer("Запускаю selftest...")
    report = await _run_selftest()
    await _send_long_message(message, report)


@router.message(Command("seed_demo"))
async def seed_demo_handler(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    if _settings is None or _storage is None:
        await message.answer("Сервис не инициализирован.")
        return
    await message.answer("Создаю демо-библиотеку...")
    result = await seed_demo(_storage, _settings, _logger)
    report = await _run_selftest()
    combined = f"seed_demo: {result}\n\n{report}"
    await _send_long_message(message, combined)


@router.message(Command("add_video"))
async def add_video_handler(message: Message, state: FSMContext) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только администраторам.")
        return
    await state.clear()
    await message.answer("Введите название видео (или /cancel для отмены).")
    await state.set_state(AddVideoStates.waiting_title)


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять.")
        return
    await state.clear()
    await message.answer("✅ Действие отменено.")


@router.message(AddVideoStates.waiting_title)
async def add_video_title_handler(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не должно быть пустым. Попробуйте еще раз.")
        return
    await state.update_data(title=title)
    await message.answer("Введите описание или отправьте /skip.")
    await state.set_state(AddVideoStates.waiting_description)


@router.message(AddVideoStates.waiting_description, Command("skip"))
async def add_video_skip_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description="")
    await message.answer("Пришлите видео файлом.")
    await state.set_state(AddVideoStates.waiting_video)


@router.message(AddVideoStates.waiting_description)
async def add_video_description_handler(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    await state.update_data(description=description)
    await message.answer("Пришлите видео файлом.")
    await state.set_state(AddVideoStates.waiting_video)


@router.message(AddVideoStates.waiting_video)
async def add_video_file_handler(message: Message, state: FSMContext) -> None:
    if _settings is None or _storage is None or _catalog is None or _index_service is None:
        await message.answer("Сервис не инициализирован.")
        await state.clear()
        return
    file_obj, filename = _extract_video_file(message)
    if file_obj is None:
        await message.answer("Пришлите видео файлом (video или document).")
        return
    
    # Check disk quota before starting upload
    file_size = getattr(file_obj, "file_size", 0) or 0
    try:
        quota = await _storage.get_quota()
        free_space = quota.get("free_space", 0)
        if file_size > 0 and free_space < file_size * 1.2:  # 20% buffer
            free_mb = free_space // (1024 * 1024)
            file_mb = file_size // (1024 * 1024)
            await message.answer(
                f"❌ Недостаточно места на Яндекс.Диске.\n"
                f"Свободно: {free_mb} МБ, нужно: {file_mb} МБ.\n"
                f"Освободите место и попробуйте снова."
            )
            await state.clear()
            return
    except Exception as exc:
        if _logger:
            _logger.warning("quota check failed", extra={"error": str(exc)})
        # Continue anyway, will fail on upload if no space

    data = await state.get_data()
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    await message.answer("⏳ Загружаю видео, подождите...")
    try:
        await _handle_add_video_upload(
            message,
            file_obj,
            filename,
            title,
            description,
        )
        await message.answer("✅ Видео добавлено и проиндексировано.")
    except Exception as exc:
        if _logger:
            _logger.exception("add_video failed", extra={"error": str(exc)})
        error_msg = str(exc)
        # User-friendly error messages
        if "507" in error_msg or "Insufficient Storage" in error_msg:
            await message.answer(
                "❌ Недостаточно места на Яндекс.Диске.\n"
                "Освободите место и попробуйте снова."
            )
        elif "timeout" in error_msg.lower():
            await message.answer(
                "❌ Превышено время ожидания загрузки.\n"
                "Попробуйте загрузить файл меньшего размера или повторите позже."
            )
        else:
            await message.answer(f"❌ Ошибка добавления видео: {exc}")
    finally:
        await state.clear()


@router.message(F.text)
async def search_handler(message: Message) -> None:
    if not message.text or not _index_service or not _settings:
        return
    query = message.text.strip()
    if not query or query.startswith("/"):
        return
    if message.from_user:
        now = time.monotonic()
        last = _last_request_at.get(message.from_user.id, 0.0)
        if now - last < 1.0:
            await message.answer("Слишком часто. Попробуйте через секунду.")
            return
        _last_request_at[message.from_user.id] = now

    top_k = max(_settings.top_k, 3)
    try:
        response = await _index_service.search(query, top_k)
    except Exception as exc:
        if _logger:
            _logger.exception("search failed", extra={"query": query, "error": str(exc)})
        await message.answer("Ошибка поиска. Попробуйте позже.")
        return
    if not response.results:
        await message.answer("Ничего не найдено. Попробуйте уточнить запрос.")
        return

    if message.from_user:
        _last_search_results[message.from_user.id] = response

    top_hit = response.results[0]
    lines = []
    if response.low_confidence:
        lines.append("⚠️ не уверен, уточните запрос")
    lines.append(f"Нашел видео: {top_hit.title}. Хочешь, пришлю?")
    if top_hit.snippet:
        snippet = top_hit.snippet
        if len(snippet) > 160:
            snippet = f"{snippet[:160]}..."
        lines.append(snippet)

    # Generate short token to avoid callback_data > 64 bytes
    token = await _create_callback_token(top_hit.video_id)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить", callback_data=f"send:{token}")],
            [InlineKeyboardButton(text="Показать еще 2 варианта", callback_data="more")],
        ]
    )
    await message.answer("\n".join(lines), reply_markup=keyboard)


@router.callback_query(F.data == "more")
async def more_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if not callback.from_user or not callback.message:
        return
    response = _last_search_results.get(callback.from_user.id)
    if not response or not response.results:
        await callback.message.answer("Сначала задайте поисковый запрос.")
        return

    lines = []
    if response.low_confidence:
        lines.append("⚠️ не уверен, уточните запрос")
    lines.append("Еще варианты:")

    buttons = []
    for idx, hit in enumerate(response.results[:3], 1):
        score_pct = int(hit.score * 100)
        line = f"{idx}. {hit.title} ({score_pct}%)"
        if hit.snippet:
            snippet = hit.snippet
            if len(snippet) > 140:
                snippet = f"{snippet[:140]}..."
            line = f"{line} - {snippet}"
        lines.append(line)
        # Generate short token for each result
        token = await _create_callback_token(hit.video_id)
        buttons.append(
            [InlineKeyboardButton(text=f"Отправить #{idx}", callback_data=f"send:{token}")]
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.answer("\n".join(lines), reply_markup=keyboard)


@router.callback_query(F.data.startswith("send:"))
async def send_video_callback(callback: CallbackQuery) -> None:
    await callback.answer("Готовлю отправку...")

    if not callback.data or not _catalog or not _storage or not _telegram_cache or not _settings:
        if callback.message:
            await callback.message.answer("Сервис недоступен.")
        return

    # Resolve token to video_id
    token = callback.data.split(":", 1)[1]
    video_id = await _resolve_callback_token(token)
    if not video_id:
        if callback.message:
            await callback.message.answer("Кнопка устарела, повторите поиск.")
        return

    video = await _catalog.get_video(video_id)
    if not video:
        if callback.message:
            await callback.message.answer(f"Видео не найдено.")
        return
    if not video.video_path:
        if callback.message:
            await callback.message.answer(
                "Видео файл не найден в хранилище. Сообщите администратору."
            )
        return

    cached_file_id = await _telegram_cache.get_file_id(video_id)
    if not cached_file_id and video.telegram_file_id:
        cached_file_id = video.telegram_file_id
    if cached_file_id and callback.message:
        try:
            sent_msg = await callback.message.answer_video(
                video=cached_file_id,
                caption=video.title,
            )
            if sent_msg.video:
                await _cache_telegram_file_id(video_id, sent_msg.video.file_id)
            return
        except Exception as exc:
            if _logger:
                _logger.warning(
                    "failed to send cached file id",
                    extra={"video_id": video_id, "error": str(exc)},
                )

    file_size = None
    missing_file = False
    try:
        meta = await _storage.get_meta(video.video_path)
        file_size = meta.get("size")
    except FileNotFoundError:
        missing_file = True
    except Exception as exc:
        if _logger:
            _logger.warning(
                "failed to get video size",
                extra={"video_id": video_id, "error": str(exc)},
            )

    if missing_file:
        if callback.message:
            await callback.message.answer(
                "Видео файл не найден в хранилище. Сообщите администратору."
            )
        return

    max_size = _settings.max_telegram_upload_bytes
    if file_size is not None and file_size <= max_size and callback.message:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                ext = os.path.splitext(video.video_path or "")[1] or ".mp4"
                safe_name = safe_filename(video.title or "video", fallback="video", default_ext=ext)
                local_path = os.path.join(tmpdir, safe_name)
                async with _download_semaphore:
                    await _storage.download_file(
                        video.video_path,
                        local_path,
                        max_bytes=max_size,
                    )

                sent_msg = await callback.message.answer_video(
                    video=FSInputFile(local_path),
                    caption=video.title,
                )

                if sent_msg.video:
                    await _cache_telegram_file_id(video_id, sent_msg.video.file_id)
                return
        except Exception as exc:
            if _logger:
                _logger.warning(
                    "failed to send video file, falling back to link",
                    extra={"video_id": video_id, "error": str(exc)},
                )
            if callback.message:
                await callback.message.answer(
                    "Не удалось отправить файлом - отправляю ссылку."
                )

    reason = ""
    if file_size is None:
        reason = "Не удалось определить размер файла, отправляю ссылку."
    elif file_size > max_size:
        reason = "Файл слишком большой для отправки в Telegram."

    try:
        public_url = await _storage.publish_link(video.video_path)
        message_text = f"{video.title}\n{public_url}"
        if reason:
            message_text = f"{message_text}\n{reason}"
        if callback.message:
            await callback.message.answer(message_text)
    except Exception as exc:
        if callback.message:
            await callback.message.answer(
                "Не могу сейчас выдать ссылку на видео, попробуйте позже."
            )
        if _logger:
            _logger.warning(
                "failed to publish link",
                extra={"video_id": video_id, "error": str(exc)},
            )


def _is_video_filename(filename: str) -> bool:
    ext = os.path.splitext(filename or "")[1].lower()
    return ext in VIDEO_EXTENSIONS


def _extract_video_file(message: Message):
    if message.video:
        return message.video, message.video.file_name or ""
    if message.document:
        doc = message.document
        mime = (doc.mime_type or "").lower()
        name = doc.file_name or ""
        if mime.startswith("video/") or _is_video_filename(name):
            return doc, name
    return None, ""


async def _cache_telegram_file_id(video_id: str, telegram_file_id: str) -> None:
    if _telegram_cache:
        await _telegram_cache.set_file_id(video_id, telegram_file_id)
    if _catalog:
        await _catalog.update_telegram_file_id(video_id, telegram_file_id)


async def _handle_add_video_upload(
    message: Message,
    file_obj,
    filename: str,
    title: str,
    description: str,
) -> None:
    if _settings is None or _storage is None or _catalog is None or _index_service is None:
        raise RuntimeError("services not initialized")

    slug = slugify(title)
    date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder = join_disk_path(_settings.yandex_disk_root, f"{slug}_{date_part}")

    await _storage.create_dir(folder)

    tmp_root = _settings.data_dir / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)

    safe_name = safe_filename(filename or f"{slug}.mp4", fallback=slug, default_ext=".mp4")
    with tempfile.TemporaryDirectory(dir=tmp_root) as tmpdir:
        local_path = os.path.join(tmpdir, safe_name)
        
        # Download file from Telegram using httpx with extended timeout
        # (aiogram's built-in download has short socket read timeout for large files)
        file_info = await message.bot.get_file(file_obj.file_id)
        download_url = f"https://api.telegram.org/file/bot{_settings.telegram_bot_token}/{file_info.file_path}"
        download_timeout = httpx.Timeout(300.0, connect=30.0)  # 5 min total, 30s connect
        async with httpx.AsyncClient(timeout=download_timeout, follow_redirects=True) as client:
            async with client.stream("GET", download_url) as response:
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

        remote_video_path = join_disk_path(folder, safe_name)
        await _storage.upload_file(remote_video_path, local_path)

    summary_text = title.strip()
    if description:
        summary_text = f"{summary_text}\n\n{description.strip()}"
    summary_path = join_disk_path(folder, "summary.md")
    await _storage.upload_text(summary_path, summary_text)

    meta_payload = {
        "title": title.strip(),
        "video_path": remote_video_path,
        "texts": [summary_path],
        "source": "telegram_upload",
        "created_at": utc_now_iso(),
    }
    meta_path = join_disk_path(folder, "meta.json")
    await _storage.upload_text(meta_path, json.dumps(meta_payload, ensure_ascii=False, indent=2))

    video_meta = await _storage.get_meta(remote_video_path)
    summary_meta = await _storage.get_meta(summary_path)
    fingerprint_payload = build_fingerprint_payload(
        remote_video_path, video_meta, [(summary_path, summary_meta)]
    )

    video_id = normalize_disk_path(folder)
    meta = VideoMeta(
        id=video_id,
        title=title.strip(),
        video_path=remote_video_path,
        summary_path=summary_path,
        transcript_path=None,
        text_paths=[summary_path],
        source="telegram_upload",
        created_at=utc_now_iso(),
    )
    entry = StorageEntry(
        folder=folder,
        meta=meta,
        fingerprint=Fingerprint(payload=fingerprint_payload),
        telegram_file_id=getattr(file_obj, "file_id", None),
    )
    await _catalog.upsert_entry(entry, status=VideoStatus.READY)

    if getattr(file_obj, "file_id", None):
        await _cache_telegram_file_id(video_id, file_obj.file_id)

    async with _index_lock:
        await _index_service.index_video(video_id)


async def _run_selftest() -> str:
    if _settings is None or _storage is None or _catalog is None or _index_service is None:
        return "Сервис не инициализирован."

    lines = []
    try:
        async with _scan_lock:
            await scan_yandex_disk_and_update_db(
                _storage,
                _catalog,
                _settings.yandex_disk_root,
                _settings.stability_check_sec,
                _settings.auto_meta_mode,
                _logger or logging.getLogger("video_library_bot.scan"),
            )
        lines.append("scan: ok")
    except Exception as exc:
        lines.append(f"scan: error {exc}")

    try:
        async with _index_lock:
            await _index_service.build_or_update_index()
        index_size = await _index_service.index_size()
        lines.append(f"index: ok (chunks={index_size})")
    except Exception as exc:
        lines.append(f"index: error {exc}")

    queries = [
        ("обзор", None),
        ("руина", "руин"),
        ("дай мне видео с руинами", "руин"),
        ("покажи мне разборы мазей", "маз"),
        ("разбор мазей", "маз"),
        ("перо", "перо"),
        ("как пользоваться пером", "перо"),
    ]
    fail_queries = {"руина", "разбор мазей"}

    for query, expected in queries:
        try:
            response = await _index_service.search(query, _settings.top_k)
        except Exception as exc:
            lines.append(f"{query}: error {exc}")
            continue
        count = len(response.results)
        top = response.results[0] if response.results else None
        if top:
            snippet = top.snippet or ""
            if len(snippet) > 120:
                snippet = f"{snippet[:120]}..."
            lines.append(
                f"{query}: found {count} low_confidence={response.low_confidence} "
                f"top1={top.title} score={top.score:.3f} snippet={snippet}"
            )
            if expected and expected not in top.title.lower():
                lines.append(f"FAIL: top1 title does not contain '{expected}' for query '{query}'")
            try:
                record = await _catalog.get_video(top.video_id)
                if not record or not record.video_path:
                    lines.append(f"{query}: DELIVERY_FAIL missing video_path")
                else:
                    try:
                        exists = await _storage.exists(record.video_path)
                    except Exception:
                        exists = True
                    if not exists:
                        lines.append(f"{query}: DELIVERY_FAIL video file missing")
            except Exception as exc:
                lines.append(f"{query}: DELIVERY_CHECK error {exc}")
        else:
            lines.append(f"{query}: found 0 low_confidence={response.low_confidence}")
            if query in fail_queries:
                lines.append(f"FAIL: {query}")

    return "\n".join(lines)


async def _send_long_message(message: Message, text: str, chunk_size: int = 3800) -> None:
    if not text:
        return
    if len(text) <= chunk_size:
        await message.answer(text)
        return
    parts = []
    remaining = text
    while len(remaining) > chunk_size:
        split_at = remaining.rfind("\n", 0, chunk_size)
        if split_at == -1:
            split_at = chunk_size
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        parts.append(remaining)
    for part in parts:
        await message.answer(part)


async def _build_health_report() -> str:
    storage_ok = False
    db_ok = False
    catalog_ok = False
    index_ok = False
    storage_error = ""
    db_error = ""
    catalog_error = ""
    index_error = ""

    if _storage:
        try:
            storage_ok = await _storage.check_token()
        except Exception as exc:
            storage_error = str(exc)

    if _settings:
        try:
            async with db_session(_settings.db_path) as db:
                await db.execute("SELECT 1")
            db_ok = True
        except Exception as exc:
            db_error = str(exc)

    if _catalog:
        try:
            await _catalog.get_status_counts()
            catalog_ok = True
        except Exception as exc:
            catalog_error = str(exc)

    index_size = 0
    if _index_service:
        try:
            index_size = await _index_service.index_size()
            index_ok = True
        except Exception as exc:
            index_error = str(exc)

    lines = [
        "Health status",
        f"storage_ok: {storage_ok}",
        f"db_ok: {db_ok}",
        f"catalog_ok: {catalog_ok}",
        f"index_ok: {index_ok}",
    ]
    if storage_error:
        lines.append(f"storage_error: {storage_error}")
    if db_error:
        lines.append(f"db_error: {db_error}")
    if catalog_error:
        lines.append(f"catalog_error: {catalog_error}")
    if index_error:
        lines.append(f"index_error: {index_error}")

    lines.append(f"last_scan_ok: {_last_scan_time or 'нет'}")
    lines.append(f"last_index_ok: {_last_index_time or 'нет'}")
    lines.append(f"last_error_time: {_last_error_time or 'нет'}")
    lines.append(f"last_scan_duration: {_last_scan_duration or 'нет'}")
    lines.append(f"last_index_duration: {_last_index_duration or 'нет'}")
    lines.append(f"index_size: {index_size}")
    if _catalog:
        try:
            counts = await _catalog.get_status_counts()
            lines.append(f"ready_count: {counts.get('READY', 0)}")
        except Exception:
            pass

    return "\n".join(lines)


def _build_admin_status(
    counts: dict[str, int],
    index_size: int,
    last_scan: str,
    last_index: str,
    last_error: str,
    last_scan_duration: str | None,
    last_index_duration: str | None,
    last_scan_error: str,
    last_index_error: str,
    recent_errors: list,
) -> str:
    scan_duration = last_scan_duration or "неизвестно"
    index_duration = last_index_duration or "неизвестно"
    status_text = (
        "Статус библиотеки\n\n"
        f"READY: {counts.get('READY', 0)}\n"
        f"NEEDS_TEXT: {counts.get('NEEDS_TEXT', 0)}\n"
        f"ERROR: {counts.get('ERROR', 0)}\n"
        f"DELETED: {counts.get('DELETED', 0)}\n\n"
        f"Чанков в индексе: {index_size}\n"
        f"Последний скан: {last_scan}\n"
        f"Длительность скана: {scan_duration}\n"
        f"Последняя индексация: {last_index}\n"
        f"Длительность индексации: {index_duration}\n"
        f"Последняя ошибка: {last_error}\n"
        f"Последняя ошибка скана: {last_scan_error}\n"
        f"Последняя ошибка индекса: {last_index_error}"
    )
    if recent_errors:
        status_text += "\n\nПоследние ошибки:"
        for record in recent_errors:
            reason = record.error_message or record.error_code or "unknown"
            if record.video_path and record.video_path not in reason:
                reason = f"{reason} ({record.video_path})"
            hint = _error_hint(record.error_code)
            suffix = f" | hint: {hint}" if hint else ""
            status_text += f"\n- {record.video_id}: {reason}{suffix}"
    return status_text


def _error_hint(error_code: str | None) -> str:
    if not error_code:
        return ""
    hints = {
        "NO_VIDEO": "add a video file to the folder",
        "MULTIPLE_VIDEOS": "leave only one video file in the folder",
        "META_REQUIRED": "set AUTO_META_MODE=write or add meta.json",
        "BAD_META_JSON": "fix meta.json format or re-upload",
        "VIDEO_NOT_FOUND": "check video_path and file exists",
        "NO_PERMISSION_MOVE": "grant write access or move file into a folder",
        "NETWORK": "check network/storage availability and retry",
        "UNKNOWN": "check logs for details",
    }
    return hints.get(error_code, "")


async def _get_last_scan_time(settings: Settings) -> str:
    async with db_session(settings.db_path) as db:
        cursor = await db.execute("SELECT scanned_at FROM scan_log ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()
        return row["scanned_at"] if row else "неизвестно"


async def _get_last_index_time(settings: Settings) -> str:
    async with db_session(settings.db_path) as db:
        cursor = await db.execute("SELECT MAX(indexed_at) AS last_index FROM index_state")
        row = await cursor.fetchone()
        if row and row["last_index"]:
            return row["last_index"]
    return "неизвестно"


async def run_scan_and_index_loop(
    scan_job: ScanJob,
    index_service: IndexService,
    settings: Settings,
    logger: logging.Logger,
) -> None:
    global _last_scan_error, _last_index_error, _last_scan_time, _last_index_time, _last_error_time
    global _last_scan_duration, _last_index_duration
    while True:
        result = None
        scan_id = uuid.uuid4().hex[:8]
        scan_logger = logging.LoggerAdapter(logger, {"scan_id": scan_id})
        try:
            scan_logger.info("background scan started")
            scan_start = time.monotonic()
            async with _scan_lock:
                result = await scan_yandex_disk_and_update_db(
                    scan_job._storage,
                    scan_job._catalog,
                    scan_job._root_path,
                    scan_job._stability_check_sec,
                    scan_job._auto_meta_mode,
                    scan_logger,
                )
            scan_elapsed = time.monotonic() - scan_start
            _last_scan_duration = f"{scan_elapsed:.2f}s"
            if not result:
                _last_scan_error = "scan failed: storage error"
                _last_error_time = utc_now_iso()
            else:
                _last_scan_error = None
                _last_scan_time = utc_now_iso()
                async with db_session(settings.db_path) as db:
                    await db.execute(
                        """
                        INSERT INTO scan_log (scanned_at, ready_count, needs_text_count, error_count, deleted_count)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            utc_now_iso(),
                            result.get("ready_count", 0),
                            result.get("needs_text_count", 0),
                            result.get("error_count", 0),
                            result.get("deleted_count", 0),
                        ),
                    )
                    await db.commit()
        except Exception as exc:
            _last_scan_error = str(exc)
            _last_error_time = utc_now_iso()
            scan_logger.exception("background scan failed")

        try:
            if result:
                scan_logger.info("background index started")
                index_start = time.monotonic()
                async with _index_lock:
                    await index_service.build_or_update_index()
                index_elapsed = time.monotonic() - index_start
                _last_index_duration = f"{index_elapsed:.2f}s"
                _last_index_error = None
                _last_index_time = utc_now_iso()
                index_size = await index_service.index_size()
                scan_logger.info("background index completed", extra={"index_size": index_size})
        except Exception as exc:
            _last_index_error = str(exc)
            _last_error_time = utc_now_iso()
            scan_logger.exception("background index failed")

        # Cleanup expired callback tokens
        try:
            deleted_count = await _cleanup_old_tokens()
            if deleted_count > 0:
                scan_logger.info("cleaned up expired callback tokens", extra={"count": deleted_count})
        except Exception as exc:
            scan_logger.warning("token cleanup failed", extra={"error": str(exc)})

        await asyncio.sleep(settings.scan_interval_sec)


async def main() -> None:
    global _settings, _index_service, _catalog, _storage, _telegram_cache, _logger

    settings = Settings()
    _settings = settings
    logger = setup_logging()
    _logger = logger

    lock_path = settings.data_dir / "run.lock"
    if not acquire_run_lock(lock_path):
        logger.error("Another instance is already running. Lock file: %s", lock_path)
        return

    try:
        if not settings.telegram_bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not set; aborting startup")
            return

        try:
            await init_db(settings.db_path)
        except Exception as exc:
            logger.error("DB migration failed: %s", exc)
            return

        storage = YandexDiskStorage(settings)
        _storage = storage
        catalog = CatalogService(settings.db_path)
        _catalog = catalog
        telegram_cache = TelegramCacheService(settings.db_path)
        _telegram_cache = telegram_cache

        index_service = IndexService(
            settings.db_path,
            settings.data_dir,
            storage,
            sim_threshold=settings.sim_threshold,
            lexical_boost=settings.lexical_boost,
        )
        _index_service = index_service

        scan_job = ScanJob(
            storage,
            catalog,
            settings.yandex_disk_root,
            settings.stability_check_sec,
            settings.auto_meta_mode,
        )

        background_task = asyncio.create_task(
            run_scan_and_index_loop(scan_job, index_service, settings, logger)
        )
        transcription_task = asyncio.create_task(
            run_transcription_loop(
                storage,
                catalog,
                index_service,
                settings.db_path,
                settings.data_dir,
                settings.enable_transcription,
                settings.transcribe_model,
                settings.auto_meta_mode,
                logger,
            )
        )

        # Use extended timeout for large file downloads (5 min = 300 sec)
        session = AiohttpSession(timeout=300)
        bot = Bot(token=settings.telegram_bot_token, session=session)
        dispatcher = Dispatcher(storage=MemoryStorage())
        dispatcher.include_router(router)

        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception as exc:
            logger.warning("deleteWebhook failed: %s", exc)

        logger.info("bot started")

        try:
            await dispatcher.start_polling(bot)
        except TelegramConflictError as exc:
            logger.error("Telegram polling conflict: another instance is running. %s", exc)
        finally:
            background_task.cancel()
            transcription_task.cancel()
            try:
                await background_task
            except asyncio.CancelledError:
                pass
            try:
                await transcription_task
            except asyncio.CancelledError:
                pass
            await bot.session.close()
            logger.info("bot stopped")
    finally:
        release_run_lock(lock_path)


if __name__ == "__main__":
    asyncio.run(main())
