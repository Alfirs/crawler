from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from app import context
from app.config import ConfigError, load_config
from app.handlers import booking, common
from app.yclients_api import YclientsAPI


async def main() -> None:
    log_level_name = os.getenv("LOGLEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    try:
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    bot = Bot(token=config.bot_token, parse_mode=ParseMode.HTML)
    api_client = YclientsAPI(
        base_url=config.base_url,
        partner_token=config.partner_token,
        user_token=config.user_token,
        strict_v2=config.strict_v2,
    )

    context.set_context(config, api_client)

    dp = Dispatcher()
    dp.include_router(common.router)
    dp.include_router(booking.router)

    await bot.get_me()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
