from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Iterable, Sequence
from uuid import uuid4

import aiosqlite

from core.dto import ProductDraft, TaskSummary, UserBatchConfig
from core.models import GenerationStatus, Idea, Product, SubTask, Task, TaskStatus

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"


def _serialize_dt(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime(ISO_FORMAT)


def _deserialize_dt(value: str) -> datetime:
    # Stored as UTC with offset +0000; fallback to fromisoformat if needed.
    try:
        return datetime.strptime(value, ISO_FORMAT)
    except ValueError:
        return datetime.fromisoformat(value)


class SQLiteStorage:
    """
    Lightweight repository over SQLite used for drafts, configs, and queued tasks.

    The class is asynchronous and safe to share across the app. All methods
    ensure PRAGMA foreign_keys=ON per connection.
    """

    def __init__(self, db_path: str | Path = Path("storage") / "app.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self) -> None:
        """Create tables if they do not exist."""
        async with self._connect() as db:
            await db.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS product_drafts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    description TEXT,
                    image_path TEXT,
                    image_file_id TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS batch_configs (
                    user_id TEXT PRIMARY KEY,
                    generation_count INTEGER NOT NULL DEFAULT 1,
                    ideas TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    owner_user_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS subtasks (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    product_id TEXT NOT NULL,
                    product_title TEXT NOT NULL,
                    product_description TEXT,
                    product_image_path TEXT,
                    product_image_file_id TEXT,
                    idea TEXT NOT NULL,
                    generation_index INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    script_text TEXT,
                    job_id TEXT,
                    record_id TEXT,
                    result_json TEXT,
                    downloaded_files TEXT,
                    last_error TEXT,
                    script_attempts INTEGER NOT NULL DEFAULT 0,
                    video_attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS worker_queue (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    enqueued_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events (task_id, created_at);
                """
            )
            await self._ensure_column(db, "subtasks", "script_text", "TEXT")
            await self._ensure_column(db, "subtasks", "last_error", "TEXT")
            await self._ensure_column(db, "subtasks", "script_attempts", "INTEGER NOT NULL DEFAULT 0")
            await self._ensure_column(db, "subtasks", "video_attempts", "INTEGER NOT NULL DEFAULT 0")
            await db.commit()

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON;")
        try:
            yield db
        finally:
            await db.close()

    async def _ensure_column(
        self,
        db: aiosqlite.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except aiosqlite.OperationalError as exc:  # noqa: PERF203
            if "duplicate column name" in str(exc).lower():
                return
            raise

    # ------------------------------------------------------------------ drafts

    async def add_product_draft(
        self,
        user_id: int | str,
        description: str,
        image_path: Path | None,
        image_file_id: str | None,
    ) -> ProductDraft:
        draft_id = uuid4().hex
        created_at = _serialize_dt(datetime.now(timezone.utc))
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO product_drafts (id, user_id, description, image_path, image_file_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    str(user_id),
                    description,
                    str(image_path) if image_path else None,
                    image_file_id,
                    created_at,
                ),
            )
            await db.commit()
        return ProductDraft(
            id=draft_id,
            description=description,
            image_path=image_path,
            image_file_id=image_file_id,
        )

    async def list_product_drafts(self, user_id: int | str) -> list[ProductDraft]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT id, description, image_path, image_file_id
                FROM product_drafts
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (str(user_id),),
            )
            rows = await cursor.fetchall()
        drafts: list[ProductDraft] = []
        for row in rows:
            path_value = Path(row["image_path"]) if row["image_path"] else None
            drafts.append(
                ProductDraft(
                    id=row["id"],
                    description=row["description"],
                    image_path=path_value,
                    image_file_id=row["image_file_id"],
                )
            )
        return drafts

    async def consume_product_drafts(self, user_id: int | str) -> list[ProductDraft]:
        drafts = await self.list_product_drafts(user_id)
        async with self._connect() as db:
            await db.execute(
                "DELETE FROM product_drafts WHERE user_id = ?",
                (str(user_id),),
            )
            await db.commit()
        return drafts

    async def update_product_draft(
        self,
        draft_id: str,
        *,
        description: str | None = None,
    ) -> None:
        fields: list[str] = []
        params: list[object] = []
        if description is not None:
            fields.append("description = ?")
            params.append(description)
        if not fields:
            return
        params.append(draft_id)
        async with self._connect() as db:
            await db.execute(
                f"UPDATE product_drafts SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            await db.commit()

    # ------------------------------------------------------------ batch config

    async def set_batch_config(
        self,
        user_id: int | str,
        *,
        generation_count: int,
        ideas: Sequence[str],
    ) -> UserBatchConfig:
        payload = json.dumps([idea.strip() for idea in ideas if idea.strip()])
        timestamp = _serialize_dt(datetime.now(timezone.utc))
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO batch_configs (user_id, generation_count, ideas, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    generation_count=excluded.generation_count,
                    ideas=excluded.ideas,
                    updated_at=excluded.updated_at
                """,
                (str(user_id), generation_count, payload or "[]", timestamp),
            )
            await db.commit()
        return await self.get_batch_config(user_id)

    async def get_batch_config(
        self,
        user_id: int | str,
        *,
        default_generation_count: int = 1,
    ) -> UserBatchConfig:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT generation_count, ideas FROM batch_configs WHERE user_id = ?",
                (str(user_id),),
            )
            row = await cursor.fetchone()
        if row is None:
            return UserBatchConfig(generation_count=default_generation_count)
        ideas = json.loads(row["ideas"]) if row["ideas"] else []
        return UserBatchConfig(generation_count=row["generation_count"], ideas=ideas)

    # ------------------------------------------------------------------- tasks

    async def save_task(self, task: Task) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO tasks (id, owner_user_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    str(task.owner_user_id) if task.owner_user_id is not None else None,
                    task.status.value,
                    task.created_at.isoformat(),
                    task.updated_at.isoformat(),
                ),
            )
            await db.execute("DELETE FROM subtasks WHERE task_id = ?", (task.id,))
            for index, subtask in enumerate(task.subtasks):
                result_payload = subtask.result_payload
                if result_payload is None and subtask.result_urls:
                    result_payload = {"resultUrls": subtask.result_urls}
                result_json = json.dumps(result_payload) if result_payload is not None else None
                await db.execute(
                    """
                    INSERT INTO subtasks (
                        id,
                        task_id,
                        product_id,
                        product_title,
                        product_description,
                        product_image_path,
                        product_image_file_id,
                        idea,
                        generation_index,
                        status,
                        script_text,
                        job_id,
                        record_id,
                        result_json,
                        downloaded_files,
                        last_error,
                        script_attempts,
                        video_attempts,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        subtask.id,
                        task.id,
                        subtask.product.id,
                        subtask.product.title,
                        subtask.product.short_description,
                        str(subtask.product.image_path) if subtask.product.image_path else None,
                        subtask.product.image_file_id,
                        subtask.idea.text,
                        index,
                        subtask.status.value,
                        subtask.script_text,
                        subtask.job_id,
                        subtask.record_id,
                        result_json,
                        json.dumps(subtask.downloaded_files),
                        subtask.last_error,
                        subtask.script_attempts,
                        subtask.video_attempts,
                        task.created_at.isoformat(),
                        task.updated_at.isoformat(),
                    ),
                )
            await db.commit()

    async def load_task(self, task_id: str) -> Task | None:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT id, owner_user_id, status, created_at, updated_at FROM tasks WHERE id = ?",
                (task_id,),
            )
            task_row = await cursor.fetchone()
            if not task_row:
                return None
            cursor = await db.execute(
                """
                SELECT *
                FROM subtasks
                WHERE task_id = ?
                ORDER BY created_at ASC
                """,
                (task_id,),
            )
            sub_rows = await cursor.fetchall()

        subtasks: list[SubTask] = []
        for row in sub_rows:
            product = Product(
                id=row["product_id"],
                title=row["product_title"],
                short_description=row["product_description"],
                image_path=Path(row["product_image_path"]) if row["product_image_path"] else None,
                image_file_id=row["product_image_file_id"],
            )
            idea = Idea(id=uuid4().hex, text=row["idea"])
            downloaded_files = json.loads(row["downloaded_files"]) if row["downloaded_files"] else []
            result_payload = json.loads(row["result_json"]) if row["result_json"] else None
            result_urls: list[str] = []
            if isinstance(result_payload, dict):
                urls = result_payload.get("resultUrls") or result_payload.get("result_urls")
                if isinstance(urls, list):
                    result_urls = [str(url) for url in urls]
            subtasks.append(
                SubTask(
                    id=row["id"],
                    product=product,
                    idea=idea,
                    n_generations=row["generation_index"],
                    status=GenerationStatus(row["status"]),
                     script_text=row["script_text"],
                    job_id=row["job_id"],
                    record_id=row["record_id"],
                     result_urls=result_urls,
                     result_payload=result_payload if isinstance(result_payload, dict) else None,
                    downloaded_files=downloaded_files,
                    last_error=row["last_error"],
                    script_attempts=row["script_attempts"],
                    video_attempts=row["video_attempts"],
                )
            )

        return Task(
            id=task_row["id"],
            subtasks=subtasks,
            created_at=_deserialize_dt(task_row["created_at"]),
            updated_at=_deserialize_dt(task_row["updated_at"]),
            owner_user_id=task_row["owner_user_id"],
            status=TaskStatus(task_row["status"]),
        )

    async def update_subtask(
        self,
        task_id: str,
        subtask_id: str,
        *,
        status: GenerationStatus | None = None,
        job_id: str | None = None,
        record_id: str | None = None,
        result_payload: dict | None = None,
        downloaded_files: list[str] | None = None,
        script_text: str | None = None,
        last_error: str | None = None,
        script_attempts: int | None = None,
        video_attempts: int | None = None,
    ) -> None:
        fields: list[str] = []
        params: list[object] = []
        if status is not None:
            fields.append("status = ?")
            params.append(status.value)
        if script_text is not None:
            fields.append("script_text = ?")
            params.append(script_text)
        if job_id is not None:
            fields.append("job_id = ?")
            params.append(job_id)
        if record_id is not None:
            fields.append("record_id = ?")
            params.append(record_id)
        if result_payload is not None:
            fields.append("result_json = ?")
            params.append(json.dumps(result_payload))
        if downloaded_files is not None:
            fields.append("downloaded_files = ?")
            params.append(json.dumps(downloaded_files))
        if last_error is not None:
            fields.append("last_error = ?")
            params.append(last_error)
        if script_attempts is not None:
            fields.append("script_attempts = ?")
            params.append(script_attempts)
        if video_attempts is not None:
            fields.append("video_attempts = ?")
            params.append(video_attempts)
        if not fields:
            return
        fields.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.extend([subtask_id, task_id])
        async with self._connect() as db:
            await db.execute(
                f"""
                UPDATE subtasks
                SET {', '.join(fields)}
                WHERE id = ? AND task_id = ?
                """,
                params,
            )
            await db.commit()

    async def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        async with self._connect() as db:
            await db.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, _serialize_dt(datetime.now(timezone.utc)), task_id),
            )
            await db.commit()

    async def list_active_task_ids(self) -> list[str]:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT id FROM tasks WHERE status IN ('pending', 'processing')"
            )
            rows = await cursor.fetchall()
        return [row["id"] for row in rows]

    async def list_tasks(
        self,
        owner_user_id: int | str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[TaskSummary]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT
                    t.id,
                    t.status,
                    t.created_at,
                    t.updated_at,
                    COUNT(s.id) AS total_cnt,
                    SUM(CASE WHEN s.status = ? THEN 1 ELSE 0 END) AS done_cnt,
                    SUM(CASE WHEN s.status = ? THEN 1 ELSE 0 END) AS failed_cnt,
                    SUM(CASE WHEN s.status = ? THEN 1 ELSE 0 END) AS cancelled_cnt
                FROM tasks t
                LEFT JOIN subtasks s ON s.task_id = t.id
                WHERE t.owner_user_id = ?
                GROUP BY t.id
                ORDER BY t.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (
                    GenerationStatus.DONE.value,
                    GenerationStatus.FAILED.value,
                    GenerationStatus.CANCELLED.value,
                    str(owner_user_id),
                    limit,
                    offset,
                ),
            )
            rows = await cursor.fetchall()
        summaries: list[TaskSummary] = []
        for row in rows:
            total = row["total_cnt"] or 0
            done = row["done_cnt"] or 0
            failed = row["failed_cnt"] or 0
            cancelled = row["cancelled_cnt"] or 0
            summaries.append(
                TaskSummary(
                    id=row["id"],
                    status=TaskStatus(row["status"]),
                    created_at=_deserialize_dt(row["created_at"]),
                    updated_at=_deserialize_dt(row["updated_at"]),
                    total=total,
                    done=done,
                    failed=failed,
                    cancelled=cancelled,
                )
            )
        return summaries

    async def get_task_progress(self, task_id: str) -> dict[str, int]:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) as cnt FROM subtasks WHERE task_id = ? GROUP BY status",
                (task_id,),
            )
            rows = await cursor.fetchall()
        progress = {row["status"]: row["cnt"] for row in rows}
        total = sum(progress.values())
        done = progress.get(GenerationStatus.DONE.value, 0)
        failed = progress.get(GenerationStatus.FAILED.value, 0)
        cancelled = progress.get(GenerationStatus.CANCELLED.value, 0)
        return {"total": total, "done": done, "failed": failed, "cancelled": cancelled}

    # ----------------------------------------------------------- worker queue

    async def add_worker_task(self, task_id: str) -> None:
        timestamp = _serialize_dt(datetime.now(timezone.utc))
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO worker_queue (task_id, state, enqueued_at, updated_at)
                VALUES (?, 'pending', ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    state='pending',
                    updated_at=excluded.updated_at
                """,
                (task_id, timestamp, timestamp),
            )
            await db.commit()

    async def update_worker_task_state(self, task_id: str, state: str) -> None:
        timestamp = _serialize_dt(datetime.now(timezone.utc))
        async with self._connect() as db:
            await db.execute(
                "UPDATE worker_queue SET state = ?, updated_at = ? WHERE task_id = ?",
                (state, timestamp, task_id),
            )
            await db.commit()

    async def delete_worker_task(self, task_id: str) -> None:
        async with self._connect() as db:
            await db.execute("DELETE FROM worker_queue WHERE task_id = ?", (task_id,))
            await db.commit()

    async def list_worker_tasks(self, states: Sequence[str] | None = None) -> list[str]:
        query = "SELECT task_id FROM worker_queue"
        params: list[object] = []
        if states:
            placeholders = ",".join("?" for _ in states)
            query += f" WHERE state IN ({placeholders})"
            params.extend(states)
        query += " ORDER BY enqueued_at ASC"
        async with self._connect() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
        return [row["task_id"] for row in rows]

    # ------------------------------------------------------------- global settings

    async def set_setting(self, key: str, value: dict | str | int | float | bool) -> None:
        timestamp = _serialize_dt(datetime.now(timezone.utc))
        payload = json.dumps(value)
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, payload, timestamp),
            )
            await db.commit()

    async def get_setting(self, key: str) -> dict | list | str | int | float | bool | None:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return json.loads(row["value"])

    # -------------------------------------------------------------- task events

    async def add_task_event(self, task_id: str, event_type: str, message: str) -> str:
        event_id = uuid4().hex
        created_at = _serialize_dt(datetime.now(timezone.utc))
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, task_id, event_type, message, created_at),
            )
            await db.commit()
        return event_id

    async def list_task_events(
        self,
        task_id: str,
        limit: int,
        offset: int = 0,
    ) -> list[dict]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT id, event_type, message, created_at
                FROM task_events
                WHERE task_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (task_id, limit, offset),
            )
            rows = await cursor.fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "message": row["message"],
                "created_at": _deserialize_dt(row["created_at"]),
            }
            for row in rows
        ]
