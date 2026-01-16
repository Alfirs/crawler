from __future__ import annotations

import uuid
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.config import resolve_media_path
from bot.service import wheel_service
from bot.states import FitSession

router = Router()

GENERATION_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Каталожный рендер", callback_data="catalog_render")],
        [InlineKeyboardButton(text="Загрузить другие диски", callback_data="change_wheel")],
    ]
)


@router.message(StateFilter(FitSession.waiting_for_car), F.photo)
async def handle_car_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    _cleanup_file(data.get("car_photo_path"))
    _cleanup_file(data.get("wheel_photo_path"))

    car_filename = f"car-{uuid.uuid4().hex}.jpg"
    car_path = resolve_media_path("temp", car_filename)
    await message.bot.download(message.photo[-1], destination=car_path)

    await state.set_state(FitSession.waiting_for_wheel)
    await state.update_data(
        car_photo_path=str(car_path),
        wheel_photo_path=None,
        wheel_caption=None,
    )
    await message.answer(
        "Фото машины сохранил. Теперь пришли фото диска, который хочешь примерить (можно добавить подпись)."
    )


@router.message(StateFilter(FitSession.waiting_for_wheel, FitSession.ready_for_generation), F.photo)
async def handle_wheel_reference(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    car_path = data.get("car_photo_path")
    if not car_path:
        await message.answer("Сначала нужно фото машины, только потом дисков.")
        await state.set_state(FitSession.waiting_for_car)
        return

    _cleanup_file(data.get("wheel_photo_path"))

    wheel_filename = f"wheel-ref-{uuid.uuid4().hex}.jpg"
    wheel_path = resolve_media_path("temp", wheel_filename)
    await message.bot.download(message.photo[-1], destination=wheel_path)

    await state.set_state(FitSession.ready_for_generation)
    await state.update_data(
        wheel_photo_path=str(wheel_path),
        wheel_caption=message.caption,
    )
    await message.answer(
        "Диск сохранил. Выбери режим: быстрая примерка на этом фото или каталожный рендер.",
        reply_markup=GENERATION_KEYBOARD,
    )


@router.callback_query(StateFilter(FitSession.ready_for_generation), F.data == "change_wheel")
async def handle_change_wheel(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    _cleanup_file(data.get("wheel_photo_path"))
    await state.set_state(FitSession.waiting_for_wheel)
    await state.update_data(wheel_photo_path=None, wheel_caption=None)
    await callback.message.answer("Окей, пришли другое фото дисков.")
    await callback.answer()


@router.callback_query(StateFilter(FitSession.ready_for_generation), F.data == "catalog_render")
async def handle_catalog(callback: CallbackQuery, state: FSMContext) -> None:
    await _process_generation(callback, state)


async def _process_generation(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    car_path = data.get("car_photo_path")
    wheel_path = data.get("wheel_photo_path")
    if not car_path or not wheel_path:
        await callback.answer("Не хватает исходных файлов. Начни заново: машина и диски.", show_alert=True)
        return

    await callback.answer()
    progress_message = await callback.message.answer("Готовлю каталожный рендер, это может занять до минуты…")

    try:
        result_path = await wheel_service.render_catalog(
            car_photo_bytes=Path(car_path).read_bytes(),
            wheel_photo_bytes=Path(wheel_path).read_bytes(),
            wheel_prompt=data.get("wheel_caption"),
            wheel_metadata=None,
        )
        result_bytes = result_path.read_bytes()
    except RuntimeError as exc:
        await progress_message.edit_text(str(exc))
    except Exception:
        await progress_message.edit_text("Не удалось обработать фото. Попробуй ещё раз позже.")
    else:
        await progress_message.delete()
        caption = "Каталожный рендер готов. Можно попробовать ещё диски!"
        await callback.message.answer_photo(
            BufferedInputFile(result_bytes, filename="wheel_swap.png"),
            caption=caption,
        )
    finally:
        _cleanup_file(car_path)
        _cleanup_file(wheel_path)
        await state.set_state(FitSession.waiting_for_car)
        await state.update_data(car_photo_path=None, wheel_photo_path=None, wheel_caption=None)


def _cleanup_file(path: str | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
