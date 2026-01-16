from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class SettingsCallback(CallbackData, prefix="usrset"):
    action: str
    value: str | None = None


def settings_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Текстовая модель", callback_data=SettingsCallback(action="choose_neuro_model").pack())
    builder.button(text="Sora модель", callback_data=SettingsCallback(action="choose_sora_model").pack())
    builder.button(text="NeuroAPI ключ", callback_data=SettingsCallback(action="set_neuro_key").pack())
    builder.button(text="Sora API ключ", callback_data=SettingsCallback(action="set_sora_key").pack())
    builder.adjust(2)
    return builder.as_markup()


def model_choice_keyboard(action: str, values: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value in values:
        builder.button(
            text=value,
            callback_data=SettingsCallback(action=action, value=value).pack(),
        )
    builder.button(text="Назад", callback_data=SettingsCallback(action="open").pack())
    builder.adjust(2)
    return builder.as_markup()
