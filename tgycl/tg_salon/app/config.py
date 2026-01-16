from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.yclients.com/api/v1"


class ConfigError(RuntimeError):
    """Raised when mandatory environment values are missing or invalid."""


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Config:
    bot_token: str
    partner_token: str
    user_token: str
    company_id: int
    about_text: str
    salon_address: str
    salon_lat: float
    salon_lon: float
    base_url: str = DEFAULT_BASE_URL
    strict_v2: bool = True

    @property
    def location(self) -> tuple[float, float]:
        return self.salon_lat, self.salon_lon


def _require(value: Optional[str], name: str) -> str:
    if not value:
        raise ConfigError(f"Environment variable {name} is required")
    return value


def load_config(env_file: str | Path | None = None) -> Config:
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    bot_token = _require(os.getenv("BOT_TOKEN"), "BOT_TOKEN")
    partner_token = _require(os.getenv("YCLIENTS_PARTNER_TOKEN"), "YCLIENTS_PARTNER_TOKEN")
    user_token = _require(os.getenv("YCLIENTS_USER_TOKEN"), "YCLIENTS_USER_TOKEN")

    company_raw = _require(os.getenv("YCLIENTS_COMPANY_ID"), "YCLIENTS_COMPANY_ID")
    try:
        company_id = int(company_raw)
    except ValueError as exc:
        raise ConfigError("YCLIENTS_COMPANY_ID must be an integer") from exc

    about_text = _require(os.getenv("ABOUT_TEXT"), "ABOUT_TEXT")
    salon_address = _require(os.getenv("SALON_ADDRESS"), "SALON_ADDRESS")

    try:
        salon_lat = float(_require(os.getenv("SALON_LAT"), "SALON_LAT"))
        salon_lon = float(_require(os.getenv("SALON_LON"), "SALON_LON"))
    except ValueError as exc:
        raise ConfigError("SALON_LAT and SALON_LON must be floats") from exc

    base_url = os.getenv("YCLIENTS_BASE_URL", DEFAULT_BASE_URL)
    strict_v2 = _env_bool(os.getenv("YCLIENTS_STRICT_V2"), default=True)

    return Config(
        bot_token=bot_token,
        partner_token=partner_token,
        user_token=user_token,
        company_id=company_id,
        about_text=about_text,
        salon_address=salon_address,
        salon_lat=salon_lat,
        salon_lon=salon_lon,
        base_url=base_url.rstrip("/"),
        strict_v2=strict_v2,
    )
