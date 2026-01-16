from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Dict, Sequence

import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .analytics import AnalyticsPipeline
from .config import AppConfig, TelegramSettings
from .image_parser import ImageParser
from .nalog_api import NalogAPI
from .pdf_parser import PDFParser
from .wb_api import WildberriesAPI

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram interface that triggers every action through buttons."""

    MENU_MAIN = "menu:main"
    MENU_NALOG = "menu:nalog"
    MENU_WB = "menu:wb"
    ACTION_IMAGE = "action:image"
    ACTION_PDF = "action:pdf"
    ACTION_ANALYTICS = "action:analytics"
    NALOG_MODE_PREFIX = "nalog_mode:"
    WB_MODE_PREFIX = "wb_mode:"
    EXPECTATION_KEY = "expectation"
    EXPECTATION_PAYLOAD_KEY = "expectation_payload"

    def __init__(self, config: AppConfig) -> None:
        if not config.telegram:
            raise ValueError("Telegram settings are not provided")
        self.config = config
        self.telegram_settings: TelegramSettings = config.telegram
        self.allowed_users = set(self.telegram_settings.allowed_user_ids)
        self.nalog_api = NalogAPI(config.nalog_api)
        self.wb_api = WildberriesAPI(config.wb_api)
        self.image_parser = ImageParser()
        self.pdf_parser = PDFParser()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        await update.effective_message.reply_text(
            "Привет! Выбирайте действие кнопками ниже. Можно запросить данные ФНС/WB, распознать накладные и запустить аналитику."
        )
        await self._send_main_menu(update, context)

    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        await self._send_main_menu(update, context)

    async def handle_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        query = update.callback_query
        if not query:
            return
        await query.answer()
        data = query.data or ""
        if data == self.MENU_MAIN:
            await self._send_main_menu(update, context, edit=True)
            self._clear_expectation(context)
        elif data == self.MENU_NALOG:
            await self._send_nalog_menu(update)
        elif data.startswith(self.NALOG_MODE_PREFIX):
            mode = data[len(self.NALOG_MODE_PREFIX) :]
            await self._ask_nalog_params(update, context, mode)
        elif data == self.MENU_WB:
            await self._send_wb_menu(update)
        elif data.startswith(self.WB_MODE_PREFIX):
            mode = data[len(self.WB_MODE_PREFIX) :]
            await self._handle_wb_button(update, context, mode)
        elif data == self.ACTION_IMAGE:
            self._set_expectation(context, "image")
            await self._send_instruction(update, "Отправьте изображение/фото документа для OCR.")
        elif data == self.ACTION_PDF:
            self._set_expectation(context, "pdf")
            await self._send_instruction(update, "Отправьте PDF-файл накладной/акта.")
        elif data == self.ACTION_ANALYTICS:
            self._set_expectation(context, "analytics")
            await self._send_instruction(
                update,
                "Отправьте JSON с заказами Wildberries (массив или объект с ключом orders).",
            )

    async def nalog(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        if len(context.args) < 2:
            await update.effective_message.reply_text(
                "Использование: /nalog <mode> <ИНН> [КПП]. Пример: /nalog company 7707083893 123456789"
            )
            return
        mode, inn, *rest = context.args
        kpp = rest[0] if rest else None
        await self._handle_nalog_request(update, mode, inn, kpp)

    async def wb(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        if len(context.args) < 2:
            await update.effective_message.reply_text(
                "Использование: /wb <mode> <dateFrom> [dateTo]. mode: orders|stocks|report"
            )
            return
        mode = context.args[0]
        date_from = context.args[1]
        date_to = context.args[2] if len(context.args) > 2 else None
        await self._handle_wb_request(update, mode, date_from=date_from, date_to=date_to)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        expectation = context.user_data.get(self.EXPECTATION_KEY)
        payload: Dict[str, Any] = context.user_data.get(self.EXPECTATION_PAYLOAD_KEY) or {}
        if not expectation:
            await update.effective_message.reply_text("Используйте кнопки меню ниже, чтобы выбрать действие.")
            await self._send_main_menu(update, context)
            return
        text = (update.effective_message.text or "").strip()
        if expectation == "nalog":
            mode = payload.get("mode")
            parts = text.split()
            if not parts:
                await update.effective_message.reply_text("Укажите ИНН и, при необходимости, КПП через пробел.")
                return
            inn = parts[0]
            kpp = parts[1] if len(parts) > 1 else None
            await self._handle_nalog_request(update, mode, inn, kpp)
            self._clear_expectation(context)
            await self._send_main_menu(update, context)
        elif expectation == "wb":
            mode = payload.get("mode")
            parts = text.split()
            if mode == "orders":
                if not parts:
                    await update.effective_message.reply_text("Отправьте дату начала в формате YYYY-MM-DD.")
                    return
                await self._handle_wb_request(update, mode, date_from=parts[0], status="all")
                self._clear_expectation(context)
                await self._send_main_menu(update, context)
            elif mode == "report":
                if len(parts) < 2:
                    await update.effective_message.reply_text("Нужны две даты: <с> <по> через пробел.")
                    return
                await self._handle_wb_request(update, mode, date_from=parts[0], date_to=parts[1])
                self._clear_expectation(context)
                await self._send_main_menu(update, context)
            else:
                await update.effective_message.reply_text("Неизвестный режим WB.")
        else:
            await update.effective_message.reply_text("Отправьте нужный файл или вернитесь в меню.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        expectation = context.user_data.get(self.EXPECTATION_KEY)
        if expectation != "image":
            await update.effective_message.reply_text(
                "Нажмите кнопку «Парсинг изображения», чтобы запустить OCR."
            )
            return
        photo = update.effective_message.photo[-1] if update.effective_message and update.effective_message.photo else None
        if not photo:
            return
        await self._process_image(update, context, photo.file_id, suffix=".jpg")
        self._clear_expectation(context)
        await self._send_main_menu(update, context)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._ensure_allowed(update):
            return
        document = update.effective_message.document if update.effective_message else None
        if not document:
            return
        expectation = context.user_data.get(self.EXPECTATION_KEY)
        suffix = Path(document.file_name or "").suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".bmp"}:
            if expectation != "image":
                await update.effective_message.reply_text(
                    "Нажмите кнопку «Парсинг изображения», чтобы отправить фото/скан."
                )
                return
            await self._process_image(update, context, document.file_id, suffix=suffix or ".jpg")
            self._clear_expectation(context)
            await self._send_main_menu(update, context)
        elif suffix == ".pdf":
            if expectation != "pdf":
                await update.effective_message.reply_text("Нажмите кнопку «Парсинг PDF» перед загрузкой файла.")
                return
            await self._process_pdf(update, context, document.file_id)
            self._clear_expectation(context)
            await self._send_main_menu(update, context)
        elif suffix == ".json":
            if expectation != "analytics":
                await update.effective_message.reply_text(
                    "Нажмите кнопку «Аналитика JSON», чтобы отправить файл заказов."
                )
                return
            await self._process_orders_json(update, context, document.file_id)
            self._clear_expectation(context)
            await self._send_main_menu(update, context)
        else:
            await update.effective_message.reply_text("Поддерживаются только изображения, PDF и JSON.")

    async def _ask_nalog_params(self, update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
        self._set_expectation(context, "nalog", mode=mode)
        examples = {
            "company": "Пример: 7707083893 123456789",
            "debt": "Пример: 7707083893",
            "statements": "Пример: 7707083893",
        }
        text = f"Режим ФНС: {mode}. Отправьте ИНН и, если нужно, КПП через пробел.\n{examples.get(mode, '')}"
        await self._send_instruction(update, text)

    async def _handle_wb_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
        if mode == "stocks":
            await self._handle_wb_request(update, mode)
            await self._send_main_menu(update, context, edit=False)
            return
        if mode == "orders":
            self._set_expectation(context, "wb", mode=mode)
            await self._send_instruction(update, "Режим: orders. Отправьте дату начала (YYYY-MM-DD).")
        elif mode == "report":
            self._set_expectation(context, "wb", mode=mode)
            await self._send_instruction(update, "Режим: report. Отправьте даты через пробел: <с> <по>.")
        else:
            await self._send_instruction(update, "Неизвестный режим WB.")

    async def _handle_nalog_request(
        self,
        update: Update,
        mode: str | None,
        inn: str,
        kpp: str | None,
    ) -> None:
        try:
            if mode == "company":
                payload = self.nalog_api.search_company(inn, kpp)
            elif mode == "debt":
                payload = self.nalog_api.fetch_tax_debt(inn)
            elif mode == "statements":
                from datetime import date, timedelta

                today = date.today()
                payload = self.nalog_api.fetch_statements(
                    inn,
                    date_from=today - timedelta(days=30),
                    date_to=today,
                )
            else:
                await update.effective_message.reply_text("Неизвестный режим ФНС.")
                return
        except Exception as exc:  # pragma: no cover - network interaction
            logger.exception("Nalog API error")
            await update.effective_message.reply_text(f"Ошибка запроса ФНС: {exc}")
            return
        await update.effective_message.reply_text(self._format_json(payload))

    async def _handle_wb_request(
        self,
        update: Update,
        mode: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str = "all",
        warehouse_id: int | None = None,
    ) -> None:
        try:
            if mode == "orders":
                if not date_from:
                    await update.effective_message.reply_text("Нужна дата начала.")
                    return
                payload = self.wb_api.get_orders(date_from, status)
            elif mode == "stocks":
                payload = self.wb_api.get_stocks(warehouse_id)
            elif mode == "report":
                if not (date_from and date_to):
                    await update.effective_message.reply_text("Нужны даты начала и конца.")
                    return
                payload = self.wb_api.get_detail_report(date_from, date_to)
            else:
                await update.effective_message.reply_text("Неизвестный режим WB.")
                return
        except Exception as exc:  # pragma: no cover - network interaction
            logger.exception("WB API error")
            await update.effective_message.reply_text(f"Ошибка запроса WB: {exc}")
            return
        await update.effective_message.reply_text(self._format_json(payload))

    async def _process_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str, suffix: str) -> None:
        await update.effective_message.reply_text("Обрабатываю изображение...")
        temp_path = await self._download_file(context, file_id, suffix)
        if not temp_path:
            await update.effective_message.reply_text("Не удалось скачать файл.")
            return
        try:
            payload = self.image_parser.parse_invoice(temp_path)
            await update.effective_message.reply_text(self._format_json(payload))
        except Exception as exc:
            logger.exception("Image parsing failed")
            await update.effective_message.reply_text(f"Ошибка OCR: {exc}")
        finally:
            temp_path.unlink(missing_ok=True)

    async def _process_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str) -> None:
        await update.effective_message.reply_text("Парсю PDF...")
        temp_path = await self._download_file(context, file_id, ".pdf")
        if not temp_path:
            await update.effective_message.reply_text("Не удалось скачать файл.")
            return
        try:
            payload = self.pdf_parser.parse_invoice(temp_path)
            await update.effective_message.reply_text(self._format_json(payload))
        except Exception as exc:
            logger.exception("PDF parsing failed")
            await update.effective_message.reply_text(f"Ошибка парсинга PDF: {exc}")
        finally:
            temp_path.unlink(missing_ok=True)

    async def _process_orders_json(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_id: str) -> None:
        await update.effective_message.reply_text("Запускаю аналитику заказов...")
        temp_path = await self._download_file(context, file_id, ".json")
        if not temp_path:
            await update.effective_message.reply_text("Не удалось скачать файл.")
            return
        try:
            orders_raw = json.loads(temp_path.read_text(encoding="utf-8"))
            if isinstance(orders_raw, dict):
                orders = orders_raw.get("orders") or orders_raw.get("data") or []
            else:
                orders = orders_raw
            if not isinstance(orders, Sequence):
                raise ValueError("JSON должен быть массивом заказов или содержать ключ 'orders'.")
            await self._run_analytics(update, orders)
        except Exception as exc:
            logger.exception("Analytics failed")
            await update.effective_message.reply_text(f"Ошибка аналитики: {exc}")
        finally:
            temp_path.unlink(missing_ok=True)

    async def _run_analytics(self, update: Update, orders: Sequence[dict]) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pipeline = AnalyticsPipeline(out_dir)
            df = pipeline.aggregate_orders(orders)
            anomalies_series = (
                pipeline.detect_anomalies(df["revenue"]) if "revenue" in df else pd.Series(dtype=float)
            )
            anomalies_df = (
                anomalies_series.reset_index()
                if not anomalies_series.empty
                else pd.DataFrame(columns=["index", "value"])
            )
            anomalies_path = out_dir / "anomalies.csv"
            anomalies_df.to_csv(anomalies_path, index=False)
            clusters_path = out_dir / "sku_clusters.csv"
            numeric_cols = df.select_dtypes(include="number").columns.tolist()
            feature_df = None
            if {"revenue", "quantity"}.issubset(df.columns):
                feature_df = df[["revenue", "quantity"]]
            elif numeric_cols:
                feature_df = df[numeric_cols]
            if feature_df is not None and len(feature_df) >= 3:
                pipeline.cluster_skus(feature_df)
            summary_lines = [
                f"Всего заказов: {len(orders)}",
                f"SKU в агрегировании: {len(df)}",
            ]
            if "revenue" in df:
                summary_lines.append(f"Суммарная выручка: {df['revenue'].sum():,.0f}")
            top_articles = df.sort_values("revenue", ascending=False).head(5) if "revenue" in df else df.head(5)
            summary_lines.append("Топ-5 артикулов:")
            for _, row in top_articles.iterrows():
                article = row.get("supplierArticle", "n/a")
                revenue = row.get("revenue", "n/a")
                qty = row.get("quantity", "n/a")
                summary_lines.append(f"- {article}: выручка {revenue}, шт {qty}")
            await update.effective_message.reply_text("\n".join(summary_lines))
            await self._send_file(update, out_dir / "orders_aggregate.csv", "orders_aggregate.csv")
            await self._send_file(update, anomalies_path, "anomalies.csv")
            if clusters_path.exists():
                await self._send_file(update, clusters_path, "sku_clusters.csv")

    async def _send_file(self, update: Update, path: Path, filename: str) -> None:
        if not path.exists():
            return
        with path.open("rb") as fh:
            await update.effective_message.reply_document(InputFile(fh, filename=filename))

    async def _download_file(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        file_id: str,
        suffix: str,
    ) -> Path | None:
        telegram_file = await context.bot.get_file(file_id)
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            await telegram_file.download_to_drive(custom_path=tmp.name)
            temp_path = Path(tmp.name)
        return temp_path

    async def _send_main_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *,
        text: str = "Выберите действие:",
        edit: bool = False,
    ) -> None:
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ФНС API", callback_data=self.MENU_NALOG),
                    InlineKeyboardButton("WB API", callback_data=self.MENU_WB),
                ],
                [
                    InlineKeyboardButton("Парсинг изображения", callback_data=self.ACTION_IMAGE),
                    InlineKeyboardButton("Парсинг PDF", callback_data=self.ACTION_PDF),
                ],
                [InlineKeyboardButton("Аналитика JSON", callback_data=self.ACTION_ANALYTICS)],
            ]
        )
        if edit and update.callback_query and update.callback_query.message:
            await update.callback_query.edit_message_text(text=text, reply_markup=markup)
        else:
            message = update.effective_message or (update.callback_query.message if update.callback_query else None)
            if message:
                await message.reply_text(text, reply_markup=markup)
            else:
                chat_id = update.effective_chat.id if update.effective_chat else None
                if chat_id:
                    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

    async def _send_nalog_menu(self, update: Update) -> None:
        query = update.callback_query
        if not query or not query.message:
            return
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Компания", callback_data=f"{self.NALOG_MODE_PREFIX}company"),
                    InlineKeyboardButton("Долги", callback_data=f"{self.NALOG_MODE_PREFIX}debt"),
                ],
                [InlineKeyboardButton("Отчётность", callback_data=f"{self.NALOG_MODE_PREFIX}statements")],
                [InlineKeyboardButton("⬅️ Назад", callback_data=self.MENU_MAIN)],
            ]
        )
        await query.edit_message_text("Выберите режим ФНС:", reply_markup=markup)

    async def _send_wb_menu(self, update: Update) -> None:
        query = update.callback_query
        if not query or not query.message:
            return
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Заказы", callback_data=f"{self.WB_MODE_PREFIX}orders"),
                    InlineKeyboardButton("Остатки", callback_data=f"{self.WB_MODE_PREFIX}stocks"),
                ],
                [InlineKeyboardButton("Фин. отчёт", callback_data=f"{self.WB_MODE_PREFIX}report")],
                [InlineKeyboardButton("⬅️ Назад", callback_data=self.MENU_MAIN)],
            ]
        )
        await query.edit_message_text("Выберите режим Wildberries:", reply_markup=markup)

    async def _send_instruction(self, update: Update, text: str) -> None:
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=self.MENU_MAIN)]])
        target = update.effective_message or (update.callback_query.message if update.callback_query else None)
        if target:
            await target.reply_text(text, reply_markup=markup)

    def _set_expectation(self, context: ContextTypes.DEFAULT_TYPE, expectation: str, **payload: Any) -> None:
        context.user_data[self.EXPECTATION_KEY] = expectation
        context.user_data[self.EXPECTATION_PAYLOAD_KEY] = payload

    def _clear_expectation(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        context.user_data.pop(self.EXPECTATION_KEY, None)
        context.user_data.pop(self.EXPECTATION_PAYLOAD_KEY, None)

    async def _ensure_allowed(self, update: Update) -> bool:
        if not self.allowed_users:
            return True
        user = update.effective_user
        if user and user.id in self.allowed_users:
            return True
        if update.effective_message:
            await update.effective_message.reply_text("Доступ запрещён. Добавьте свой chat_id в TELEGRAM_ALLOWED_USERS.")
        logger.warning("Unauthorized user tried to access bot: %s", user)
        return False

    @staticmethod
    def _format_json(payload: dict, limit: int = 3500) -> str:
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        return raw if len(raw) <= limit else raw[: limit - 3] + "..."


def build_bot_application(config: AppConfig) -> Application:
    if not config.telegram:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в окружении.")
    application = ApplicationBuilder().token(config.telegram.bot_token).build()
    bot = TelegramBot(config)
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("menu", bot.show_menu))
    application.add_handler(CommandHandler("nalog", bot.nalog))
    application.add_handler(CommandHandler("wb", bot.wb))
    application.add_handler(CallbackQueryHandler(bot.handle_menu_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    application.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    return application


def run_bot() -> None:
    config = AppConfig.load()
    application = build_bot_application(config)
    application.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
