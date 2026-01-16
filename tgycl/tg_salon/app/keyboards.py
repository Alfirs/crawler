from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_LIMIT = 10


def _paginate(sequence: Sequence, offset: int) -> tuple[Sequence, bool, bool]:
    start = max(offset, 0)
    end = start + PAGE_LIMIT
    page = sequence[start:end]
    has_prev = start > 0
    has_next = end < len(sequence)
    return page, has_prev, has_next


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💇 О нас", callback_data="menu_about")
    builder.button(text="🗺 Как добраться", callback_data="menu_location")
    builder.button(text="🗓 Записаться", callback_data="menu_booking")
    builder.adjust(1)
    return builder.as_markup()


def services_keyboard(services: Sequence[dict], offset: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    page, has_prev, has_next = _paginate(services, offset)
    for service in page:
        title = service.get("title") or f"Услуга {service.get('id')}"
        builder.button(text=title[:45], callback_data=f"service:{service['id']}")
    builder.adjust(1)
    _append_pagination(builder, "service_page", offset, has_prev, has_next)
    builder.button(text="↩️ В меню", callback_data="menu_back")
    return builder.as_markup()


def staff_keyboard(staff: Sequence[dict], offset: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    page, has_prev, has_next = _paginate(staff, offset)
    for member in page:
        name = member.get("name") or f"Мастер {member.get('id')}"
        builder.button(text=name[:45], callback_data=f"staff:{member['id']}")
    builder.adjust(1)
    _append_pagination(builder, "staff_page", offset, has_prev, has_next)
    builder.button(text="↩️ Сменить услугу", callback_data="back_to_services")
    return builder.as_markup()


def date_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сегодня", callback_data="date:today")
    builder.button(text="Завтра", callback_data="date:tomorrow")
    builder.button(text="Другой день...", callback_data="date:custom")
    builder.button(text="↩️ Сменить мастера", callback_data="back_to_staff")
    builder.adjust(1)
    return builder.as_markup()


def slots_keyboard(slots: Sequence[str], offset: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    page, has_prev, has_next = _paginate(slots, offset)
    for slot in page:
        builder.button(text=slot, callback_data=f"slot:{slot}")
    builder.adjust(2)
    _append_pagination(builder, "slot_page", offset, has_prev, has_next)
    builder.button(text="↩️ Сменить дату", callback_data="back_to_dates")
    return builder.as_markup()


def _append_pagination(
    builder: InlineKeyboardBuilder,
    prefix: str,
    offset: int,
    has_prev: bool,
    has_next: bool,
) -> None:
    nav_buttons: list[InlineKeyboardButton] = []
    if has_prev:
        prev_offset = max(offset - PAGE_LIMIT, 0)
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{prefix}:{prev_offset}")
        )
    if has_next:
        nav_buttons.append(
            InlineKeyboardButton(text="Далее ➡️", callback_data=f"{prefix}:{offset + PAGE_LIMIT}")
        )
    if nav_buttons:
        builder.row(*nav_buttons)
