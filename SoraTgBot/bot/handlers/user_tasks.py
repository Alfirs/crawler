from __future__ import annotations

import asyncio
import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.keyboards import (
    confirm_start_task_keyboard,
    main_menu_keyboard,
)
from core.dto import ProductDraft, ProductFormData, TaskSummary
from core.models import GenerationStatus, TaskStatus
from services.pipeline_worker import PipelineWorker
from services.session_storage import UserSessionStorage
from services.task_exporter import TaskExporter
from services.task_manager import TaskManager

router = Router(name=__name__)

UPLOADS_ROOT = Path("storage") / "uploads"

_task_manager: TaskManager | None = None
_pipeline_worker: PipelineWorker | None = None
_session_storage: UserSessionStorage | None = None
_task_exporter: TaskExporter | None = None

logger = logging.getLogger(__name__)

TASK_STATUS_TEXT = {
    TaskStatus.PENDING: "В очереди",
    TaskStatus.PROCESSING: "В работе",
    TaskStatus.COMPLETED: "Готова",
    TaskStatus.FAILED: "Готова с ошибками",
    TaskStatus.CANCELLED: "Отменена",
}


SUBTASK_STATUS_TEXT = {
    GenerationStatus.PENDING: "в очереди",
    GenerationStatus.SCRIPT_GENERATING: "скрипт",
    GenerationStatus.VIDEO_GENERATING: "видео",
    GenerationStatus.DONE: "готово",
    GenerationStatus.FAILED: "ошибка",
    GenerationStatus.CANCELLED: "отменён",
}

ALBUM_DEBOUNCE_SECONDS = 1.0

# Limit how many products we show in the pre-start summary
PREVIEW_LIMIT = 10

# Hard cap for summary length to avoid exceeding Telegram message limits
MAX_SUMMARY_CHARS = 2000


@dataclass
class AlbumBuffer:
    state: FSMContext
    messages: list[Message] = field(default_factory=list)
    caption: str | None = None
    task: asyncio.Task | None = None


_album_buffers: dict[tuple[int, str], AlbumBuffer] = {}









def setup_handlers(
    task_manager: TaskManager,
    session_storage: UserSessionStorage,
    pipeline_worker: PipelineWorker | None,
    task_exporter: TaskExporter | None,
) -> None:
    global _task_manager, _pipeline_worker, _session_storage, _task_exporter
    _task_manager = task_manager
    _pipeline_worker = pipeline_worker
    _session_storage = session_storage
    _task_exporter = task_exporter


def _require_task_manager() -> TaskManager:
    if _task_manager is None:
        raise RuntimeError("TaskManager is not configured")
    return _task_manager


def _session() -> UserSessionStorage:
    if _session_storage is None:
        raise RuntimeError("Session storage is not configured")
    return _session_storage


def _exporter() -> TaskExporter:
    if _task_exporter is None:
        raise RuntimeError("Task exporter is not configured")
    return _task_exporter


class ProductForm(StatesGroup):
    waiting_for_photo = State()
    waiting_for_description = State()


class BatchConfig(StatesGroup):
    waiting_for_generation_count = State()
    waiting_for_ideas = State()


class TaskCreation(StatesGroup):
    waiting_for_confirmation = State()


class BulkImport(StatesGroup):
    waiting_for_descriptions = State()


def _format_ideas(ideas: Iterable[str]) -> str:
    cleaned = [idea.strip() for idea in ideas if idea.strip()]
    return ", ".join(cleaned) if cleaned else "—"


def _format_draft(draft: ProductDraft, index: int) -> str:
    return textwrap.dedent(
        f"""
        {index}. {draft.description or "Без описания"}
           Файл: {draft.image_path.name if draft.image_path else "—"}
        """
    ).strip()


