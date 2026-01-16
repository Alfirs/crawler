from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bot.config import Settings
from services.user_settings import UserSettingsRepository


@dataclass(slots=True)
class EffectiveNeuroConfig:
    api_key: Optional[str]
    base_url: str
    model: str


@dataclass(slots=True)
class EffectiveSoraConfig:
    api_key: Optional[str]
    base_url: str
    model: str
    aspect_ratio: str
    n_frames: str
    remove_watermark: bool


class UserConfigService:
    """Resolves per-user configuration with global fallbacks."""

    def __init__(self, repo: UserSettingsRepository, settings: Settings) -> None:
        self._repo = repo
        self._settings = settings

    @property
    def global_neuro_api_key(self) -> Optional[str]:
        return self._settings.NEUROAPI_API_KEY

    @property
    def global_sora_api_key(self) -> Optional[str]:
        return self._settings.KIE_API_KEY

    async def get_neuro_config(self, user_id: int | str | None) -> EffectiveNeuroConfig:
        user_settings = await self._repo.get(user_id)
        api_key = (user_settings.neuro_api_key if user_settings else None) or self._settings.NEUROAPI_API_KEY
        model = (user_settings.neuro_model if user_settings else None) or self._settings.NEUROAPI_MODEL
        return EffectiveNeuroConfig(
            api_key=api_key,
            base_url=self._settings.NEUROAPI_BASE_URL,
            model=model,
        )

    async def get_sora_config(self, user_id: int | str | None) -> EffectiveSoraConfig:
        user_settings = await self._repo.get(user_id)
        api_key = (user_settings.sora_api_key if user_settings else None) or self._settings.KIE_API_KEY
        model = (user_settings.sora_model if user_settings else None) or self._settings.SORA_MODEL
        return EffectiveSoraConfig(
            api_key=api_key,
            base_url=self._settings.KIE_API_BASE_URL,
            model=model,
            aspect_ratio=self._settings.SORA_ASPECT_RATIO,
            n_frames=self._settings.SORA_N_FRAMES,
            remove_watermark=self._settings.SORA_REMOVE_WATERMARK,
        )
