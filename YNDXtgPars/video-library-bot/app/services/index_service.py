from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import sqlite3
import uuid
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

from txtai.embeddings import Embeddings

from app.db import db_session, utc_now_iso
from app.models import SearchHit, SearchResponse, VideoStatus
from app.services.storage_base import StorageBase
from app.utils import join_disk_path, normalize_disk_path


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_DIRNAME = "txtai_index"
TMP_INDEX_DIRNAME = "txtai_index_tmp"
BACKUP_INDEX_DIRNAME = "txtai_index_backup"
INDEX_VERSION_FILENAME = "index_version.json"
INDEX_SCHEMA_VERSION = 1
CHUNKING_VERSION = "v3"
MIN_CHUNK_LEN = 1200
MAX_CHUNK_LEN = 2000
SEARCH_MULTIPLIER = 12


class IndexService:
    """txtai-based semantic index service for video library."""

    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
        storage: StorageBase,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        sim_threshold: float = 0.30,
        lexical_boost: float = 0.15,
    ) -> None:
        self._db_path = db_path
        self._storage = storage
        self._embedding_model = embedding_model
        self._sim_threshold = sim_threshold
        self._lexical_boost_limit = max(0.0, min(lexical_boost, 0.35))
        self._index_path = data_dir / INDEX_DIRNAME
        self._embeddings: Optional[Embeddings] = None
        self._index_dirty = False
        self._index_loaded = False
        self._has_index = False
        self._needs_rebuild = False
        self._version_checked = False
        self._rebuild_attempted = False
        self._index_version_path = self._index_path / INDEX_VERSION_FILENAME
        self._generation_id: str | None = None
        self._logger = logging.getLogger("video_library_bot.index")
        self._mutex = asyncio.Lock()

    async def build_or_update_index(
        self,
        force: bool = False,
        storage: Optional[StorageBase] = None,
    ) -> bool:
        """Build or update the index for READY videos, respecting index_state."""
        async with self._mutex:
            storage = storage or self._storage
            if storage is None:
                raise ValueError("storage is required for indexing")

            async with db_session(self._db_path) as db:
                total, ready = await self._video_counts(db)
                if total == 0 or ready == 0:
                    self._logger.warning(
                        "skip index update due to empty scan result",
                        extra={"total": total, "ready": ready},
                    )
                    return False

            self._load_index_if_exists()
            async with db_session(self._db_path) as db:
                if self._needs_rebuild:
                    if self._rebuild_attempted:
                        self._logger.error("index rebuild already attempted; skipping")
                        return False
                    self._logger.warning("index version mismatch, rebuilding")
                    self._rebuild_attempted = True
                    rebuilt = await self._rebuild_index(db, storage)
                    if not rebuilt:
                        self._rebuild_attempted = False
                    return bool(rebuilt)
                try:
                    await self._build_or_update_index(db, storage, force=force)
                except sqlite3.IntegrityError as exc:
                    if self._rebuild_attempted:
                        self._logger.error(
                            "index corruption detected after rebuild; skipping",
                            extra={"error": str(exc)},
                        )
                        return False
                    self._logger.warning(
                        "index corruption detected, rebuilding",
                        extra={"error": str(exc)},
                    )
                    self._rebuild_attempted = True
                    rebuilt = await self._rebuild_index(db, storage)
                    if not rebuilt:
                        self._rebuild_attempted = False
                    return bool(rebuilt)
            self._save_index()
            return True

    async def index_video(
        self,
        video_id: str,
        storage: Optional[StorageBase] = None,
    ) -> None:
        """Index a single video by ID."""
        async with self._mutex:
            storage = storage or self._storage
            if storage is None:
                raise ValueError("storage is required for indexing")

            self._load_index_if_exists()
            async with db_session(self._db_path) as db:
                if self._needs_rebuild:
                    if self._rebuild_attempted:
                        self._logger.error("index rebuild already attempted; skipping")
                        return
                    self._logger.warning("index version mismatch, rebuilding")
                    self._rebuild_attempted = True
                    rebuilt = await self._rebuild_index(db, storage)
                    if not rebuilt:
                        self._rebuild_attempted = False
                    return
                cursor = await db.execute(
                    """
                    SELECT
                        video_id,
                        title,
                        disk_folder,
                        summary_path,
                        transcript_path,
                        fingerprint_json,
                        status
                    FROM videos
                    WHERE video_id = ?
                    """,
                    (video_id,),
                )
                row = await cursor.fetchone()
                if not row or row["status"] != VideoStatus.READY.value:
                    self._logger.warning(
                        "video not ready for indexing",
                        extra={"video_id": video_id},
                    )
                    return
                try:
                    await self._index_video_record(db, row, storage)
                except sqlite3.IntegrityError as exc:
                    if self._rebuild_attempted:
                        self._logger.error(
                            "index corruption detected after rebuild; skipping",
                            extra={"error": str(exc)},
                        )
                        return
                    self._logger.warning(
                        "index corruption detected, rebuilding",
                        extra={"error": str(exc)},
                    )
                    self._rebuild_attempted = True
                    rebuilt = await self._rebuild_index(db, storage)
                    if not rebuilt:
                        self._rebuild_attempted = False
            self._save_index()

    async def remove_video(self, video_id: str) -> None:
        """Remove a video from the index."""
        async with self._mutex:
            self._load_index_if_exists()
            async with db_session(self._db_path) as db:
                await self._remove_video_with_db(db, video_id)
            self._save_index()

    async def search(self, query: str, top_k: int = 3) -> SearchResponse:
        """
        Search the index for videos matching the query.
        Returns SearchResponse with grouped results by video_id.
        """
        async with self._mutex:
            self._load_index_if_exists()
            if not self._has_index or not self._embeddings:
                return SearchResponse(
                    query=query,
                    threshold=self._sim_threshold,
                    low_confidence=True,
                    results=[],
                )

            limit = max(top_k * SEARCH_MULTIPLIER, top_k)
            query_for_embedding = self._expand_query(query)
            keyword_query = self._keyword_query(query)
            if keyword_query and keyword_query not in query_for_embedding:
                query_for_embedding = f"{query_for_embedding} {keyword_query}"
            raw_results = self._embeddings.search(
                query_for_embedding,
                limit=limit,
                parameters={"minscore": -1},
            )
            chunk_ids = [self._extract_chunk_id(result) for result in raw_results]
            chunk_ids = [chunk_id for chunk_id in chunk_ids if chunk_id]
            if not chunk_ids:
                return SearchResponse(
                    query=query,
                    threshold=self._sim_threshold,
                    low_confidence=True,
                    results=[],
                )

            async with db_session(self._db_path) as db:
                chunk_map = await self._load_chunks(db, chunk_ids)
                if not chunk_map:
                    return SearchResponse(
                        query=query,
                        threshold=self._sim_threshold,
                        low_confidence=True,
                        results=[],
                    )
                video_ids = {chunk["video_id"] for chunk in chunk_map.values()}
                title_map = await self._load_titles(db, video_ids)

            best_by_video: dict[str, SearchHit] = {}
            best_text_by_video: dict[str, str] = {}
            title_match_flags: dict[str, bool] = {}
            for result in raw_results:
                chunk_id = self._extract_chunk_id(result)
                score = self._extract_score(result)
                if not chunk_id or chunk_id not in chunk_map:
                    continue
                chunk = chunk_map[chunk_id]
                title = title_map.get(chunk["video_id"], "")
                current = best_by_video.get(chunk["video_id"])
                if current is None or score > current.score:
                    source_text = chunk["source"] if "source" in chunk.keys() else ""
                    best_by_video[chunk["video_id"]] = SearchHit(
                        rank=0,
                        video_id=chunk["video_id"],
                        title=title,
                        score=score,
                        snippet=self._make_snippet(chunk["text"], query),
                        source_text_type=source_text or "",
                        start_sec=chunk["start_sec"],
                        end_sec=chunk["end_sec"],
                    )
                    best_text_by_video[chunk["video_id"]] = chunk["text"] or ""
                    title_match_flags[chunk["video_id"]] = self._title_match(query, title)

            boosted_results: list[SearchHit] = []
            for video_id, hit in best_by_video.items():
                boost = self._lexical_boost(query, hit.title, best_text_by_video.get(video_id, ""))
                boosted_results.append(
                    SearchHit(
                        rank=0,
                        video_id=hit.video_id,
                        title=hit.title,
                        score=hit.score + boost,
                        snippet=hit.snippet,
                        source_text_type=hit.source_text_type,
                        start_sec=hit.start_sec,
                        end_sec=hit.end_sec,
                    )
                )

            results = sorted(
                boosted_results,
                key=lambda item: (title_match_flags.get(item.video_id, False), item.score),
                reverse=True,
            )
            results = results[:top_k]
            ranked_results = []
            for idx, hit in enumerate(results, 1):
                ranked_results.append(
                    SearchHit(
                        rank=idx,
                        video_id=hit.video_id,
                        title=hit.title,
                        score=hit.score,
                        snippet=hit.snippet,
                        source_text_type=hit.source_text_type,
                        start_sec=hit.start_sec,
                        end_sec=hit.end_sec,
                    )
                )
            best_score = results[0].score if results else 0.0
            low_confidence = best_score < self._sim_threshold

            return SearchResponse(
                query=query,
                threshold=self._sim_threshold,
                low_confidence=low_confidence,
                results=ranked_results,
            )

    async def index_size(self) -> int:
        """Return the number of chunks in the index."""
        async with db_session(self._db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) AS cnt FROM chunks")
            row = await cursor.fetchone()
            return int(row["cnt"]) if row else 0

    # --- Private Methods ---

    async def _build_or_update_index(
        self,
        db,
        storage: StorageBase,
        force: bool = False,
    ) -> None:
        videos = await self._load_videos(db)
        index_state = await self._load_index_state(db)

        # Remove DELETED or non-READY videos from index
        removed_ids = await self._remove_deleted_or_unready(db, videos, index_state)
        for video_id in removed_ids:
            index_state.pop(video_id, None)

        # Index new or changed READY videos
        for video_id, row in videos.items():
            if row["status"] != VideoStatus.READY.value:
                continue
            if not force and index_state.get(video_id) == row["fingerprint_json"]:
                continue
            await self._index_video_record(db, row, storage)
            self._logger.info("indexed video", extra={"video_id": video_id})

    async def _index_video_record(self, db, row, storage: StorageBase) -> None:
        video_id = row["video_id"]
        chunks = await self._load_text_chunks(row, storage)
        if not chunks:
            self._logger.warning("no text to index", extra={"video_id": video_id})
            return

        await self._remove_video_with_db(db, video_id)

        documents = []
        chunk_records = []
        for chunk in chunks:
            chunk_id = uuid.uuid4().hex
            documents.append((chunk_id, chunk["text"]))
            chunk_records.append(
                (
                    chunk_id,
                    video_id,
                    chunk["text"],
                    chunk["start_sec"],
                    chunk["end_sec"],
                    chunk["source"],
                )
            )

        self._ensure_embeddings().upsert(documents)
        self._index_dirty = True

        await db.executemany(
            """
            INSERT INTO chunks (chunk_id, video_id, text, start_sec, end_sec, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            chunk_records,
        )
        await db.execute(
            """
            INSERT INTO index_state (video_id, fingerprint_json, indexed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                fingerprint_json=excluded.fingerprint_json,
                indexed_at=excluded.indexed_at
            """,
            (video_id, row["fingerprint_json"], utc_now_iso()),
        )
        await db.commit()

    async def _remove_video_with_db(self, db, video_id: str) -> None:
        chunk_ids = await self._load_chunk_ids(db, video_id)
        if chunk_ids:
            self._ensure_embeddings().delete(chunk_ids)
            self._index_dirty = True
            await db.execute("DELETE FROM chunks WHERE video_id = ?", (video_id,))
        await db.execute("DELETE FROM index_state WHERE video_id = ?", (video_id,))
        await db.commit()

    async def _remove_deleted_or_unready(
        self,
        db,
        videos: dict[str, dict],
        index_state: dict[str, str],
    ) -> set[str]:
        removed: set[str] = set()
        for video_id in list(index_state.keys()):
            row = videos.get(video_id)
            if not row or row["status"] != VideoStatus.READY.value:
                await self._remove_video_with_db(db, video_id)
                removed.add(video_id)
                self._logger.info("removed from index", extra={"video_id": video_id})
        return removed

    async def _rebuild_index(self, db, storage: StorageBase) -> bool:
        temp_index_path = self._index_path.parent / TMP_INDEX_DIRNAME
        backup_path: Path | None = None
        if temp_index_path.exists():
            shutil.rmtree(temp_index_path, ignore_errors=True)
        await self._prepare_temp_tables(db)
        embeddings = Embeddings({"path": self._embedding_model})
        try:
            videos = await self._load_videos(db)
            for row in videos.values():
                if row["status"] != VideoStatus.READY.value:
                    continue
                await self._index_video_record_temp(db, row, storage, embeddings)
                self._logger.info("indexed video", extra={"video_id": row["video_id"]})
            temp_chunk_count = await self._count_temp_chunks(db)
            if temp_chunk_count == 0:
                self._logger.warning("skip index swap due to empty rebuild")
                await self._cleanup_temp_tables(db)
                if temp_index_path.exists():
                    shutil.rmtree(temp_index_path, ignore_errors=True)
                return False
            temp_index_path.parent.mkdir(parents=True, exist_ok=True)
            embeddings.save(str(temp_index_path))
            backup_path = self._swap_index_dir(temp_index_path)
            await self._swap_temp_tables(db)
            if backup_path and backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            self._embeddings = embeddings
            self._index_dirty = False
            self._index_loaded = True
            self._has_index = True
            self._needs_rebuild = False
            self._version_checked = True
            self._advance_generation()
            self._write_index_version()
            return True
        except Exception:
            await self._cleanup_temp_tables(db)
            if temp_index_path.exists():
                shutil.rmtree(temp_index_path, ignore_errors=True)
            if backup_path and backup_path.exists():
                if self._index_path.exists():
                    shutil.rmtree(self._index_path, ignore_errors=True)
                shutil.move(str(backup_path), str(self._index_path))
            raise

    async def _reset_index_state(self, db) -> None:
        if self._index_path.exists():
            shutil.rmtree(self._index_path, ignore_errors=True)
        if self._index_version_path.exists():
            self._index_version_path.unlink()
        self._embeddings = None
        self._index_loaded = False
        self._index_dirty = False
        self._has_index = False
        self._needs_rebuild = False
        self._version_checked = False
        self._rebuild_attempted = False
        self._generation_id = None
        await db.execute("DELETE FROM chunks")
        await db.execute("DELETE FROM index_state")
        await db.commit()

    async def _prepare_temp_tables(self, db) -> None:
        await db.execute("DROP TABLE IF EXISTS chunks_tmp")
        await db.execute(
            """
            CREATE TABLE chunks_tmp (
                chunk_id TEXT PRIMARY KEY,
                video_id TEXT,
                text TEXT,
                start_sec INTEGER NULL,
                end_sec INTEGER NULL,
                source TEXT
            )
            """
        )
        await db.execute("DROP TABLE IF EXISTS index_state_tmp")
        await db.execute(
            """
            CREATE TABLE index_state_tmp (
                video_id TEXT PRIMARY KEY,
                fingerprint_json TEXT,
                indexed_at TEXT
            )
            """
        )
        await db.commit()

    async def _cleanup_temp_tables(self, db) -> None:
        await db.execute("DROP TABLE IF EXISTS chunks_tmp")
        await db.execute("DROP TABLE IF EXISTS index_state_tmp")
        await db.commit()

    async def _swap_temp_tables(self, db) -> None:
        try:
            await db.execute("ALTER TABLE chunks RENAME TO chunks_old")
            await db.execute("ALTER TABLE chunks_tmp RENAME TO chunks")
            await db.execute("DROP TABLE chunks_old")

            await db.execute("ALTER TABLE index_state RENAME TO index_state_old")
            await db.execute("ALTER TABLE index_state_tmp RENAME TO index_state")
            await db.execute("DROP TABLE index_state_old")
            await db.commit()
        except Exception:
            await db.rollback()
            try:
                await db.execute("ALTER TABLE chunks_old RENAME TO chunks")
                await db.execute("ALTER TABLE index_state_old RENAME TO index_state")
                await db.commit()
            except Exception:
                await db.rollback()
            raise

    async def _count_temp_chunks(self, db) -> int:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM chunks_tmp")
        row = await cursor.fetchone()
        return int(row["cnt"]) if row and row["cnt"] is not None else 0

    def _swap_index_dir(self, temp_index_path: Path) -> Path | None:
        backup_path = self._index_path.parent / BACKUP_INDEX_DIRNAME
        if backup_path.exists():
            shutil.rmtree(backup_path, ignore_errors=True)
        if self._index_path.exists():
            shutil.move(str(self._index_path), str(backup_path))
        else:
            backup_path = None
        try:
            shutil.move(str(temp_index_path), str(self._index_path))
        except Exception:
            if self._index_path.exists():
                shutil.rmtree(self._index_path, ignore_errors=True)
            if backup_path and backup_path.exists():
                shutil.move(str(backup_path), str(self._index_path))
            raise
        return backup_path

    async def _index_video_record_temp(self, db, row, storage: StorageBase, embeddings: Embeddings) -> None:
        video_id = row["video_id"]
        chunks = await self._load_text_chunks(row, storage)
        if not chunks:
            self._logger.warning("no text to index", extra={"video_id": video_id})
            return

        documents = []
        chunk_records = []
        for chunk in chunks:
            chunk_id = uuid.uuid4().hex
            documents.append((chunk_id, chunk["text"]))
            chunk_records.append(
                (
                    chunk_id,
                    video_id,
                    chunk["text"],
                    chunk["start_sec"],
                    chunk["end_sec"],
                    chunk["source"],
                )
            )

        embeddings.upsert(documents)

        await db.executemany(
            """
            INSERT INTO chunks_tmp (chunk_id, video_id, text, start_sec, end_sec, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            chunk_records,
        )
        await db.execute(
            """
            INSERT INTO index_state_tmp (video_id, fingerprint_json, indexed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                fingerprint_json=excluded.fingerprint_json,
                indexed_at=excluded.indexed_at
            """,
            (video_id, row["fingerprint_json"], utc_now_iso()),
        )
        await db.commit()

    async def _load_videos(self, db) -> dict[str, dict]:
        cursor = await db.execute(
            """
            SELECT
                video_id,
                title,
                disk_folder,
                summary_path,
                transcript_path,
                text_paths_json,
                fingerprint_json,
                status
            FROM videos
            """
        )
        rows = await cursor.fetchall()
        return {row["video_id"]: row for row in rows}

    async def _video_counts(self, db) -> tuple[int, int]:
        cursor = await db.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) AS ready_count
            FROM videos
            """,
            (VideoStatus.READY.value,),
        )
        row = await cursor.fetchone()
        total = int(row["total_count"]) if row and row["total_count"] is not None else 0
        ready = int(row["ready_count"] or 0) if row else 0
        return total, ready

    async def _load_index_state(self, db) -> dict[str, str]:
        cursor = await db.execute(
            "SELECT video_id, fingerprint_json FROM index_state"
        )
        rows = await cursor.fetchall()
        return {row["video_id"]: row["fingerprint_json"] for row in rows}

    async def _load_chunk_ids(self, db, video_id: str) -> list[str]:
        cursor = await db.execute(
            "SELECT chunk_id FROM chunks WHERE video_id = ?",
            (video_id,),
        )
        rows = await cursor.fetchall()
        return [row["chunk_id"] for row in rows]

    async def _load_chunks(self, db, chunk_ids: Iterable[str]) -> dict[str, dict]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" for _ in chunk_ids)
        cursor = await db.execute(
            f"""
            SELECT chunk_id, video_id, text, start_sec, end_sec, source
            FROM chunks
            WHERE chunk_id IN ({placeholders})
            """,
            tuple(chunk_ids),
        )
        rows = await cursor.fetchall()
        return {row["chunk_id"]: row for row in rows}

    async def _load_titles(self, db, video_ids: Iterable[str]) -> dict[str, str]:
        if not video_ids:
            return {}
        placeholders = ",".join("?" for _ in video_ids)
        cursor = await db.execute(
            f"SELECT video_id, title FROM videos WHERE video_id IN ({placeholders})",
            tuple(video_ids),
        )
        rows = await cursor.fetchall()
        return {row["video_id"]: row["title"] for row in rows}

    async def _load_text_chunks(self, row, storage: StorageBase) -> list[dict]:
        text_paths = self._resolve_text_paths(row)
        if not text_paths:
            return []
        title_prefix = (row["title"] or "").strip()
        chunks: list[dict] = []
        for path in text_paths:
            try:
                text = await self._read_storage_text(row["disk_folder"], path, storage)
            except Exception as exc:
                if getattr(exc, "status_code", None) == 404:
                    self._logger.info(
                        "text disappeared; will re-scan next cycle",
                        extra={"path": path},
                    )
                else:
                    self._logger.warning(
                        "failed to read text",
                        extra={"path": path, "error": str(exc)},
                    )
                continue
            text = text.strip()
            if not text:
                continue
            if title_prefix:
                text = f"{title_prefix}\n{text}"
            text_type = self._classify_text_path(path)
            if text_type == "summary":
                if len(text) <= MAX_CHUNK_LEN:
                    chunks.append(
                        {
                            "text": text,
                            "start_sec": None,
                            "end_sec": None,
                            "source": "summary",
                        }
                    )
                else:
                    for chunk in self._split_long_text(text):
                        chunks.append(
                            {
                                "text": chunk,
                                "start_sec": None,
                                "end_sec": None,
                                "source": "summary",
                            }
                        )
                continue
            if path.lower().endswith(".vtt"):
                parts = self._chunk_vtt(text)
            else:
                parts = self._chunk_transcript(text)
            for chunk in parts:
                chunks.append(
                    {
                        "text": chunk["text"],
                        "start_sec": chunk["start_sec"],
                        "end_sec": chunk["end_sec"],
                        "source": "transcript",
                    }
                )
        return chunks

    async def _read_storage_text(
        self, folder: str, relative_path: str, storage: StorageBase
    ) -> str:
        target = self._build_storage_path(folder, relative_path)
        return await storage.read_text(target)

    @staticmethod
    def _build_storage_path(folder: str, relative_path: str) -> str:
        if relative_path.startswith("disk:") or relative_path.startswith("/disk:"):
            return normalize_disk_path(relative_path)
        if relative_path.startswith("/"):
            return normalize_disk_path(relative_path)
        return join_disk_path(folder, relative_path)

    @staticmethod
    def _chunk_transcript(text: str) -> list[dict]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        chunks = []
        for paragraph in paragraphs:
            paragraph = " ".join(paragraph.split())
            if len(paragraph) <= MAX_CHUNK_LEN:
                chunks.append({"text": paragraph, "start_sec": None, "end_sec": None})
                continue
            for chunk in IndexService._split_long_text(paragraph):
                chunks.append({"text": chunk, "start_sec": None, "end_sec": None})
        return chunks

    @staticmethod
    def _chunk_vtt(text: str) -> list[dict]:
        chunks = []
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if not line or line.startswith("WEBVTT"):
                index += 1
                continue
            if "-->" not in line:
                index += 1
                continue
            try:
                start_sec, end_sec = IndexService._parse_timecodes(line)
            except ValueError:
                index += 1
                continue
            index += 1
            cue_lines = []
            while index < len(lines) and lines[index].strip():
                cue_lines.append(lines[index].strip())
                index += 1
            cue_text = " ".join(cue_lines).strip()
            if not cue_text:
                continue
            cue_text = " ".join(cue_text.split())
            time_prefix = f"{IndexService._format_timestamp(start_sec)}-{IndexService._format_timestamp(end_sec)} "
            if len(cue_text) > MAX_CHUNK_LEN:
                for chunk in IndexService._split_long_text(cue_text):
                    chunks.append(
                        {
                            "text": f"{time_prefix}{chunk}",
                            "start_sec": start_sec,
                            "end_sec": end_sec,
                        }
                    )
            else:
                chunks.append(
                    {
                        "text": f"{time_prefix}{cue_text}",
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                    }
                )
        return chunks

    @staticmethod
    def _parse_timecodes(line: str) -> tuple[int, int]:
        start_raw, end_raw = line.split("-->", 1)
        start_token = start_raw.strip().split()[0]
        end_token = end_raw.strip().split()[0]
        return (
            IndexService._parse_timestamp(start_token),
            IndexService._parse_timestamp(end_token),
        )

    @staticmethod
    def _parse_timestamp(value: str) -> int:
        parts = value.split(":")
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = IndexService._parse_seconds(parts[2])
        elif len(parts) == 2:
            hours = 0
            minutes = int(parts[0])
            seconds = IndexService._parse_seconds(parts[1])
        else:
            raise ValueError("Unsupported timestamp")
        return int(hours * 3600 + minutes * 60 + seconds)

    @staticmethod
    def _parse_seconds(value: str) -> float:
        if "." not in value:
            return float(value)
        seconds, millis = value.split(".", 1)
        return float(seconds) + float(f"0.{millis}")

    @staticmethod
    def _format_timestamp(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _resolve_text_paths(self, row) -> list[str]:
        paths: list[str] = []
        text_paths_json = None
        if hasattr(row, "keys") and "text_paths_json" in row.keys():
            text_paths_json = row["text_paths_json"]
        if text_paths_json:
            try:
                raw = json.loads(text_paths_json)
                if isinstance(raw, list):
                    paths.extend([item for item in raw if isinstance(item, str) and item.strip()])
            except ValueError:
                pass
        summary_path = row["summary_path"] if "summary_path" in row.keys() else None
        transcript_path = (
            row["transcript_path"] if "transcript_path" in row.keys() else None
        )
        for fallback in (summary_path, transcript_path):
            if fallback:
                paths.append(fallback)
        return self._dedupe_paths(paths)

    @staticmethod
    def _dedupe_paths(paths: list[str]) -> list[str]:
        seen: set[str] = set()
        result = []
        for path in paths:
            normalized = normalize_disk_path(path)
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _classify_text_path(path: str) -> str:
        name = PurePosixPath(normalize_disk_path(path)[len("disk:") :]).name.lower()
        if name.endswith(".md"):
            return "summary"
        return "transcript"

    @staticmethod
    def _split_long_text(text: str) -> list[str]:
        chunks = []
        remaining = text.strip()
        while len(remaining) > MAX_CHUNK_LEN:
            split_at = remaining.rfind(" ", 0, MAX_CHUNK_LEN)
            if split_at < MIN_CHUNK_LEN:
                split_at = remaining.find(" ", MAX_CHUNK_LEN)
                if split_at == -1:
                    split_at = MAX_CHUNK_LEN
            chunk = remaining[:split_at].strip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[split_at:].strip()
        if remaining:
            chunks.append(remaining)
        return chunks

    @staticmethod
    def _make_snippet(text: str, query: str, max_len: int = 180) -> str:
        if not text:
            return ""
        normalized = " ".join(text.split())
        query_lower = query.lower()
        lower_text = normalized.lower()
        index = lower_text.find(query_lower)
        if index == -1:
            snippet = normalized[:max_len]
            return snippet + ("..." if len(normalized) > max_len else "")
        start = max(index - 40, 0)
        end = min(index + len(query_lower) + 80, len(normalized))
        snippet = normalized[start:end]
        if start > 0:
            snippet = f"...{snippet}"
        if end < len(normalized):
            snippet = f"{snippet}..."
        return snippet

    def _lexical_boost(self, query: str, title: str, text: str) -> float:
        if self._lexical_boost_limit <= 0:
            return 0.0
        query_tokens = [token for token in self._tokenize(query) if len(token) >= 3]
        if not query_tokens:
            return 0.0
        title_tokens = self._tokenize(title)
        if title_tokens:
            for query_token in query_tokens:
                for title_token in title_tokens:
                    if title_token.startswith(query_token):
                        return self._lexical_boost_limit
        text_tokens = self._tokenize(text)
        text_hits = sum(1 for token in query_tokens if token in text_tokens)
        if text_hits:
            return min(self._lexical_boost_limit * 0.3, self._lexical_boost_limit)
        return 0.0

    @staticmethod
    def _title_match(query: str, title: str) -> bool:
        if not query or not title:
            return False
        query_tokens = IndexService._tokenize(query)
        if not query_tokens:
            return False
        title_tokens = IndexService._tokenize(title)
        for stem in query_tokens:
            if len(stem) < 4:
                continue
            for token in title_tokens:
                if token.startswith(stem):
                    return True
        return False

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        normalized = IndexService._normalize_text(text)
        tokens = normalized.split()
        return [IndexService._stem_token(token) for token in tokens if token]

    @staticmethod
    def _stem_token(token: str) -> str:
        if not token:
            return token
        suffixes = (
            "иями",
            "ями",
            "ами",
            "ыми",
            "ими",
            "ого",
            "ему",
            "ому",
            "его",
            "иях",
            "ях",
            "ах",
            "ием",
            "ом",
            "ем",
            "ам",
            "ям",
            "ию",
            "ью",
            "ья",
            "ье",
            "ия",
            "ий",
            "ый",
            "ой",
            "ая",
            "яя",
            "ое",
            "ее",
            "ые",
            "ие",
            "ев",
            "ов",
            "ей",
            "ться",
            "ся",
            "ать",
            "ять",
            "ить",
            "еть",
            "уть",
            "а",
            "я",
            "ы",
            "и",
            "о",
            "у",
            "е",
        )
        for suffix in suffixes:
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                if len(suffix) == 1 and len(token) <= 4:
                    continue
                return token[: -len(suffix)]
        return token

    @staticmethod
    def _expand_query(query: str) -> str:
        tokens = IndexService._tokenize(query)
        expanded = list(dict.fromkeys(tokens))
        if not expanded:
            return query
        base = IndexService._normalize_text(query)
        additions = [token for token in expanded if token and token not in base]
        if additions:
            return f"{query} {' '.join(additions)}"
        return query

    @staticmethod
    def _keyword_query(query: str) -> str:
        raw_stopwords = {
            "как",
            "мне",
            "пожалуйста",
            "нужен",
            "нужна",
            "нужны",
            "нужно",
            "дай",
            "дайте",
            "покажи",
            "покажите",
            "про",
            "для",
            "и",
            "в",
            "на",
            "по",
            "с",
            "о",
            "об",
            "от",
            "до",
            "это",
            "этот",
            "эта",
            "эти",
            "мой",
            "моя",
            "мои",
            "твой",
            "твоя",
            "твои",
            "его",
            "ее",
            "их",
            "мы",
            "вы",
            "я",
            "ты",
            "он",
            "она",
            "оно",
            "они",
            "ли",
            "же",
            "бы",
        }
        stopwords = {IndexService._stem_token(word) for word in raw_stopwords}
        tokens = IndexService._tokenize(query)
        filtered = [
            token for token in tokens if len(token) >= 3 and token not in stopwords
        ]
        return " ".join(filtered).strip()

    @staticmethod
    def _normalize_text(value: str) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"[^\w\s]", " ", value.lower(), flags=re.UNICODE)
        return " ".join(cleaned.split())

    def _load_index_if_exists(self) -> None:
        if self._index_loaded:
            return
        self._check_index_version()
        if not self._needs_rebuild:
            embeddings = self._ensure_embeddings()
            if self._index_path.exists():
                embeddings.load(str(self._index_path))
                self._has_index = True
        self._index_loaded = True

    def _save_index(self) -> None:
        if not self._index_dirty or not self._embeddings:
            return
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._embeddings.save(str(self._index_path))
        self._advance_generation()
        self._write_index_version()
        self._index_dirty = False
        self._has_index = True

    def _ensure_embeddings(self) -> Embeddings:
        if self._embeddings is None:
            self._embeddings = Embeddings({"path": self._embedding_model})
        return self._embeddings

    def _current_index_version(self) -> dict[str, object]:
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "chunking_version": CHUNKING_VERSION,
            "embedding_model": self._embedding_model,
            "generation_id": self._generation_id,
        }

    def _check_index_version(self) -> None:
        if self._version_checked:
            return
        self._version_checked = True
        if not self._index_path.exists():
            self._needs_rebuild = False
            return
        if not self._index_version_path.exists():
            self._needs_rebuild = True
            return
        try:
            data = json.loads(self._index_version_path.read_text(encoding="utf-8"))
        except OSError:
            self._needs_rebuild = True
            return
        except ValueError:
            self._needs_rebuild = True
            return
        if not isinstance(data, dict):
            self._needs_rebuild = True
            return
        self._generation_id = data.get("generation_id") if isinstance(data.get("generation_id"), str) else None
        current = self._current_index_version()
        compare_keys = {"schema_version", "chunking_version", "embedding_model"}
        if any(data.get(key) != current.get(key) for key in compare_keys):
            self._needs_rebuild = True

    def _write_index_version(self) -> None:
        self._write_index_version_to(self._index_version_path)

    def _write_index_version_to(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not self._generation_id:
                self._advance_generation()
            payload = json.dumps(self._current_index_version(), ensure_ascii=False, indent=2)
            path.write_text(payload, encoding="utf-8")
        except OSError:
            self._logger.warning("failed to write index version file")

    def _advance_generation(self) -> None:
        self._generation_id = uuid.uuid4().hex

    @staticmethod
    def _extract_chunk_id(result) -> Optional[str]:
        if isinstance(result, dict):
            return result.get("id")
        if isinstance(result, (list, tuple)) and result:
            return result[0]
        return None

    @staticmethod
    def _extract_score(result) -> float:
        if isinstance(result, dict):
            return float(result.get("score", 0.0))
        if isinstance(result, (list, tuple)) and len(result) > 1:
            return float(result[1])
        return 0.0
