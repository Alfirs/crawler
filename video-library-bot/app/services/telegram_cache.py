from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.db import db_session, utc_now_iso


class TelegramCacheService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def get_file_id(self, video_id: str) -> Optional[str]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute(
                "SELECT telegram_file_id FROM telegram_cache WHERE video_id = ?",
                (video_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_file_id(self, video_id: str, telegram_file_id: str) -> None:
        now = utc_now_iso()
        async with db_session(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO telegram_cache (video_id, telegram_file_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    telegram_file_id=excluded.telegram_file_id,
                    updated_at=excluded.updated_at
                """,
                (video_id, telegram_file_id, now),
            )
            await db.commit()