async def _build_tasks_text(user_id: int, page: int = 1, limit: int = 5) -> str:
    task_manager = _require_task_manager()
    if page < 1:
        page = 1
    offset = (page - 1) * limit
    summaries = await task_manager.list_tasks_for_user(user_id, limit=limit, offset=offset)
    if not summaries:
        if page == 1:
            return "У вас пока нет задач. Добавьте товары и идеи, затем запустите первую задачу."
        return f"На странице {page} задач нет. Попробуйте меньший номер страницы."

    lines = [f"Ваши задачи (стр. {page}):"]
    for summary in summaries:
        lines.append(_format_task_summary(summary))
    lines.append("")
    lines.append(f"Следующая страница: /tasks {page + 1}")
    lines.append("Детали: /task <task_id>, журнал: /tasklog <task_id>")
    return "\n".join(lines)


def _format_task_summary(summary: TaskSummary) -> str:
    status_text = TASK_STATUS_TEXT.get(summary.status, summary.status.value)
    total = summary.total or 0
    done = summary.done or 0
    failed = summary.failed or 0
    cancelled = summary.cancelled or 0
    updated = summary.updated_at.astimezone().strftime("%d.%m %H:%M")
    parts = [
        f"{summary.id}: {status_text}",
        f"готово {done}/{total}",
    ]
    if failed:
        parts.append(f"ошибок {failed}")
    if cancelled:
        parts.append(f"отменено {cancelled}")
    parts.append(f"обновлена {updated}")
    return ", ".join(parts)


def _format_subtask_line(index: int, subtask) -> str:
    status_text = SUBTASK_STATUS_TEXT.get(subtask.status, subtask.status.value)
    product_name = subtask.product.title[:40]
    idea_text = subtask.idea.text[:40]
    return f"{index}. {product_name} × «{idea_text}» — {status_text}"


def _parse_page_argument(raw: str | None) -> int:
    if not raw:
        return 1
    try:
        page = int(raw.strip())
    except (ValueError, AttributeError):
        return 1
    return page if page > 0 else 1


async def _collect_album_photo(message: Message, state: FSMContext) -> None:
    media_group_id = message.media_group_id
    if not media_group_id:
        return
    key = (message.from_user.id, media_group_id)
    buffer = _album_buffers.get(key)
    if buffer is None:
        buffer = AlbumBuffer(state=state)
        _album_buffers[key] = buffer
    buffer.messages.append(message)
    if message.caption and not buffer.caption:
        buffer.caption = message.caption
    if buffer.task:
        buffer.task.cancel()
    buffer.task = asyncio.create_task(_finalize_album_buffer(key))


async def _finalize_album_buffer(key: tuple[int, str]) -> None:
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return
    buffer = _album_buffers.pop(key, None)
    if not buffer:
        return
    await _process_album_buffer(buffer)


async def _process_album_buffer(buffer: AlbumBuffer) -> None:
    if not buffer.messages:
        return
    state = buffer.state
    user_id = buffer.messages[0].from_user.id
    uploads_dir = UPLOADS_ROOT / str(user_id)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    created_drafts: list[ProductDraft] = []
    base_caption = buffer.caption.strip() if buffer.caption else None
    try:
        for message in buffer.messages:
            if not message.photo:
                continue
            photo = message.photo[-1]
            file_path = uploads_dir / f"{photo.file_unique_id}.jpg"
            await message.bot.download(photo, destination=file_path)
            caption = (message.caption or base_caption or "").strip() or None
            draft = await _session().create_draft_from_photo(
                user_id=user_id,
                description=caption,
                image_path=file_path,
                image_file_id=photo.file_id,
            )
            created_drafts.append(draft)
    except Exception:
        logger.exception("Failed to import album for user %s", user_id)
        await buffer.messages[-1].answer(
            "Не удалось обработать альбом. Попробуйте ещё раз или загрузите фото по одному.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _session().discard_current_form(user_id)

    pending_ids = [draft.id for draft in created_drafts if not (draft.description or "").strip()]
    total = len(created_drafts)
    summary_lines = [f"????????? {total} ????."]

    if pending_ids:
        await state.set_state(BulkImport.waiting_for_descriptions)
        await state.update_data(bulk_draft_ids=pending_ids)
        summary_lines.append(
            "????????? ???? ???????? ? ???????? ?? ???? ????, "
            f"??? {len(pending_ids)} ????? (?????? ?????? ? ???????? ??? ???????????????? ????)."
        )
        summary_lines.append("??????? '-' ??? /skip, ????? ?????????? ? ????????? ?????.")
    else:
        await state.clear()
        summary_lines.append("???????? ????? ?? ??????? ???????. ????? ??????????????? ????? ????? /my_products.")

    await buffer.messages[-1].answer("\n".join(summary_lines), reply_markup=main_menu_keyboard())


@router.message(Command("tasks"))
async def handle_list_tasks(message: Message, command: CommandObject) -> None:
    page = _parse_page_argument(command.args)
    text = await _build_tasks_text(message.from_user.id, page=page)
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "list_tasks")
async def handle_list_tasks_callback(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    text = await _build_tasks_text(callback_query.from_user.id)
    if callback_query.message:
        await callback_query.message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("task"))
