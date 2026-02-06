from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    bot_token: str
    db_url: str
    admin_ids: set[int]
    input_dir: Path
    rates_path: Path
    default_keyboard_mode: str
    log_level: str
    
    # NeuroAPI / LLM config
    llm_provider: str | None = None
    llm_mode: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str | None = None
    openrouter_model: str | None = None


def load_config() -> AppConfig:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN is not set")

    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    admin_ids = {int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()}

    return AppConfig(
        bot_token=bot_token,
        db_url=os.getenv("DB_URL", "sqlite:///clone.db"),
        admin_ids=admin_ids,
        input_dir=Path(os.getenv("INPUT_DIR", "input")),
        rates_path=Path(os.getenv("RATES_PATH", "rates.yaml")),
        default_keyboard_mode=os.getenv("DEFAULT_KEYBOARD_MODE", "reply"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        
        llm_provider=os.getenv("LLM_PROVIDER"),
        llm_mode=os.getenv("LLM_MODE"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL"),
        openrouter_model=os.getenv("OPENROUTER_MODEL"),
    )
