from __future__ import annotations

from aiogram import Router

from bot.handlers import commands, photos


def register_handlers() -> Router:
    router = Router()
    router.include_router(commands.router)
    router.include_router(photos.router)
    return router
