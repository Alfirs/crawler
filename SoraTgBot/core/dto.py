from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.models import TaskStatus


@dataclass(slots=True)
class ProductFormData:
    """Temporary data collected while user fills out a product form."""

    image_path: Path | None = None
    image_file_id: str | None = None
    description: str | None = None


@dataclass(slots=True)
class ProductDraft(ProductFormData):
    """Completed product draft ready for task creation."""

    id: str = ""


@dataclass(slots=True)
class UserBatchConfig:
    """Global settings that apply to every product in the batch."""

    generation_count: int = 1
    ideas: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskSummary:
    """Compact info about a user's task for status listings."""

    id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    total: int
    done: int
    failed: int
    cancelled: int
