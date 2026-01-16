from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Primary inline keyboard for task management actions."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить товар", callback_data="add_product")
    builder.button(text="Описание", callback_data="edit_description")
    builder.button(text="Количество генераций", callback_data="set_generation_count")
    builder.button(text="Добавить идеи", callback_data="add_ideas")
    builder.button(text="Запустить задачу", callback_data="start_task")
    builder.button(text="Мои задачи", callback_data="list_tasks")
    builder.button(text="Настройки", callback_data="open_settings")
    builder.adjust(1)
    return builder.as_markup()


def confirm_start_task_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Запустить", callback_data="confirm_start_task")
    builder.button(text="Отмена", callback_data="cancel_start_task")
    builder.adjust(2)
    return builder.as_markup()
