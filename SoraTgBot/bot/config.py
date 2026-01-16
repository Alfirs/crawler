from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables from .env if present.
load_dotenv()


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    TELEGRAM_BOT_TOKEN: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    NEUROAPI_API_KEY: str | None = Field(default=None, env="NEUROAPI_API_KEY")
    NEUROAPI_BASE_URL: str = Field(
        default="https://api.neuroapi.dev/v1",
        env="NEUROAPI_BASE_URL",
    )
    NEUROAPI_MODEL: str = Field(default="gpt-5-mini", env="NEUROAPI_MODEL")
    KIE_API_KEY: str | None = Field(default=None, env="KIE_API_KEY")
    KIE_API_BASE_URL: str = Field(
        default="https://api.kie.ai/api/v1",
        env="KIE_API_BASE_URL",
    )
    SORA_ASPECT_RATIO: str = Field(default="portrait", env="SORA_ASPECT_RATIO")
    SORA_N_FRAMES: str = Field(default="15", env="SORA_N_FRAMES")
    SORA_REMOVE_WATERMARK: bool = Field(default=True, env="SORA_REMOVE_WATERMARK")
    SORA_MODEL: str = Field(default="sora-2-image-to-video", env="SORA_MODEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
