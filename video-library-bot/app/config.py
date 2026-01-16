from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    telegram_bot_token: str = Field("", alias="TELEGRAM_BOT_TOKEN")
    admin_user_ids: List[int] = Field(default_factory=list, alias="ADMIN_USER_IDS")
    yandex_disk_oauth_token: str = Field("", alias="YANDEX_DISK_OAUTH_TOKEN")
    yandex_disk_root: str = Field("/VideoLibrary", alias="YANDEX_DISK_ROOT")
    scan_interval_sec: int = Field(300, alias="SCAN_INTERVAL_SEC")
    stability_check_sec: int = Field(30, alias="STABILITY_CHECK_SEC")
    sim_threshold: float = Field(0.30, alias="SIM_THRESHOLD")
    lexical_boost: float = Field(0.15, alias="LEXICAL_BOOST")
    top_k: int = Field(3, alias="TOP_K")
    max_telegram_upload_mb: int = Field(45, alias="MAX_TELEGRAM_UPLOAD_MB")
    telegram_send_max_mb: int = Field(45, alias="TELEGRAM_SEND_MAX_MB")
    auto_meta_mode: str = Field("write", alias="AUTO_META_MODE")
    enable_transcription: bool = Field(False, alias="ENABLE_TRANSCRIPTION")
    transcribe_model: str = Field("small", alias="TRANSCRIBE_MODEL")
    seed_sample_video_path: str = Field("", alias="SEED_SAMPLE_VIDEO_PATH")
    chaos_mode: bool = Field(False, alias="CHAOS_MODE")
    chaos_rate: float = Field(0.15, alias="CHAOS_RATE")
    max_storage_concurrency: int = Field(5, alias="MAX_STORAGE_CONCURRENCY")
    max_download_concurrency: int = Field(1, alias="MAX_DOWNLOAD_CONCURRENCY")
    data_dir: Path = Field(Path("./data"), alias="DATA_DIR")

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def parse_admin_user_ids(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("auto_meta_mode", mode="before")
    @classmethod
    def normalize_auto_meta_mode(cls, value: str) -> str:
        if not value:
            return "write"
        value = str(value).strip().lower()
        if value not in {"write", "derive", "off"}:
            return "write"
        return value

    @field_validator("enable_transcription", mode="before")
    @classmethod
    def parse_enable_transcription(cls, value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @field_validator("chaos_mode", mode="before")
    @classmethod
    def parse_chaos_mode(cls, value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return False
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @field_validator("chaos_rate", mode="before")
    @classmethod
    def clamp_chaos_rate(cls, value) -> float:
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return 0.15
        if rate < 0:
            return 0.0
        if rate > 1:
            return 1.0
        return rate

    @field_validator("max_storage_concurrency", "max_download_concurrency", mode="before")
    @classmethod
    def clamp_concurrency(cls, value) -> int:
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return 1
        return max(1, min(limit, 32))

    @field_validator("lexical_boost", mode="before")
    @classmethod
    def clamp_lexical_boost(cls, value) -> float:
        try:
            boost = float(value)
        except (TypeError, ValueError):
            return 0.15
        if boost < 0:
            return 0.0
        if boost > 0.35:
            return 0.35
        return boost

    @property
    def db_path(self) -> Path:
        return self.data_dir / "video_library.db"

    @property
    def effective_telegram_send_mb(self) -> int:
        if "telegram_send_max_mb" in self.model_fields_set:
            return self.telegram_send_max_mb
        if "max_telegram_upload_mb" in self.model_fields_set:
            return self.max_telegram_upload_mb
        return self.telegram_send_max_mb

    @property
    def max_telegram_upload_bytes(self) -> int:
        return self.effective_telegram_send_mb * 1024 * 1024
