from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class TemplateMetadata:
    """Serializable representation of a carousel template."""

    name: str
    base_prompt: str
    slides_count: int
    style_ref: str
    username: str
    font: Optional[str] = None
    text_area: Optional[Dict[str, int]] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    auto_generate_daily: bool = False
    last_generated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TemplateMetadata":
        data = payload.copy()
        return cls(**data)

    def style_path(self) -> Path:
        return Path(self.style_ref)

    def mark_generated(self) -> None:
        self.last_generated_at = datetime.utcnow().isoformat()

