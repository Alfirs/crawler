from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from services.sqlite_storage import SQLiteStorage


NEURO_MODELS = ["gpt-5-mini", "gpt-4.1", "claude-3.5-sonnet"]
SORA_MODELS = ["sora-2-image-to-video", "sora-2-pro-image-to-video"]


@dataclass(slots=True)
class UserSettings:
    user_id: str
    sora_api_key: Optional[str] = None
    sora_model: Optional[str] = None
    neuro_api_key: Optional[str] = None
    neuro_model: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserSettingsRepository:
    """Persistence layer for per-user model/API settings."""

    def __init__(self, sqlite_storage: SQLiteStorage) -> None:
        self._db_path: Path = sqlite_storage.db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    sora_api_key TEXT,
                    sora_model TEXT,
                    neuro_api_key TEXT,
                    neuro_model TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def get(self, user_id: int | str | None) -> Optional[UserSettings]:
        if user_id is None:
            return None
        user_id = str(user_id)
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT user_id, sora_api_key, sora_model, neuro_api_key, neuro_model,
                       created_at, updated_at
                FROM user_settings
                WHERE user_id = ?
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return UserSettings(
            user_id=row["user_id"],
            sora_api_key=row["sora_api_key"],
            sora_model=row["sora_model"],
            neuro_api_key=row["neuro_api_key"],
            neuro_model=row["neuro_model"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    async def update_settings(self, user_id: int | str, **fields: Optional[str]) -> None:
        user_id = str(user_id)
        filtered = {k: v for k, v in fields.items() if k in {"sora_api_key", "sora_model", "neuro_api_key", "neuro_model"}}
        if not filtered:
            return
        now = _now_iso()
        sets = ", ".join(f"{column} = ?" for column in filtered)
        params = list(filtered.values()) + [now, user_id]
        async with aiosqlite.connect(self._db_path) as db:
            await self._ensure_row(db, user_id)
            await db.execute(
                f"""
                UPDATE user_settings
                SET {sets}, updated_at = ?
                WHERE user_id = ?
                """,
                params,
            )
            await db.commit()

    async def _ensure_row(self, db: aiosqlite.Connection, user_id: str) -> None:
        now = _now_iso()
        await db.execute(
            """
            INSERT INTO user_settings (user_id, created_at, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, now, now),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)
