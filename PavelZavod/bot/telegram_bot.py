from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes)

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


async def weekly_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send weekly batch of new drafts for review."""

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BACKEND_BASE_URL}/drafts", params={"status": "new"})
        response.raise_for_status()
        drafts = response.json()

    if not drafts:
        await update.message.reply_text("Новых черновиков нет.")
        return

    since = datetime.utcnow() - timedelta(days=7)
    for draft in drafts:
        created_at = datetime.fromisoformat(draft["created_at"])
        if created_at < since:
            continue
        text = f"{draft['short_hook'] or 'Без хука'}\n\n{draft['body_ru'] or draft['translated_text_ru']}\n\nCTA: {draft['cta_ru']}"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✅ Опубликовать",
                    callback_data=f"approve:{draft['id']}",
                ),
                InlineKeyboardButton(
                    "❌ Отклонить",
                    callback_data=f"reject:{draft['id']}",
                ),
            ]
        ])
        await update.message.reply_text(text, reply_markup=keyboard)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process approve/reject button presses."""

    query = update.callback_query
    await query.answer()
    action, draft_id = query.data.split(":")
    endpoint = "approve" if action == "approve" else "reject"
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BACKEND_BASE_URL}/drafts/{draft_id}/{endpoint}")
        response.raise_for_status()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text("Готово!")


def run_bot() -> None:
    """Entry point for running Telegram bot."""

    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("weekly_review", weekly_review))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()


if __name__ == "__main__":
    run_bot()
