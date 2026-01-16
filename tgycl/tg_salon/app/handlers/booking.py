from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import context
from app.config import Config
from app.keyboards import date_keyboard, services_keyboard, slots_keyboard, staff_keyboard
from app.states import BookingState
from app.yclients_api import YclientsAPI, YclientsAPIError

logger = logging.getLogger(__name__)
MSK_TZ = ZoneInfo("Europe/Moscow")
NAME_PHONE_HINT = "Введите имя и телефон, например: Анна +7 999 123-45-67"

router = Router(name="booking")


def _config(_: Message | CallbackQuery) -> Config:
    return context.get_config()


def _api(_: Message | CallbackQuery) -> YclientsAPI:
    return context.get_api_client()


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"
    if digits.startswith("9") and len(digits) == 10:
        return f"+7{digits}"
    raise ValueError("Телефон должен быть формата +7XXXXXXXXXX")


def _parse_custom_date(text: str) -> date | None:
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def _format_display_date(target: date) -> str:
    return target.strftime("%d.%m")


@router.callback_query(F.data == "menu_booking")
async def start_booking(callback: CallbackQuery, state: FSMContext) -> None:
    config = _config(callback)
    api = _api(callback)
    await state.clear()
    await state.set_state(BookingState.pick_service)
    try:
        services = api.get_services(config.company_id)
    except YclientsAPIError as exc:
        await callback.answer(f"Ошибка YCLIENTS: {exc.message}", show_alert=True)
        return
    if not services:
        await callback.answer("Нет опубликованных услуг", show_alert=True)
        return
    await state.update_data(services=services)
    await callback.message.edit_text(
        "Выбери услугу:", reply_markup=services_keyboard(services)
    )
    await callback.answer()


