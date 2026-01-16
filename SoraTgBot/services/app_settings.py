from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from bot.config import Settings
from services.sqlite_storage import SQLiteStorage


@dataclass(slots=True)
class RuntimeSettings:
    """Resolved configuration that the pipeline should use."""

    neuroapi_api_key: str | None
    neuroapi_base_url: str
    neuroapi_model: str
    kie_api_key: str | None
    kie_api_base_url: str
    sora_aspect_ratio: str
    sora_n_frames: str
    sora_remove_watermark: bool
    default_generation_count: int


class AppSettingsService:
    """Manages user-editable settings stored in SQLite."""

    STORAGE_KEY = "runtime_settings_overrides"

    def __init__(self, sqlite_storage: SQLiteStorage, base_settings: Settings) -> None:
        self._sqlite = sqlite_storage
        self._base = base_settings

    async def _load_overrides(self) -> Dict[str, Any]:
        data = await self._sqlite.get_setting(self.STORAGE_KEY)
        return data if isinstance(data, dict) else {}

    async def _save_overrides(self, overrides: Dict[str, Any]) -> None:
        await self._sqlite.set_setting(self.STORAGE_KEY, overrides)

    async def get_runtime_settings(self) -> RuntimeSettings:
        overrides = await self._load_overrides()
        return RuntimeSettings(
            neuroapi_api_key=overrides.get("NEUROAPI_API_KEY", self._base.NEUROAPI_API_KEY),
            neuroapi_base_url=overrides.get("NEUROAPI_BASE_URL", self._base.NEUROAPI_BASE_URL),
            neuroapi_model=overrides.get("NEUROAPI_MODEL", self._base.NEUROAPI_MODEL),
            kie_api_key=overrides.get("KIE_API_KEY", self._base.KIE_API_KEY),
            kie_api_base_url=overrides.get("KIE_API_BASE_URL", self._base.KIE_API_BASE_URL),
            sora_aspect_ratio=overrides.get("SORA_ASPECT_RATIO", self._base.SORA_ASPECT_RATIO),
            sora_n_frames=overrides.get("SORA_N_FRAMES", self._base.SORA_N_FRAMES),
            sora_remove_watermark=bool(
                overrides.get("SORA_REMOVE_WATERMARK", self._base.SORA_REMOVE_WATERMARK)
            ),
            default_generation_count=int(overrides.get("DEFAULT_GENERATION_COUNT", 1)),
        )

    async def set_values(self, **values: Any) -> None:
        overrides = await self._load_overrides()
        changed = False
        for key, value in values.items():
            if value is None:
                if overrides.pop(key, None) is not None:
                    changed = True
            else:
                if overrides.get(key) != value:
                    overrides[key] = value
                    changed = True
        if changed:
            await self._save_overrides(overrides)

    async def describe(self) -> str:
        runtime = await self.get_runtime_settings()
        lines = [
            "Текущие настройки:",
            f"- NeuroAPI ключ: {'установлен' if runtime.neuroapi_api_key else 'не задан'}",
            f"- NeuroAPI модель: {runtime.neuroapi_model}",
            f"- Sora ключ: {'установлен' if runtime.kie_api_key else 'не задан'}",
            f"- Формат видео (aspect_ratio): {runtime.sora_aspect_ratio}",
            f"- Длительность (n_frames): {runtime.sora_n_frames}",
            f"- Водяной знак: {'убираем' if runtime.sora_remove_watermark else 'оставляем'}",
            f"- Дефолтное количество генераций: {runtime.default_generation_count}",
        ]
        return "\n".join(lines)

    async def get_default_generation_count(self) -> int:
        runtime = await self.get_runtime_settings()
        return runtime.default_generation_count
