from __future__ import annotations

import hashlib
from typing import Tuple

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.admin.commands import register_admin_handlers
from app.config import AppConfig
from app.domain.rates import RatesStore
from app.flow.engine import EngineResponse, FlowEngine, KeyboardType, RenderedScreen
from app.flow.loader import ActionType, Button
from app.storage.models import InteractionLog, SessionState
from app.storage.repo import SessionRepository


def build_bot(
    engine: FlowEngine,
    repo: SessionRepository,
    rates_store: RatesStore,
    config: AppConfig,
) -> tuple[Bot, Dispatcher]:
    bot = Bot(token=config.bot_token)
    dispatcher = Dispatcher()
    router = Router()

    register_admin_handlers(router, repo, rates_store, config)
    _register_flow_handlers(router, engine, repo, rates_store)

    dispatcher.include_router(router)
    return bot, dispatcher


def _register_flow_handlers(
    router: Router,
    engine: FlowEngine,
    repo: SessionRepository,
    rates_store: RatesStore,
) -> None:
    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        session = engine.start_session(message.from_user.id)
        rendered = await engine.render(session.current_node_id)
        await _send_rendered(message, rendered, session, repo)
        await repo.log_interaction(
            InteractionLog(
                user_id=message.from_user.id,
                node_id=rendered.node_id,
                user_message="/start",
                bot_message=rendered.text,
                chosen_action="/start",
            )
        )
        print(f"\n🟢 USER START: /start")
        print(f"🤖 BOT REPLY ({rendered.node_id}):\n{rendered.text}")
        if rendered.buttons:
            import json
            btns = [b.text for row in rendered.buttons for b in row]
            print(f"   BUTTONS: {btns}")

    @router.callback_query()
    async def callback_handler(query: CallbackQuery) -> None:
        print(f"DEBUG: Callback received: {query.data}")
        if not query.from_user:
            return
        session = await repo.get_or_create_session(query.from_user.id, engine.root_node_id)
        action_value = session.last_buttons.get(query.data or "", query.data or "")
        
        print(f"\n👇 USER CLICK: '{action_value}' (data={query.data})")
        
        response = await engine.handle_action(session, ActionType.CLICK, action_value)
        await query.answer()
        await _process_response(query.message, response, repo)

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        text = (
            "🛠 **Справка:**\n\n"
            "• **/start** — Сброс и переход в главное меню\n"
            "• **/rates** — Текущие курсы валют (USD/CNY)\n"
            "• **/example** — Пример кода ТНВЭД для теста\n"
            "• **Поиск** — Просто пришлите название товара (напр. 'рюкзак') или код (10 цифр).\n"
        )
        await message.answer(text)

    @router.message(Command("example"))
    async def example_handler(message: Message) -> None:
        await message.answer("Попробуйте ввести код: `9503009500` (Игрушки) или просто напишите 'кроссовки'.")

    @router.message(Command("rates"))
    async def rates_handler(message: Message) -> None:
        await message.answer(rates_store.render())

    @router.message(Command("reset"))
    async def reset_handler(message: Message) -> None:
        session = engine.start_session(message.from_user.id)
        rendered = await engine.render(session.current_node_id)
        await _send_rendered(message, rendered, session, repo)

    @router.message()
    async def text_handler(message: Message) -> None:
        print(f"DEBUG: Text received: {message.text}")
        if not message.text:
            return
        print(f"\n📩 USER TEXT: {message.text}")
        session = await repo.get_or_create_session(message.from_user.id, engine.root_node_id)
        response = await engine.handle_action(session, ActionType.SEND_TEXT, message.text)
        await _process_response(message, response, repo)


def _build_inline_keyboard(
    buttons: list[list[Button]],
) -> Tuple[InlineKeyboardMarkup, dict[str, str]]:
    rows: list[list[InlineKeyboardButton]] = []
    mapping: dict[str, str] = {}
    for r_idx, row in enumerate(buttons):
        row_buttons: list[InlineKeyboardButton] = []
        for c_idx, btn in enumerate(row):
            if btn.url:
                row_buttons.append(InlineKeyboardButton(text=btn.text, url=btn.url))
                continue
            callback_data = _make_callback_id(btn.text, r_idx, c_idx)
            mapping[callback_data] = btn.text
            row_buttons.append(
                InlineKeyboardButton(text=btn.text, callback_data=callback_data)
            )
        rows.append(row_buttons)
    return InlineKeyboardMarkup(inline_keyboard=rows), mapping


def _build_reply_keyboard(buttons: list[list[Button]]) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    for row in buttons:
        rows.append([KeyboardButton(text=btn.text) for btn in row])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def _make_callback_id(text: str, row: int, col: int) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"b{row}_{col}_{digest}"


def _build_markup(
    rendered: RenderedScreen,
) -> tuple[object | None, dict[str, str]]:
    if rendered.keyboard == KeyboardType.NONE:
        return ReplyKeyboardRemove(), {}
    if rendered.keyboard == KeyboardType.REPLY:
        return _build_reply_keyboard(rendered.buttons), {}
    markup, mapping = _build_inline_keyboard(rendered.buttons)
    return markup, mapping


def _build_log(
    session: SessionState,
    response: EngineResponse,
) -> InteractionLog:
    return InteractionLog(
        user_id=session.user_id,
        node_id=response.rendered.node_id,
        user_message=str(response.action_value or ""),
        bot_message=response.rendered.text,
        chosen_action=str(response.action_value or ""),
    )


async def _send_rendered(
    message: Message,
    rendered: RenderedScreen,
    session: SessionState,
    repo: SessionRepository,
) -> None:
    markup, mapping = _build_markup(rendered)
    session.last_buttons = mapping
    session.current_node_id = rendered.node_id
    await repo.save_session(session)
    await message.answer(rendered.text, reply_markup=markup)
    
    print(f"🤖 BOT REPLY ({rendered.node_id}):\n{rendered.text}")
    if rendered.buttons:
        btns = [b.text for row in rendered.buttons for b in row]
        print(f"   BUTTONS: {btns}")


async def _process_response(
    message: Message | None,
    response: EngineResponse,
    repo: SessionRepository,
) -> None:
    if message is None:
        return
    session = response.session

    for hint in response.hints:
        await message.answer(hint)

    if response.transitioned:
        await _send_rendered(message, response.rendered, session, repo)
        for extra in response.extra_messages:
            await message.answer(extra)
    else:
        for extra in response.extra_messages:
            await message.answer(extra)
        await _send_rendered(message, response.rendered, session, repo)

    await repo.log_interaction(_build_log(session, response))
