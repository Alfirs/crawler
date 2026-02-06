from __future__ import annotations

import asyncio
import logging

from app.bot import build_bot
from app.config import load_config
from app.domain.rates import RatesStore
from app.domain.search import SearchService
from app.flow.detectors import InputDetector, build_log_hints
from app.flow.engine import FlowEngine
from app.flow.loader import load_artifacts
from app.storage.db import Database
from app.storage.repo import SessionRepository


async def main() -> None:
    config = load_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    artifacts = load_artifacts(config.input_dir)
    log_hints = build_log_hints(artifacts.raw_log)
    detector = InputDetector(log_hints)

    rates_store = RatesStore.load(config.rates_path)
    db = Database(config.db_url)
    db.initialize()

    # Initialize Search Service (with DB)
    search_service = SearchService(db, config)
    # Optional: Ingest data if implementation plan requires it during startup
    # search_service.ingest_data("tnved_data.json")

    repo = SessionRepository(db)
    engine = FlowEngine(
        bot_map=artifacts.bot_map,
        detector=detector,
        rates_store=rates_store,
        default_keyboard_mode=config.default_keyboard_mode,
        raw_log=artifacts.raw_log,
        search_service=search_service,
    )

    bot, dispatcher = build_bot(
        engine=engine,
        repo=repo,
        rates_store=rates_store,
        config=config,
    )

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
