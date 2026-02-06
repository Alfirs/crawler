from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types.input_file import BufferedInputFile

from app.config import AppConfig
from app.domain.rates import RatesStore
from app.exporters.session_export import export_logs
from app.storage.repo import SessionRepository


def register_admin_handlers(
    router: Router,
    repo: SessionRepository,
    rates_store: RatesStore,
    config: AppConfig,
) -> None:
    @router.message(Command("admin"))
    async def admin_menu(message: Message) -> None:
        if not _is_admin(message.from_user, config):
            return
        await message.answer(
            "Admin commands:\n"
            "/rates - show rates\n"
            "/set_rate <key> <value> - update default rate\n"
            "/set_rate <category.key> <value> - update category rate\n"
            "/export <user_id> - export logs"
        )

    @router.message(Command("rates"))
    async def show_rates(message: Message) -> None:
        if not _is_admin(message.from_user, config):
            return
        await message.answer(rates_store.render())

    @router.message(Command("set_rate"))
    async def set_rate(message: Message) -> None:
        if not _is_admin(message.from_user, config):
            return
        parts = (message.text or "").split()
        if len(parts) < 3:
            await message.answer("Usage: /set_rate <key> <value>")
            return
        key = parts[1]
        raw_value = parts[2]
        try:
            value = float(raw_value)
        except ValueError:
            await message.answer("Value must be a number")
            return
        category = None
        if "." in key:
            category, key = key.split(".", 1)
        try:
            rates_store.update_rate(key, value, category=category)
        except KeyError as exc:
            await message.answer(str(exc))
            return
        await message.answer("Rate updated")

    @router.message(Command("export"))
    async def export_session(message: Message) -> None:
        if not _is_admin(message.from_user, config):
            return
        parts = (message.text or "").split()
        if len(parts) < 2:
            await message.answer("Usage: /export <user_id>")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("User ID must be an integer")
            return
        logs = await repo.export_logs(target_id)
        payload = export_logs(logs)
        data = BufferedInputFile(payload.encode("utf-8"), filename=f"session_{target_id}.json")
        await message.answer_document(data)


def _is_admin(user: object | None, config: AppConfig) -> bool:
    if not user:
        return False
    user_id = getattr(user, "id", None)
    return bool(user_id in config.admin_ids)
