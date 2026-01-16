from __future__ import annotations

from typing import Optional

from app.config import Config
from app.yclients_api import YclientsAPI

_config: Optional[Config] = None
_api_client: Optional[YclientsAPI] = None


def set_context(config: Config, api_client: YclientsAPI) -> None:
    global _config, _api_client
    _config = config
    _api_client = api_client


def get_config() -> Config:
    if _config is None:
        raise RuntimeError("Config is not initialized")
    return _config


def get_api_client() -> YclientsAPI:
    if _api_client is None:
        raise RuntimeError("YclientsAPI is not initialized")
    return _api_client