@router.callback_query(BookingState.pick_service, F.data.startswith("service_page:"))
async def paginate_services(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    services = data.get("services", [])
    offset = int(callback.data.split(":", 1)[1])
    await callback.message.edit_reply_markup(services_keyboard(services, offset=offset))
    await callback.answer()


@router.callback_query(BookingState.pick_service, F.data.startswith("service:"))
async def pick_service(callback: CallbackQuery, state: FSMContext) -> None:
    config = _config(callback)
    api = _api(callback)
    service_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    services = data.get("services", [])
    service = next((item for item in services if item.get("id") == service_id), None)
    if not service:
        await callback.answer("Не удалось найти услугу", show_alert=True)
        return
    logger.info("Service selected: %s", service.get("title"))
    try:
        staff = api.get_staff(config.company_id, service_id=service_id)
    except YclientsAPIError as exc:
        await callback.answer(f"Ошибка API: {exc.message}", show_alert=True)
        return
    if not staff:
        await callback.answer("Нет мастеров для услуги", show_alert=True)
        return
    await state.update_data(service=service, staff=staff)
    await state.set_state(BookingState.pick_staff)
    await callback.message.edit_text(
        f"Выбрана услуга: {service.get('title')}\nВыберите мастера:",
        reply_markup=staff_keyboard(staff),
    )
    await callback.answer()


@router.callback_query(BookingState.pick_staff, F.data.startswith("staff_page:"))
async def paginate_staff(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    staff = data.get("staff", [])
    offset = int(callback.data.split(":", 1)[1])
    await callback.message.edit_reply_markup(staff_keyboard(staff, offset=offset))
    await callback.answer()


@router.callback_query(BookingState.pick_staff, F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    services = data.get("services", [])
    await state.set_state(BookingState.pick_service)
    await callback.message.edit_text(
        "Выбери услугу:", reply_markup=services_keyboard(services)
    )
    await callback.answer()


@router.callback_query(BookingState.pick_staff, F.data.startswith("staff:"))
async def pick_staff(callback: CallbackQuery, state: FSMContext) -> None:
    staff_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    staff_list = data.get("staff", [])
    staff = next((item for item in staff_list if item.get("id") == staff_id), None)
    if not staff:
        await callback.answer("Мастер не найден", show_alert=True)
        return
    logger.info("Staff selected: %s", staff.get("name"))
    await state.update_data(selected_staff=staff)
    await state.set_state(BookingState.pick_date)
    await callback.message.edit_text(
        f"Мастер: {staff.get('name')}\nВыберите дату:",
        reply_markup=date_keyboard(),
    )
    await callback.answer()


@router.callback_query(BookingState.pick_date, F.data == "back_to_staff")
async def back_to_staff(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    staff_list = data.get("staff", [])
    await state.set_state(BookingState.pick_staff)
    await callback.message.edit_text(
        "Снова выберите мастера:", reply_markup=staff_keyboard(staff_list)
    )
    await callback.answer()


@router.callback_query(BookingState.pick_date, F.data.startswith("date:"))
async def handle_date_choice(callback: CallbackQuery, state: FSMContext) -> None:
    _, choice = callback.data.split(":", 1)
    today = datetime.now(MSK_TZ).date()
    if choice == "today":
        target_date = today
    elif choice == "tomorrow":
        target_date = today + timedelta(days=1)
    else:
        await state.update_data(awaiting_custom_date=True)
        await callback.message.answer("Введите дату в формате ДД.ММ.ГГГГ")
        await callback.answer()
        return
    await _render_slots_from_callback(callback, state, target_date)


async def _render_slots_from_callback(
    callback: CallbackQuery, state: FSMContext, target_date: date
) -> None:
    try:
        slots = await _load_slots(callback, state, target_date)
    except YclientsAPIError as exc:
        await callback.answer(f"Ошибка API: {exc.message}", show_alert=True)
        return
    except RuntimeError as exc:
        await callback.answer(str(exc), show_alert=True)
        await state.clear()
        return
    logger.info("Slots loaded: %s items for %s", len(slots), target_date)
    if not slots:
        await callback.message.answer(
            f"Нет свободных окон на {_format_display_date(target_date)}. Попробуйте другую дату.",
            reply_markup=date_keyboard(),
        )
        await callback.answer()
        return
    await state.update_data(
        selected_date=target_date.isoformat(),
        slots=slots,
        awaiting_custom_date=False,
    )
    await state.set_state(BookingState.pick_time)
    await callback.message.edit_text(
        f"Свободные окна {_format_display_date(target_date)}:",
        reply_markup=slots_keyboard(slots),
    )
    await callback.answer()


async def _load_slots(
    source: Message | CallbackQuery, state: FSMContext, target_date: date
) -> list[str]:
    config = _config(source)
    api = _api(source)
    data = await state.get_data()
    service = data.get("service")
    staff = data.get("selected_staff")
    if not service or not staff:
        raise RuntimeError("Сессия устарела, начните заново /start")
    return api.get_free_slots(
        config.company_id,
        staff_id=staff["id"],
        service_id=service["id"],
        date_iso=target_date.isoformat(),
    )


@router.message(BookingState.pick_date)
async def custom_date_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("awaiting_custom_date"):
        await message.answer("Пожалуйста, выберите дату кнопками")
        return
    parsed = _parse_custom_date(message.text or "")
    if not parsed:
        await message.answer("Формат даты ДД.ММ.ГГГГ")
        return
    try:
        slots = await _load_slots(message, state, parsed)
    except YclientsAPIError as exc:
        await message.answer(f"Ошибка API: {exc.message}")
        return
    except RuntimeError as exc:
        await message.answer(str(exc))
        await state.clear()
        return
    logger.info("Custom date slots loaded: %s items for %s", len(slots), parsed)
    if not slots:
        await message.answer(
            f"Нет свободных окон на {_format_display_date(parsed)}. Попробуйте другую дату.",
            reply_markup=date_keyboard(),
        )
        return
    await state.update_data(
        selected_date=parsed.isoformat(),
        slots=slots,
        awaiting_custom_date=False,
    )
    await state.set_state(BookingState.pick_time)
    await message.answer(
        f"Свободные окна {_format_display_date(parsed)}:",
        reply_markup=slots_keyboard(slots),
    )


@router.callback_query(BookingState.pick_time, F.data == "back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BookingState.pick_date)
    await callback.message.edit_text("Выберите дату:", reply_markup=date_keyboard())
    await callback.answer()


@router.callback_query(BookingState.pick_time, F.data.startswith("slot_page:"))
async def paginate_slots(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    slots = data.get("slots", [])
    offset = int(callback.data.split(":", 1)[1])
    await callback.message.edit_reply_markup(slots_keyboard(slots, offset=offset))
    await callback.answer()


@router.callback_query(BookingState.pick_time, F.data.startswith("slot:"))
async def pick_slot(callback: CallbackQuery, state: FSMContext) -> None:
    slot = callback.data.split(":", 1)[1]
    data = await state.get_data()
    slots = data.get("slots", [])
    if slot not in slots:
        await callback.answer("Слот недоступен", show_alert=True)
        return
    logger.info("Slot selected: %s", slot)
    await state.update_data(selected_time=slot)
    await state.set_state(BookingState.enter_client)
    await callback.message.edit_text(
        "Отлично! Теперь отправьте имя и телефон (пример: Анна +7 999 123-45-67)",
    )
    await callback.answer()


@router.message(BookingState.enter_client)
async def enter_client(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    parts = text.strip().split()
    if len(parts) < 2:
        await message.answer(NAME_PHONE_HINT)
        return
    phone_raw = parts[-1]
    name = " ".join(parts[:-1]).strip()
    if not name:
        await message.answer("Имя не должно быть пустым")
        return
    try:
        phone = _normalize_phone(phone_raw)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    data = await state.get_data()
    service = data.get("service")
    staff = data.get("selected_staff")
    date_iso = data.get("selected_date")
    time_txt = data.get("selected_time")
    if not all([service, staff, date_iso, time_txt]):
        await message.answer("Сессия устарела, начните заново /start")
        await state.clear()
        return
    start_dt = datetime.fromisoformat(f"{date_iso}T{time_txt}:00").replace(tzinfo=MSK_TZ)
    api = _api(message)
    config = _config(message)
    try:
        result = api.create_record(
            config.company_id,
            service_id=service["id"],
            staff_id=staff["id"],
            start_iso=start_dt.isoformat(),
            client_name=name,
            client_phone=phone,
        )
    except YclientsAPIError as exc:
        await message.answer(f"Не удалось создать запись: {exc.message}")
        return
    await state.clear()
    record_id = result.get("id") if isinstance(result, dict) else result
    await message.answer(
        f"Готово! Бронь № {record_id}. Ждем тебя {_format_display_date(start_dt.date())} в {time_txt}.",
    )
    logger.info("Record created: %s", result)
