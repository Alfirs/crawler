from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

import os


@dataclass(slots=True)
class APISettings:
    """Generic HTTP API connection settings."""

    base_url: str
    api_key: Optional[str] = None
    timeout: int = 15


@dataclass(slots=True)
class StorageSettings:
    data_dir: Path = Path("data")
    cache_dir: Path = Path("data/cache")


@dataclass(slots=True)
class TelegramSettings:
    bot_token: str
    allowed_user_ids: Tuple[int, ...] = ()


@dataclass(slots=True)
class AppConfig:
    """Container that gathers all configuration objects."""

    nalog_api: APISettings
    wb_api: APISettings
    storage: StorageSettings = field(default_factory=StorageSettings)
    telegram: Optional[TelegramSettings] = None

    @classmethod
    def load(cls, env_file: str | Path | None = ".env") -> "AppConfig":
        """Load configuration from environment variables or .env file."""
        if env_file and load_dotenv:
            load_dotenv(env_file)

        nalog_settings = APISettings(
            base_url=os.getenv("NALOG_API_URL", "https://api.nalog.ru"),
            api_key=os.getenv("NALOG_API_KEY"),
            timeout=int(os.getenv("NALOG_API_TIMEOUT", "15")),
        )

        wb_settings = APISettings(
            base_url=os.getenv("WB_API_URL", "https://suppliers-api.wildberries.ru"),
            api_key=os.getenv("WB_API_KEY"),
            timeout=int(os.getenv("WB_API_TIMEOUT", "15")),
        )

        storage = StorageSettings(
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            cache_dir=Path(os.getenv("CACHE_DIR", "data/cache")),
        )

        storage.data_dir.mkdir(parents=True, exist_ok=True)
        storage.cache_dir.mkdir(parents=True, exist_ok=True)

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        allowed_raw = os.getenv("TELEGRAM_ALLOWED_USERS", "")
        allowed_user_ids = tuple(
            int(item.strip())
            for item in allowed_raw.split(",")
            if item.strip()
        )
        telegram = None
        if telegram_token:
            telegram = TelegramSettings(bot_token=telegram_token, allowed_user_ids=allowed_user_ids)

        return cls(
            nalog_api=nalog_settings,
            wb_api=wb_settings,
            storage=storage,
            telegram=telegram,
        )
