from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Config
from app import context
from app.keyboards import main_menu_keyboard

router = Router(name="common")


def _config(_: Message | CallbackQuery) -> Config:
    return context.get_config()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я помогу записаться в салон красоты.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "menu_back")
async def back_to_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выбери действие:", reply_markup=main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_about")
async def menu_about(callback: CallbackQuery) -> None:
    config = _config(callback)
    await callback.message.edit_text(config.about_text, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu_location")
async def menu_location(callback: CallbackQuery) -> None:
    config = _config(callback)
    lat, lon = config.location
    await callback.message.answer_location(latitude=lat, longitude=lon)
    await callback.message.answer(config.salon_address, reply_markup=main_menu_keyboard())
    await callback.answer()
