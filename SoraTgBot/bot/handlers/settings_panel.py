from __future__ import annotations

import logging
from typing import Sequence

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards.settings import SettingsCallback, model_choice_keyboard, settings_main_keyboard
from services.user_config import UserConfigService
from services.user_settings import NEURO_MODELS, SORA_MODELS, UserSettingsRepository

router = Router(name="settings_panel")
_repo: UserSettingsRepository | None = None
_config_service: UserConfigService | None = None

logger = logging.getLogger(__name__)


class SettingsForm(StatesGroup):
    waiting_for_neuro_key = State()
    waiting_for_sora_key = State()


def setup_handlers(
    repo: UserSettingsRepository,
    config_service: UserConfigService,
) -> None:
    global _repo, _config_service
    _repo = repo
    _config_service = config_service


def _repo_instance() -> UserSettingsRepository:
    if _repo is None:
        raise RuntimeError("UserSettingsRepository is not configured")
    return _repo


def _config_instance() -> UserConfigService:
    if _config_service is None:
        raise RuntimeError("UserConfigService is not configured")
    return _config_service


@router.message(Command("settings"))
async def handle_settings_command(message: Message) -> None:
    await _send_settings_overview(message.chat.id, message)


@router.callback_query(F.data == "open_settings")
async def handle_settings_button(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if callback_query.message:
        await _send_settings_overview(callback_query.from_user.id, callback_query.message)


@router.callback_query(SettingsCallback.filter(F.action == "open"))
async def handle_settings_callback(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if callback_query.message:
        await _send_settings_overview(callback_query.from_user.id, callback_query.message)


async def _send_settings_overview(user_id: int, target: Message) -> None:
    text = await _build_settings_text(user_id)
    await target.answer(text, reply_markup=settings_main_keyboard())


async def _build_settings_text(user_id: int) -> str:
    repo = _repo_instance()
    config = _config_instance()
    raw_settings = await repo.get(user_id)
    neuro_cfg = await config.get_neuro_config(user_id)
    sora_cfg = await config.get_sora_config(user_id)

    neuro_key_text = _format_key(raw_settings.neuro_api_key if raw_settings else None, fallback=bool(config.global_neuro_api_key))
    sora_key_text = _format_key(raw_settings.sora_api_key if raw_settings else None, fallback=bool(config.global_sora_api_key))
    neuro_model_text = (
        raw_settings.neuro_model if raw_settings and raw_settings.neuro_model else f"{neuro_cfg.model} (по умолчанию)"
    )
    sora_model_text = (
        raw_settings.sora_model if raw_settings and raw_settings.sora_model else f"{sora_cfg.model} (по умолчанию)"
    )

    return (
        "Настройки:\n"
        f"- Текстовая модель: {neuro_model_text}\n"
        f"- Sora модель: {sora_model_text}\n"
        f"- NeuroAPI ключ: {neuro_key_text}\n"
        f"- Sora API ключ: {sora_key_text}\n\n"
        "Выберите действие:"
    )


def _format_key(value: str | None, fallback: bool) -> str:
    if value:
        return _mask_secret(value)
    if fallback:
        return "используется значение по умолчанию"
    return "не задан"


def _mask_secret(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return f"установлен ({value})"
    return f"установлен ({value[:4]}…{value[-4:]})"


@router.callback_query(SettingsCallback.filter(F.action == "choose_neuro_model"))
async def handle_choose_neuro_model(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if callback_query.message:
        keyboard = model_choice_keyboard("set_neuro_model", NEURO_MODELS)
        await callback_query.message.answer("Выберите модель для сценариев:", reply_markup=keyboard)


@router.callback_query(SettingsCallback.filter(F.action == "choose_sora_model"))
async def handle_choose_sora_model(callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    if callback_query.message:
        keyboard = model_choice_keyboard("set_sora_model", SORA_MODELS)
        await callback_query.message.answer("Выберите Sora модель:", reply_markup=keyboard)


@router.callback_query(SettingsCallback.filter(F.action == "set_neuro_model"))
async def set_neuro_model(callback_query: CallbackQuery, callback_data: SettingsCallback) -> None:
    await callback_query.answer()
    repo = _repo_instance()
    await repo.update_settings(callback_query.from_user.id, neuro_model=callback_data.value)
    if callback_query.message:
        await callback_query.message.answer(f"Текстовая модель обновлена: {callback_data.value}")
        await _send_settings_overview(callback_query.from_user.id, callback_query.message)


@router.callback_query(SettingsCallback.filter(F.action == "set_sora_model"))
async def set_sora_model(callback_query: CallbackQuery, callback_data: SettingsCallback) -> None:
    await callback_query.answer()
    repo = _repo_instance()
    await repo.update_settings(callback_query.from_user.id, sora_model=callback_data.value)
    if callback_query.message:
        await callback_query.message.answer(f"Sora модель обновлена: {callback_data.value}")
        await _send_settings_overview(callback_query.from_user.id, callback_query.message)


@router.callback_query(SettingsCallback.filter(F.action == "set_neuro_key"))
async def ask_neuro_key(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await state.set_state(SettingsForm.waiting_for_neuro_key)
    await callback_query.message.answer(
        "Отправьте новый NeuroAPI ключ (или '-' чтобы очистить)."
    )


@router.callback_query(SettingsCallback.filter(F.action == "set_sora_key"))
async def ask_sora_key(callback_query: CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    await state.set_state(SettingsForm.waiting_for_sora_key)
    await callback_query.message.answer(
        "Отправьте новый Sora (Kie.ai) API ключ (или '-' чтобы очистить)."
    )


@router.message(SettingsForm.waiting_for_neuro_key)
async def store_neuro_key(message: Message, state: FSMContext) -> None:
    await _store_key(message, state, field="neuro_api_key", label="NeuroAPI")


@router.message(SettingsForm.waiting_for_sora_key)
async def store_sora_key(message: Message, state: FSMContext) -> None:
    await _store_key(message, state, field="sora_api_key", label="Sora")


async def _store_key(message: Message, state: FSMContext, *, field: str, label: str) -> None:
    value = message.text.strip() if message.text else ""
    repo = _repo_instance()
    if value.lower() in {"-", "none", "clear"}:
        await repo.update_settings(message.from_user.id, **{field: None})
        await message.answer(f"{label} ключ очищен.", reply_markup=settings_main_keyboard())
    else:
        await repo.update_settings(message.from_user.id, **{field: value})
        await message.answer(f"{label} ключ обновлён.", reply_markup=settings_main_keyboard())
    await _send_settings_overview(message.from_user.id, message)
    await state.clear()


@router.message(Command("settings"), SettingsForm.waiting_for_neuro_key)
@router.message(Command("settings"), SettingsForm.waiting_for_sora_key)
async def handle_settings_during_input(message: Message, state: FSMContext) -> None:
    await state.clear()
    await handle_settings_command(message)