async def handle_task_detail(message: Message, command: CommandObject) -> None:
    task_id = (command.args or "").strip()
    if not task_id:
        await message.answer("Укажите ID задачи: /task <task_id>")
        return

    task_manager = _require_task_manager()
    task = await task_manager.load_task(task_id)
    if task is None or task.owner_user_id != message.from_user.id:
        await message.answer("Задача с таким ID не найдена.")
        return

    progress = await task_manager.get_task_progress(task.id)
    total = progress["total"]
    done = progress["done"]
    failed = progress["failed"]
    cancelled = progress.get("cancelled", 0)
    pending = total - done - failed - cancelled

    subtask_lines = [
        _format_subtask_line(index, subtask)
        for index, subtask in enumerate(task.subtasks[:5], start=1)
    ]
    if len(task.subtasks) > 5:
        subtask_lines.append(f"… и ещё {len(task.subtasks) - 5} комбинаций.")

    status_text = TASK_STATUS_TEXT.get(task.status, task.status.value)
    lines = [
        f"Задача {task.id}",
        f"Статус: {status_text}",
        f"Прогресс: готово {done}/{total}, ошибок {failed}, отменено {cancelled}, в очереди {pending}",
        "",
    ]
    if subtask_lines:
        lines.append("Примеры сабтасков:")
        lines.extend(subtask_lines)
        lines.append("")
    lines.append("Для списка задач используйте /tasks.")
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())


@router.message(Command("tasklog"))
async def handle_task_log(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if not parts:
        await message.answer("Использование: /tasklog <task_id> [page]", reply_markup=main_menu_keyboard())
        return
    task_id = parts[0]
    page = _parse_page_argument(parts[1] if len(parts) > 1 else None)
    limit = 10
    offset = (page - 1) * limit

    task_manager = _require_task_manager()
    task = await task_manager.load_task(task_id)
    if task is None or task.owner_user_id != message.from_user.id:
        await message.answer("Задача с таким ID не найдена.", reply_markup=main_menu_keyboard())
        return

    events = await task_manager.get_task_events(task.id, limit=limit, offset=offset)
    if not events:
        await message.answer("Нет записей в журнале для этой страницы.", reply_markup=main_menu_keyboard())
        return

    lines = [f"Журнал задачи {task.id} (стр. {page}):"]
    for event in events:
        ts = event["created_at"].astimezone().strftime("%d.%m %H:%M:%S")
        lines.append(f"{ts} — {event['message']}")
    lines.append("")
    lines.append(f"Следующая страница: /tasklog {task.id} {page + 1}")
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())


@router.message(Command("download_task"))
async def handle_download_task(message: Message, command: CommandObject) -> None:
    task_id = (command.args or "").strip()
    if not task_id:
        await message.answer("Укажите ID задачи: /download_task <task_id>")
        return

    task_manager = _require_task_manager()
    task = await task_manager.load_task(task_id)
    if task is None or task.owner_user_id != message.from_user.id:
        await message.answer("Задача с таким ID не найдена.")
        return

    exporter = _exporter()
    archive_path = await exporter.ensure_archive(task)
    if not archive_path.exists():
        await message.answer("Архив ещё не готов. Попробуйте позже.")
        return

    caption = f"Архив задачи {task.id}. Видео и metadata.json внутри."
    try:
        await message.answer_document(FSInputFile(archive_path, filename=archive_path.name), caption=caption)
        await _require_task_manager().record_event(
            task.id,
            "task_archive_downloaded",
            "Пользователь запросил архив через /download_task.",
        )
    except Exception:
        logging.exception("Failed to send archive %s", archive_path)
        await message.answer(
            f"Не удалось отправить архив автоматически. Заберите файл вручную: {archive_path}",
            reply_markup=main_menu_keyboard(),
        )


