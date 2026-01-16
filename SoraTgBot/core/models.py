from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class GenerationStatus(str, Enum):
    """Lifecycle statuses for video generation subtasks."""

    PENDING = "pending"
    SCRIPT_GENERATING = "script_generating"
    VIDEO_GENERATING = "video_generating"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """High-level status for the whole task."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Product:
    """Product card uploaded by the user."""

    id: str
    title: str
    short_description: str | None = None
    image_path: Path | None = None
    image_file_id: str | None = None


@dataclass(slots=True)
class Idea:
    """Creative hint that defines the scenario style."""

    id: str
    text: str


@dataclass(slots=True)
class SubTask:
    """Single combination of product x idea."""

    id: str
    product: Product
    idea: Idea
    n_generations: int
    status: GenerationStatus = GenerationStatus.PENDING
    script_text: str | None = None
    job_id: str | None = None
    record_id: str | None = None
    result_urls: list[str] = field(default_factory=list)
    result_payload: dict[str, Any] | None = None
    downloaded_files: list[str] = field(default_factory=list)
    last_error: str | None = None
    script_attempts: int = 0
    video_attempts: int = 0


@dataclass
class Task:
    """Batch of subtasks created by the user."""

    id: str
    subtasks: list[SubTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    owner_user_id: int | str | None = None
    status: TaskStatus = TaskStatus.PENDING
