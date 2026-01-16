from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    database_url: str = "sqlite:///./app.db"
    llm_api_key: str = "test"
    threads_topics: list[str] = ["ai", "startups"]
    sync_interval_seconds: int = 24 * 3600
    publish_interval_seconds: int = 3600

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