@router.message(Command("cancel_task"))
async def handle_cancel_task(message: Message, command: CommandObject) -> None:
    task_id = (command.args or "").strip()
    if not task_id:
        await message.answer("Укажите ID задачи: /cancel_task <task_id>")
        return

    task_manager = _require_task_manager()
    success = await task_manager.cancel_task(task_id)
    if not success:
        await message.answer("Задача с таким ID не найдена.")
        return

    await message.answer(f"Задача {task_id} отменена.", reply_markup=main_menu_keyboard())


@router.message(Command("repeat_task"))
async def handle_repeat_task(message: Message, command: CommandObject) -> None:
    task_id = (command.args or "").strip()
    if not task_id:
        await message.answer("Укажите ID задачи: /repeat_task <task_id>")
        return

    task_manager = _require_task_manager()
    new_task = await task_manager.repeat_task(task_id, owner_user_id=message.from_user.id)
    if new_task is None:
        await message.answer("Не удалось повторить задачу. Убедитесь, что исходная задача существует.", reply_markup=main_menu_keyboard())
        return

    if _pipeline_worker:
        await _pipeline_worker.enqueue(new_task.id)
        status_text = "Новая задача отправлена в обработку."
    else:
        status_text = "Новая задача создана. Запустите обработку вручную."

    await message.answer(
        f"{status_text}\nID новой задачи: {new_task.id}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(BulkImport.waiting_for_descriptions, F.text)
async def handle_bulk_descriptions(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    draft_ids: list[str] = data.get("bulk_draft_ids") or []
    if not draft_ids:
        await state.clear()
        await message.answer("Список черновиков пуст. Начните добавление заново.", reply_markup=main_menu_keyboard())
        return

    text = message.text.strip()
    if not text:
        await message.answer("Отправьте текст или '-' чтобы пропустить.", reply_markup=main_menu_keyboard())
        return

    if text.lower() in {"-", "пропустить", "/skip", "skip"}:
        await state.clear()
        await message.answer("Пропускаем. Описания можно добавить позже через /my_products.", reply_markup=main_menu_keyboard())
        return

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == 1:
        descriptions = lines * len(draft_ids)
    elif len(lines) == len(draft_ids):
        descriptions = lines
    else:
        await message.answer(
            f"Нужно либо одно описание, либо {len(draft_ids)} строк. Сейчас строк: {len(lines)}.",
            reply_markup=main_menu_keyboard(),
        )
        return

    for draft_id, desc in zip(draft_ids, descriptions):
        await _session().update_draft_description(draft_id, desc)

    await state.clear()
    await message.answer("Описания сохранены.", reply_markup=main_menu_keyboard())


@router.message(BulkImport.waiting_for_descriptions)
async def handle_bulk_descriptions_invalid(message: Message) -> None:
    await message.answer("Отправьте текстовые описания или '-' чтобы пропустить.", reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "add_product")
async def handle_add_product(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Start product creation flow."""
    await callback_query.answer()
    user_id = callback_query.from_user.id
    _session().start_form(user_id)
    await state.set_state(ProductForm.waiting_for_photo)
    if callback_query.message:
        await callback_query.message.answer(
            "Отправь фото товара (можно одно). Файл будет сохранён и добавлен в карточку.",
            reply_markup=main_menu_keyboard(),
        )


@router.message(ProductForm.waiting_for_photo, F.photo)
async def handle_product_photo(message: Message, state: FSMContext) -> None:
    """Save uploaded photo and ask for description."""
    user_id = message.from_user.id
    if message.media_group_id:
        await _collect_album_photo(message, state)
        return
    photo = message.photo[-1]
    uploads_dir = UPLOADS_ROOT / str(user_id)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / f"{photo.file_unique_id}.jpg"
    await message.bot.download(photo, destination=file_path)
    _session().update_current_form(
        user_id,
        image_path=file_path,
        image_file_id=photo.file_id,
    )
    await state.set_state(ProductForm.waiting_for_description)
    await message.answer("Фото сохранено. Введи краткое описание товара (название/ключевые характеристики).")


@router.message(ProductForm.waiting_for_photo)
async def handle_missing_photo(message: Message) -> None:
    await message.answer("Пожалуйста, отправь фотографию товара, чтобы продолжить.")


@router.callback_query(F.data == "edit_description")
async def prompt_description(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    if _session().get_current_form(user_id) is None:
        await callback_query.message.answer("Сначала нажми «Добавить товар» и отправь фото.")
        return
    await state.set_state(ProductForm.waiting_for_description)
    await callback_query.message.answer("Введи новое описание товара.")


@router.message(ProductForm.waiting_for_description, F.text)
async def handle_description(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    _session().update_current_form(user_id, description=message.text.strip())
    try:
        draft = await _session().complete_form(user_id)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()
    await message.answer(
        "Товар сохранён! Чтобы добавить ещё, снова нажми «Добавить товар».",
        reply_markup=main_menu_keyboard(),
    )
    summary = await _format_draft_summary(user_id, draft)
    await message.answer(summary)


@router.message(ProductForm.waiting_for_description)
async def handle_missing_description(message: Message) -> None:
    await message.answer("Опиши товар текстом, чтобы продолжить.")


@router.callback_query(F.data == "set_generation_count")
async def prompt_generation_count(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await state.set_state(BatchConfig.waiting_for_generation_count)
    await callback_query.message.answer("Введи общее количество видео на каждую идею (1–10).")


@router.message(BatchConfig.waiting_for_generation_count, F.text)
async def handle_generation_count(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    try:
        count = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно число от 1 до 10.")
        return
    if not 1 <= count <= 10:
        await message.answer("Нужно число от 1 до 10.")
        return
    await _session().set_generation_count(user_id, count)
    await state.clear()
    await message.answer(f"Количество генераций установлено: {count}.")


@router.callback_query(F.data == "add_ideas")
async def prompt_ideas(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await state.set_state(BatchConfig.waiting_for_ideas)
    await callback_query.message.answer(
        "Отправь идеи для сценариев. Можно строками (каждая идея с новой строки) "
        "или списком через запятую."
    )


@router.message(BatchConfig.waiting_for_ideas, F.text)
async def handle_global_ideas(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    raw = message.text.replace("\r", "\n")
    pieces = [part.strip() for part in raw.replace(",", "\n").split("\n") if part.strip()]
    if not pieces:
        await message.answer("Не нашёл идей в сообщении — попробуй ещё раз.")
        return
    await _session().set_ideas(user_id, pieces)
    await state.clear()
    await message.answer(f"Добавлено идей: {len(pieces)}.")


@router.message(Command("my_products"))
async def handle_my_products(message: Message) -> None:
    user_id = message.from_user.id
    drafts = await _session().get_drafts(user_id)
    if not drafts:
        await message.answer("У тебя пока нет сохранённых товаров. Нажми «Добавить товар», чтобы начать.")
        return
    config = await _session().get_config(user_id)
    text = "\n\n".join(_format_draft(draft, index + 1) for index, draft in enumerate(drafts))
    await message.answer(
        textwrap.dedent(
            f"""
            Сохранённые товары:

            {text}

            ⚙️ Параметры задачи:
            • Генераций на идею: {config.generation_count}
            • Идей: {len(config.ideas) or 1}
            """
        ).strip()
    )


async def _format_draft_summary(user_id: int, draft: ProductDraft) -> str:
    drafts = await _session().get_drafts(user_id)
    return textwrap.dedent(
        f"""
        ❇️ Карточка #{len(drafts)}:
        • Описание: {draft.description}
        • Фото: {draft.image_path.name if draft.image_path else "—"}
        """
    ).strip()


@router.callback_query(F.data == "start_task")
async def handle_start_task(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    if _session().get_current_form(user_id):
        await callback_query.message.answer(
            "Сначала заверши текущую карточку товара (заполни описание/идеи), затем запускай задачу."
        )
        return

    drafts = await _session().get_drafts(user_id)
    if not drafts:
        await callback_query.message.answer("Список товаров пуст. Нажми «Добавить товар», чтобы создать карточку.")
        return

    config = await _session().get_config(user_id)
    summary_text, totals = _build_task_summary(drafts, config)
    idea_preview = _format_idea_preview(config.ideas)
    await state.set_state(TaskCreation.waiting_for_confirmation)
    await callback_query.message.answer(
        "Готово к запуску:\n"
        f"• Товаров: {totals['products']}\n"
        f"• Подзадач (товар × идея): {totals['subtasks']}\n"
        f"• Суммарных генераций: {totals['generations']}\n\n"
        f"Идеи ({len(config.ideas) or 1}): {idea_preview}\n\n"
        f"{summary_text}\n\n"
        "Запустить задачу?",
        reply_markup=confirm_start_task_keyboard(),
    )


@router.callback_query(TaskCreation.waiting_for_confirmation, F.data == "cancel_start_task")
async def handle_cancel_start_task(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer("Запуск отменён")
    await state.clear()


@router.callback_query(TaskCreation.waiting_for_confirmation, F.data == "confirm_start_task")
async def handle_confirm_start_task(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    drafts = await _session().consume_drafts(user_id)
    config = await _session().get_config(user_id)
    if not drafts:
        await callback_query.message.answer("Карточки товаров не найдены — возможно, их уже запустили.")
        await state.clear()
        return

    task_manager = _require_task_manager()
    task = await task_manager.create_task_from_drafts(
        drafts,
        ideas=config.ideas,
        generation_count=config.generation_count,
        owner_user_id=user_id,
    )
    await task_manager.record_event(
        task.id,
        "task_created",
        f"Создано пользователем {user_id}: {len(drafts)} товаров, {len(config.ideas) or 1} идей.",
    )
    await state.clear()

    if _pipeline_worker:
        await _pipeline_worker.enqueue(task.id)
        status_text = "Задача создана и отправлена в очередь на генерацию."
    else:
        status_text = (
            "Задача создана. Запусти обработчик вручную или используй /check_sora "
            "после выполнения тестовой команды."
        )

    await callback_query.message.answer(
        f"{status_text}\nID задачи: {task.id}\nПодзадач: {len(task.subtasks)}",
        reply_markup=main_menu_keyboard(),
    )


def _build_task_summary(drafts: list[ProductDraft], config) -> tuple[str, dict[str, int]]:
    lines: list[str] = []
    idea_list = config.ideas or ["Общий сценарий"]
    subtasks = len(drafts) * len(idea_list)
    generations = subtasks * config.generation_count
    for index, draft in enumerate(drafts, start=1):
        lines.append(
            textwrap.dedent(
                f"""
                {index}. {draft.description or "Без описания"}
                   Фото: {draft.image_path.name if draft.image_path else "—"}
                """
            ).strip()
        )

    visible_lines = lines[:PREVIEW_LIMIT]
    if len(lines) > PREVIEW_LIMIT:
        remaining = len(lines) - PREVIEW_LIMIT
        visible_lines.append(f"… ещё {remaining} товаров. Подробности в /my_products.")

    summary = "\n\n".join(visible_lines)
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rstrip() + "… (укорочено)"

    totals = {
        "products": len(drafts),
        "subtasks": subtasks,
        "generations": generations,
    }
    return summary, totals


def _format_idea_preview(ideas: list[str]) -> str:
    values = [idea.strip() for idea in ideas or [] if idea.strip()]
    if not values:
        return "Общий сценарий"
    preview = ", ".join(values[:5])
    if len(values) > 5:
        preview += f" … +{len(values) - 5}"
    return preview
