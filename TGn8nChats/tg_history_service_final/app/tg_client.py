import logging
from typing import Optional

from pydantic import ValidationError
from telethon import TelegramClient
from telethon.sessions import StringSession

from .settings import get_settings


_client: Optional[TelegramClient] = None


def _build_client() -> TelegramClient:
    try:
        settings = get_settings()
    except ValidationError as exc:
        raise ValueError(
            "Missing or invalid env vars: TG_API_ID, TG_API_HASH, TG_SESSION_STRING"
        ) from exc

    if not settings.tg_api_hash or not settings.tg_session_string:
        raise ValueError("Missing required environment variables: TG_API_HASH, TG_SESSION_STRING")

    return TelegramClient(
        StringSession(settings.tg_session_string),
        settings.tg_api_id,
        settings.tg_api_hash,
    )


async def connect() -> TelegramClient:
    global _client
    if _client is not None:
        return _client

    _client = _build_client()
    await _client.start()
    logging.info("Telegram client connected")
    return _client


def get_client() -> TelegramClient:
    if _client is None:
        raise RuntimeError("Telegram client not initialized")
    return _client


async def disconnect() -> None:
    global _client
    if _client is None:
        return
    await _client.disconnect()
    _client = None
    logging.info("Telegram client disconnected")
