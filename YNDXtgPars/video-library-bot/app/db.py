from __future__ import annotations

import json
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY,
        title TEXT,
        disk_folder TEXT,
        video_path TEXT,
        summary_path TEXT,
        transcript_path TEXT,
        text_paths_json TEXT,
        tags_json TEXT,
        lang TEXT,
        status TEXT,
        fingerprint_json TEXT,
        updated_at TEXT,
        error_code TEXT,
        error_message TEXT,
        telegram_file_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chunks (
        chunk_id TEXT PRIMARY KEY,
        video_id TEXT,
        text TEXT,
        start_sec INTEGER NULL,
        end_sec INTEGER NULL,
        source TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_state (
        video_id TEXT PRIMARY KEY,
        fingerprint_json TEXT,
        indexed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS telegram_cache (
        video_id TEXT PRIMARY KEY,
        telegram_file_id TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scan_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scanned_at TEXT,
        ready_count INTEGER,
        needs_text_count INTEGER,
        error_count INTEGER,
        deleted_count INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS callback_tokens (
        token TEXT PRIMARY KEY,
        video_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        backup_path = db_path.with_suffix(db_path.suffix + ".bak")
        try:
            shutil.copy2(db_path, backup_path)
        except OSError as exc:
            raise RuntimeError(f"DB backup failed: {exc}") from exc
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        for statement in SCHEMA_STATEMENTS:
            await db.execute(statement)
        try:
            await _ensure_columns(db)
        except Exception as exc:
            raise RuntimeError(f"DB migration failed: {exc}") from exc
        await db.commit()


async def _ensure_columns(db: aiosqlite.Connection) -> None:
    await _ensure_table_columns(
        db,
        "videos",
        {
            "text_paths_json": "text_paths_json TEXT",
            "telegram_file_id": "telegram_file_id TEXT",
            "error_code": "error_code TEXT",
            "error_message": "error_message TEXT",
        },
    )
    await _ensure_table_columns(
        db,
        "chunks",
        {"source": "source TEXT"},
    )


async def _ensure_table_columns(
    db: aiosqlite.Connection, table: str, columns: dict[str, str]
) -> None:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    existing = {row[1] for row in rows}
    for name, ddl in columns.items():
        if name in existing:
            continue
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


@asynccontextmanager
async def db_session(db_path: Path):
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys=ON;")
    try:
        yield db
    finally:
        await db.close()


def dumps_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False)
