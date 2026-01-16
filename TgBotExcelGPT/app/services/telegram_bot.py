import asyncio
from typing import Optional

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services import google_drive, intake_pipeline

COMMAND_KEYBOARD = ReplyKeyboardMarkup(
    [["Спецификация", "Чертежи"], ["Сбросить теги"]],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Отправьте файл проекта или сметы. "
        "Используйте кнопки /spec и /drawing, чтобы отметить, к какому типу относится следующий документ. "
        "Кнопка /clear_tags сбрасывает выбранные теги.",
        reply_markup=COMMAND_KEYBOARD,
    )


async def toggle_spec(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = context.user_data.get("spec_mode", False)
    context.user_data["spec_mode"] = not current
    status = "включён" if not current else "выключен"
    await update.message.reply_text(f"Режим «Спецификация» {status}.", reply_markup=COMMAND_KEYBOARD)


async def toggle_drawing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = context.user_data.get("drawing_mode", False)
    context.user_data["drawing_mode"] = not current
    status = "включён" if not current else "выключен"
    await update.message.reply_text(f"Режим «Чертежи» {status}.", reply_markup=COMMAND_KEYBOARD)


async def clear_tags(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["spec_mode"] = False
    context.user_data["drawing_mode"] = False
    await update.message.reply_text("Теги сброшены.", reply_markup=COMMAND_KEYBOARD)


async def handle_documents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return
    doc = update.message.document
    file = await doc.get_file()
    content = await file.download_as_bytearray()

    project_id = str(update.message.chat_id)
    temp_upload = google_drive.LOCAL_STORAGE_ROOT / project_id / doc.file_name
    temp_upload.parent.mkdir(parents=True, exist_ok=True)
    temp_upload.write_bytes(content)

    caption = update.message.caption or ""
    is_spec = context.user_data.get("spec_mode", False) or "спецификация" in caption.lower()
    is_draw = context.user_data.get("drawing_mode", False) or "чертеж" in caption.lower()

    result = await intake_pipeline.process_upload(
        project_id=project_id,
        file_links=[str(temp_upload)],
        is_specification=is_spec,
        is_drawing=is_draw,
        notes=update.message.caption,
    )
    status = result.get("extraction", {}).get("status", "обработано")
    await update.message.reply_text(
        f"Готово: {status}\n"
        f"Спецификация: {'да' if is_spec else 'нет'} | Чертежи: {'да' if is_draw else 'нет'}",
        reply_markup=COMMAND_KEYBOARD,
    )


def build_application(token: Optional[str] = None) -> Optional[Application]:
    real_token = token or settings.telegram_bot_token
    if not real_token:
        return None
    app = Application.builder().token(real_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("spec", toggle_spec))
    app.add_handler(CommandHandler("drawing", toggle_drawing))
    app.add_handler(CommandHandler("clear_tags", clear_tags))
    app.add_handler(MessageHandler(filters.Regex("^(Спецификация)$"), toggle_spec))
    app.add_handler(MessageHandler(filters.Regex("^(Чертежи)$"), toggle_drawing))
    app.add_handler(MessageHandler(filters.Regex("^(Сбросить теги)$"), clear_tags))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_documents))
    return app


async def run_bot() -> None:
    app = build_application()
    if not app:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    # Keep running until interrupted
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run_bot())
