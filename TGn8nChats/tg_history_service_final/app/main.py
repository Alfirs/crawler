import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import ValidationError
from telethon.errors import ChannelInvalidError, FloodWaitError, PeerIdInvalidError

from .models import ChatHistoryRequest, DialogItem, MessageItem
from .settings import get_settings
from .tg_client import connect, disconnect, get_client


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="Telegram History Service")


@app.on_event("startup")
async def on_startup() -> None:
    logging.info("Connecting to Telegram...")
    try:
        await connect()
    except Exception as exc:
        logging.exception("Telegram client failed to connect: %s", exc)
        raise


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await disconnect()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    api_key = get_settings().api_key
    if api_key and x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def to_unix_seconds(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())


def parse_int(value: str | int | None, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{name} must be an integer")


def raise_flood_wait(exc: FloodWaitError) -> None:
    retry_after = int(getattr(exc, "seconds", 0) or 0)
    detail = f"Rate limited by Telegram. Retry after {retry_after} seconds"
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    raise HTTPException(status_code=429, detail=detail, headers=headers)


@app.get("/health", dependencies=[Depends(require_api_key)])
async def health_check() -> dict:
    return {
        "ok": True,
        "ts": datetime.now(tz=timezone.utc).isoformat(),
    }


@app.get("/tg/getDialogs", response_model=list[DialogItem], dependencies=[Depends(require_api_key)])
async def get_dialogs(days: str = "7", limit: str = "200") -> list[DialogItem]:
    days_value = parse_int(days, "days")
    limit_value = parse_int(limit, "limit")

    if days_value <= 0:
        raise HTTPException(status_code=400, detail="days must be > 0")
    if limit_value <= 0 or limit_value > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")

    client = get_client()
    cutoff = int(datetime.now(tz=timezone.utc).timestamp()) - (days_value * 86400)
    results: list[DialogItem] = []

    try:
        async for dialog in client.iter_dialogs():
            if not getattr(dialog, "date", None):
                continue
            last_ts = to_unix_seconds(dialog.date)
            if last_ts < cutoff:
                continue
            results.append(
                DialogItem(
                    chatId=int(dialog.id),
                    title=dialog.name or "",
                    lastTs=last_ts,
                )
            )
    except FloodWaitError as exc:
        logging.warning("Flood wait in getDialogs: %s", exc)
        raise_flood_wait(exc)
    except Exception as exc:
        logging.exception("getDialogs failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch dialogs")

    results.sort(key=lambda item: item.lastTs, reverse=True)
    return results[:limit_value]


@app.post("/tg/getChatHistory", response_model=list[MessageItem], dependencies=[Depends(require_api_key)])
async def get_chat_history(request: Request) -> list[MessageItem]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        req = ChatHistoryRequest.model_validate(payload)
    except ValidationError:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if req.count <= 0 or req.count > 200:
        raise HTTPException(status_code=400, detail="count must be between 1 and 200")

    client = get_client()
    try:
        entity = await client.get_entity(req.chatId)
    except FloodWaitError as exc:
        logging.warning("Flood wait in getChatHistory (get_entity): %s", exc)
        raise_flood_wait(exc)
    except (ValueError, PeerIdInvalidError, ChannelInvalidError) as exc:
        logging.warning("Chat not found for chatId=%s: %s", req.chatId, exc)
        raise HTTPException(status_code=404, detail=f"Chat not found: {req.chatId}")
    except Exception as exc:
        logging.exception("get_entity failed for chatId=%s: %s", req.chatId, exc)
        raise HTTPException(status_code=500, detail="Failed to resolve chat")

    messages: list[MessageItem] = []
    try:
        async for message in client.iter_messages(entity):
            text = getattr(message, "message", None)
            if not text:
                continue
            text = text.strip()
            if not text:
                continue
            messages.append(
                MessageItem(
                    chatId=req.chatId,
                    timestamp=to_unix_seconds(message.date),
                    fromMe=bool(getattr(message, "out", False)),
                    typeMessage="textMessage",
                    textMessage=text,
                )
            )
            if len(messages) >= req.count:
                break
    except FloodWaitError as exc:
        logging.warning("Flood wait in getChatHistory: %s", exc)
        raise_flood_wait(exc)
    except Exception as exc:
        logging.exception("getChatHistory failed for chatId=%s: %s", req.chatId, exc)
        raise HTTPException(status_code=500, detail="Failed to fetch messages")

    messages.sort(key=lambda item: item.timestamp)
    return messages
