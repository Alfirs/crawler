import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.token import TokenValidationError, validate_token
from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("BOT_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")

API_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MAX_IDEA_CHARS = int(os.getenv("MAX_IDEA_CHARS", "1500"))

dp = Dispatcher()

kb_main = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Create carousel"), KeyboardButton(text="How it works?")]],
    resize_keyboard=True,
)

UserSession = Dict[str, Any]
user_sessions: Dict[int, UserSession] = {}


def _get_session(user_id: int) -> Optional[UserSession]:
    return user_sessions.get(user_id)


def _set_session(user_id: int, data: UserSession) -> None:
    user_sessions[user_id] = data


def _clear_session(user_id: int) -> None:
    user_sessions.pop(user_id, None)


async def _submit_generation(message: Message, slides: int, text: str) -> bool:
    trimmed = text.strip()
    if not trimmed:
        await message.answer("The idea text is empty. Please describe the topic.")
        return False
    if len(trimmed) > MAX_IDEA_CHARS:
        trimmed = trimmed[:MAX_IDEA_CHARS]
        await message.answer(f"Trimmed idea to {MAX_IDEA_CHARS} characters.")

    logger.info("Submitting generation: user=%s slides=%s", message.from_user.id, slides)
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/generate",
                json={
                    "format": "carousel",
                    "slides": slides,
                    "source": {"kind": "text", "text": trimmed},
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("HTTP error during /api/generate")
            await message.answer(f"Request failed: {exc}")
            return False

        payload = response.json()
        share_url = payload.get("share_url")
        if not share_url:
            logger.error("Missing share_url in payload: %s", payload)
            await message.answer("Generation succeeded but no editor link was returned.")
            return False

        await message.answer(
            "Draft is ready! Click the editor link to fine-tune slides:\n"
            f"{share_url}",
        )
        return True


@dp.message(Command("start", "new_post"))
async def start(m: Message):
    _set_session(m.from_user.id, {"stage": "slides"})
    await m.answer(
        "Hi! Let's craft a carousel.\n"
        "1) Send how many slides you need (6/8/10).\n"
        "2) Send the topic or a short draft.",
        reply_markup=kb_main,
    )


@dp.message(F.text == "How it works?")
async def instruction(m: Message):
    await m.answer(
        "The bot generates an outline and immediately opens an editor, similar to getdraft.io.\n"
        "Inside the editor you can change text, fonts, backgrounds, number of slides and export later.",
        reply_markup=kb_main,
    )
    _set_session(m.from_user.id, {"stage": "slides"})


@dp.message(F.text == "Create carousel")
async def mk_carousel(m: Message):
    _set_session(m.from_user.id, {"stage": "slides"})
    await m.answer("How many slides do you need? Choose 6, 8 or 10.")


@dp.message(F.text.regexp(r"^\d+$"))
async def slides_input(m: Message):
    session = _get_session(m.from_user.id)
    if not session or session.get("stage") != "slides":
        await m.answer("Send /start to begin a new carousel.")
        return

    slides = int(m.text.strip())
    if slides not in {6, 8, 10}:
        await m.answer("Please choose one of: 6, 8 or 10 slides.")
        return

    session["slides"] = slides
    session["stage"] = "idea"
    await m.answer("Great! Now describe the topic or paste your idea.")


@dp.message(F.text & ~F.text.regexp(r"^\d+$"))
async def idea_text(m: Message):
    if m.text in {"Create carousel", "How it works?"}:
        return
    session = _get_session(m.from_user.id)
    if not session or session.get("stage") != "idea":
        await m.answer("Please send /start before sharing an idea.")
        return
    slides = session["slides"]
    await m.answer("Working on the outline...")
    success = await _submit_generation(m, slides, m.text)
    if success:
        _clear_session(m.from_user.id)


def main() -> None:
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN missing in .env")
        raise SystemExit(1)
    try:
        validate_token(TOKEN)
    except TokenValidationError:
        logger.error("TELEGRAM_BOT_TOKEN looks invalid")
        raise SystemExit(1)

    logger.info("Bot started. API_URL=%s", API_URL)
    bot = Bot(TOKEN)
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
