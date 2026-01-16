from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class VideoStatus(str, Enum):
    READY = "READY"
    NEEDS_TEXT = "NEEDS_TEXT"
    ERROR = "ERROR"
    DELETED = "DELETED"


class VideoMeta(BaseModel):
    id: Optional[str] = None
    title: str = ""
    video_path: str = ""
    summary_path: Optional[str] = None
    transcript_path: Optional[str] = None
    text_paths: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    lang: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class Fingerprint:
    payload: dict[str, Any]


@dataclass(frozen=True)
class StorageEntry:
    folder: str
    meta: VideoMeta
    fingerprint: Fingerprint
    telegram_file_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class VideoRecord:
    video_id: str
    title: str
    disk_folder: str
    video_path: str
    summary_path: Optional[str]
    transcript_path: Optional[str]
    text_paths_json: str
    tags_json: str
    lang: Optional[str]
    status: VideoStatus
    fingerprint_json: str
    updated_at: str
    error_code: Optional[str]
    error_message: Optional[str]
    telegram_file_id: Optional[str]


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    video_id: str
    text: str
    start_sec: Optional[int]
    end_sec: Optional[int]


@dataclass(frozen=True)
class TelegramCacheRecord:
    video_id: str
    telegram_file_id: str
    updated_at: str


# --- Search Contract (Step 2) ---

@dataclass(frozen=True)
class SearchHit:
    """Single search result for a video."""
    rank: int
    video_id: str
    title: str
    score: float
    snippet: str = ""
    source_text_type: str = ""
    start_sec: Optional[int] = None
    end_sec: Optional[int] = None


@dataclass
class SearchResponse:
    """Response from IndexService.search()."""
    query: str
    threshold: float
    low_confidence: bool
    results: list[SearchHit] = field(default_factory=list)
