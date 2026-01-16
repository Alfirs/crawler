from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.db import db_session, dumps_json, utc_now_iso
from app.models import StorageEntry, VideoMeta, VideoRecord, VideoStatus


class CatalogService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def upsert_entry(self, entry: StorageEntry, status: VideoStatus | None = None) -> None:
        status = status or self._derive_status(entry.meta)
        now = utc_now_iso()
        tags_json = dumps_json(entry.meta.tags)
        text_paths_json = dumps_json(entry.meta.text_paths)
        fingerprint_json = dumps_json(entry.fingerprint.payload)
        if status == VideoStatus.ERROR:
            error_code = entry.error_code or "UNKNOWN"
            error_message = entry.error_message or "unspecified error"
        else:
            error_code = None
            error_message = None

        async with db_session(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO videos (
                    video_id,
                    title,
                    disk_folder,
                    video_path,
                    summary_path,
                    transcript_path,
                    text_paths_json,
                    tags_json,
                    lang,
                    status,
                    fingerprint_json,
                    updated_at,
                    error_code,
                    error_message,
                    telegram_file_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    disk_folder=excluded.disk_folder,
                    video_path=excluded.video_path,
                    summary_path=excluded.summary_path,
                    transcript_path=excluded.transcript_path,
                    text_paths_json=excluded.text_paths_json,
                    tags_json=excluded.tags_json,
                    lang=excluded.lang,
                    status=excluded.status,
                    fingerprint_json=excluded.fingerprint_json,
                    updated_at=excluded.updated_at,
                    error_code=excluded.error_code,
                    error_message=excluded.error_message,
                    telegram_file_id=COALESCE(excluded.telegram_file_id, telegram_file_id)
                """,
                (
                    entry.meta.id,
                    entry.meta.title,
                    entry.folder,
                    entry.meta.video_path,
                    entry.meta.summary_path,
                    entry.meta.transcript_path,
                    text_paths_json,
                    tags_json,
                    entry.meta.lang,
                    status.value,
                    fingerprint_json,
                    now,
                    error_code,
                    error_message,
                    entry.telegram_file_id,
                ),
            )
            await db.commit()

    async def list_video_ids(self) -> list[str]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute("SELECT video_id FROM videos")
            rows = await cursor.fetchall()
            return [row["video_id"] for row in rows]

    async def list_all_videos(self) -> list[VideoRecord]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute("SELECT * FROM videos")
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    async def list_video_index(self) -> dict[str, dict[str, str | None]]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute(
                "SELECT video_id, fingerprint_json, status, disk_folder FROM videos"
            )
            rows = await cursor.fetchall()
            return {
                row["video_id"]: {
                    "fingerprint_json": row["fingerprint_json"],
                    "status": row["status"],
                    "disk_folder": row["disk_folder"],
                }
                for row in rows
            }

    async def mark_deleted(self, video_ids: list[str]) -> None:
        if not video_ids:
            return
        now = utc_now_iso()
        async with db_session(self._db_path) as db:
            await db.executemany(
                "UPDATE videos SET status = ?, updated_at = ? WHERE video_id = ?",
                [(VideoStatus.DELETED.value, now, video_id) for video_id in video_ids],
            )
            await db.commit()

    async def get_video(self, video_id: str) -> Optional[VideoRecord]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    async def get_status_counts(self) -> dict[str, int]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) as cnt FROM videos GROUP BY status"
            )
            rows = await cursor.fetchall()
            return {row["status"]: int(row["cnt"]) for row in rows}

    @staticmethod
    def _derive_status(meta: VideoMeta) -> VideoStatus:
        if not meta.video_path:
            return VideoStatus.ERROR
        if not meta.text_paths and not meta.summary_path and not meta.transcript_path:
            return VideoStatus.NEEDS_TEXT
        return VideoStatus.READY

    async def update_telegram_file_id(self, video_id: str, telegram_file_id: str) -> None:
        now = utc_now_iso()
        async with db_session(self._db_path) as db:
            await db.execute(
                """
                UPDATE videos
                SET telegram_file_id = ?, updated_at = ?
                WHERE video_id = ?
                """,
                (telegram_file_id, now, video_id),
            )
            await db.commit()

    async def list_recent_errors(self, limit: int = 5) -> list[VideoRecord]:
        async with db_session(self._db_path) as db:
            cursor = await db.execute(
                """
                SELECT * FROM videos
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (VideoStatus.ERROR.value, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_record(row) for row in rows]

    @staticmethod
    def _row_to_record(row) -> VideoRecord:
        try:
            status = VideoStatus(row["status"])
        except ValueError:
            status = VideoStatus.ERROR
        return VideoRecord(
            video_id=row["video_id"],
            title=row["title"],
            disk_folder=row["disk_folder"],
            video_path=row["video_path"],
            summary_path=row["summary_path"],
            transcript_path=row["transcript_path"],
            text_paths_json=row["text_paths_json"] or "[]",
            tags_json=row["tags_json"],
            lang=row["lang"],
            status=status,
            fingerprint_json=row["fingerprint_json"],
            updated_at=row["updated_at"],
            error_code=row["error_code"] if "error_code" in row.keys() else None,
            error_message=row["error_message"] if "error_message" in row.keys() else None,
            telegram_file_id=row["telegram_file_id"],
        )
