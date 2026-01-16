from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.states import FitSession

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(FitSession.waiting_for_car)
    text = (
        "Привет! Отправь фото машины строго сбоку, чтобы было видно оба колеса. "
        "После этого скинь фото дисков — смогу сделать быструю примерку или каталожный рендер."
    )
    await message.answer(text)
