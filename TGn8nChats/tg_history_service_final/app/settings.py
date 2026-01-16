import os
from functools import lru_cache

from pydantic import BaseModel


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


class Settings(BaseModel):
    tg_api_id: int
    tg_api_hash: str
    tg_session_string: str
    api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    data = {
        "tg_api_id": _clean(os.getenv("TG_API_ID")),
        "tg_api_hash": _clean(os.getenv("TG_API_HASH")),
        "tg_session_string": _clean(os.getenv("TG_SESSION_STRING")),
        "api_key": _clean(os.getenv("TG_HISTORY_API_KEY")),
    }
    return Settings(**data)
