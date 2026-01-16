from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import List, Optional

from pydantic import BaseModel, Field

# Default wheel definitions used when no storage file exists yet.
DEFAULT_WHEELS = [
    {
        "id": "wk-01",
        "name": "Modern Forged 19\"",
        "short_description": "modern forged multi-spoke 19 inch rims in brushed aluminum finish",
        "style_prompt": "modern forged multi-spoke 19 inch brushed aluminum rims",
        "preview_url": None,
    },
    {
        "id": "wk-02",
        "name": "Sport Mesh 20\"",
        "short_description": "aggressive 20 inch black mesh wheels with gloss lip",
        "style_prompt": "aggressive black mesh 20 inch wheels with glossy polished lip",
        "preview_url": None,
    },
    {
        "id": "wk-03",
        "name": "Classic Chrome 18\"",
        "short_description": "classic chrome plated 18 inch five-spoke wheels",
        "style_prompt": "classic chrome plated five-spoke 18 inch wheels",
        "preview_url": None,
    },
]


class Wheel(BaseModel):
    id: str
    name: str
    short_description: str = Field(..., description="Short plain-text description for overlays.")
    style_prompt: Optional[str] = Field(
        None, description="English description of the wheel style for AI prompts."
    )
    preview_url: Optional[str] = None


class WheelCreate(BaseModel):
    id: Optional[str] = None
    name: str
    short_description: str
    style_prompt: Optional[str] = None
    preview_url: Optional[str] = None


class WheelStore:
    """Simple wheel catalogue backed by JSON file for demo purposes."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = storage_path
        self._lock = Lock()
        self._wheels: dict[str, Wheel] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path and self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        else:
            data = DEFAULT_WHEELS
        for item in data:
            wheel = Wheel(**item)
            self._wheels[wheel.id] = wheel

    def _persist(self) -> None:
        if not self.storage_path:
            return
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump([wheel.model_dump() for wheel in self._wheels.values()], f, ensure_ascii=False, indent=2)

    def list_wheels(self) -> List[Wheel]:
        return list(self._wheels.values())

    def get_wheel(self, wheel_id: str) -> Optional[Wheel]:
        return self._wheels.get(wheel_id)

    def upsert_wheel(self, data: WheelCreate) -> Wheel:
        with self._lock:
            if data.id:
                wheel_id = data.id
            else:
                wheel_id = f"wheel-{len(self._wheels) + 1:03d}"
            wheel = Wheel(
                id=wheel_id,
                name=data.name,
                short_description=data.short_description,
                style_prompt=data.style_prompt or data.short_description,
                preview_url=data.preview_url,
            )
            self._wheels[wheel.id] = wheel
            self._persist()
            return wheel
