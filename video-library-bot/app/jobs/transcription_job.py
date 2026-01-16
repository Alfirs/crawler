from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.db import utc_now_iso
from app.models import Fingerprint, StorageEntry, VideoMeta, VideoStatus
from app.services.catalog_service import CatalogService
from app.services.fingerprint import build_fingerprint_payload
from app.services.index_service import IndexService
from app.services.storage_base import StorageBase
from app.utils import join_disk_path, normalize_disk_path


TRANSCRIPTION_INTERVAL_SEC = 45


async def run_transcription_loop(
    storage: StorageBase,
    catalog: CatalogService,
    index_service: IndexService,
    db_path: Path,
    data_dir: Path,
    enable_transcription: bool,
    transcribe_model: str,
    auto_meta_mode: str,
    logger: logging.Logger,
) -> None:
    if not enable_transcription:
        logger.info("transcription disabled (ENABLE_TRANSCRIPTION=0)")
        return

    missing_logged = False
    transcriber = None

    while True:
        if not transcriber:
            transcriber = _ensure_transcriber(transcribe_model, logger, missing_logged)
            if transcriber is None:
                missing_logged = True
                await asyncio.sleep(TRANSCRIPTION_INTERVAL_SEC)
                continue

        try:
            candidate = await _pick_candidate(db_path)
            if not candidate:
                await asyncio.sleep(TRANSCRIPTION_INTERVAL_SEC)
                continue
            await _process_candidate(
                candidate,
                storage,
                catalog,
                index_service,
                data_dir,
                transcriber,
                auto_meta_mode,
                logger,
            )
        except Exception:
            logger.exception("transcription loop failed")

        await asyncio.sleep(TRANSCRIPTION_INTERVAL_SEC)


def _ensure_transcriber(model_name: str, logger: logging.Logger, logged: bool):
    if shutil.which("ffmpeg") is None:
        if not logged:
            logger.warning("transcription disabled: ffmpeg not found")
        return None
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        if not logged:
            logger.warning("transcription disabled: faster-whisper not available")
            logger.debug("faster-whisper import error: %s", exc)
        return None
    return WhisperModel(model_name, device="cpu", compute_type="int8")


async def _pick_candidate(db_path: Path) -> dict[str, Any] | None:
    from app.db import db_session

    async with db_session(db_path) as db:
        cursor = await db.execute(
            """
            SELECT
                video_id,
                title,
                disk_folder,
                video_path,
                summary_path,
                transcript_path,
                text_paths_json,
                tags_json,
                lang,
                telegram_file_id
            FROM videos
            WHERE status = ?
            """,
            (VideoStatus.READY.value,),
        )
        rows = await cursor.fetchall()

    for row in rows:
        text_paths = _parse_text_paths(row["text_paths_json"])
        if row["summary_path"]:
            text_paths.append(row["summary_path"])
        if row["transcript_path"]:
            text_paths.append(row["transcript_path"])
        text_paths = _dedupe_paths(text_paths)
        transcript_exists = any(
            path.lower().endswith(".txt") or path.lower().endswith(".vtt")
            for path in text_paths
        )
        if transcript_exists:
            continue
        return dict(row)
    return None


async def _process_candidate(
    row: dict[str, Any],
    storage: StorageBase,
    catalog: CatalogService,
    index_service: IndexService,
    data_dir: Path,
    transcriber,
    auto_meta_mode: str,
    logger: logging.Logger,
) -> None:
    video_id = row["video_id"]
    video_path = normalize_disk_path(row["video_path"])
    disk_folder = normalize_disk_path(row["disk_folder"])
    title = row.get("title") or disk_folder

    tmp_dir = Path(data_dir) / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=tmp_dir) as workdir:
        ext = Path(video_path).suffix or ".mp4"
        local_video = os.path.join(workdir, f"source_video{ext}")
        await storage.download_file(video_path, local_video)

        segments, _info = transcriber.transcribe(local_video)
        segments_list = list(segments)

        transcript_text = "\n".join(segment.text.strip() for segment in segments_list if segment.text)
        transcript_vtt = _segments_to_vtt(segments_list)

        transcript_txt_path = join_disk_path(disk_folder, "transcript.txt")
        transcript_vtt_path = join_disk_path(disk_folder, "transcript.vtt")

        await storage.upload_text(transcript_txt_path, transcript_text)
        await storage.upload_text(transcript_vtt_path, transcript_vtt)

    await _update_meta_json(
        storage,
        disk_folder,
        title,
        video_path,
        [transcript_txt_path, transcript_vtt_path],
        auto_meta_mode,
        logger,
    )

    text_paths = _parse_text_paths(row.get("text_paths_json") if hasattr(row, "get") else row["text_paths_json"])
    text_paths.extend([transcript_txt_path, transcript_vtt_path])
    text_paths = _dedupe_paths(text_paths)

    summary_path = row.get("summary_path") if hasattr(row, "get") else row["summary_path"]
    transcript_path = transcript_vtt_path

    tags = _safe_load_json(row.get("tags_json") if hasattr(row, "get") else row["tags_json"]) or []
    lang = row.get("lang") if hasattr(row, "get") else row["lang"]

    meta = VideoMeta(
        id=video_id,
        title=title,
        video_path=video_path,
        summary_path=summary_path,
        transcript_path=transcript_path,
        text_paths=text_paths,
        tags=tags,
        lang=lang,
        source="auto_transcribe",
        created_at=utc_now_iso(),
    )

    video_meta = await storage.get_meta(video_path)
    text_metas = []
    for path in text_paths:
        try:
            meta_item = await storage.get_meta(path)
        except FileNotFoundError:
            continue
        text_metas.append((path, meta_item))
    fingerprint_payload = build_fingerprint_payload(video_path, video_meta, text_metas)

    entry = StorageEntry(
        folder=disk_folder,
        meta=meta,
        fingerprint=Fingerprint(payload=fingerprint_payload),
        telegram_file_id=row.get("telegram_file_id") if hasattr(row, "get") else row["telegram_file_id"],
    )
    await catalog.upsert_entry(entry, status=VideoStatus.READY)
    await index_service.index_video(video_id)

    logger.info("transcription completed", extra={"video_id": video_id})


async def _update_meta_json(
    storage: StorageBase,
    folder: str,
    title: str,
    video_path: str,
    new_texts: list[str],
    auto_meta_mode: str,
    logger: logging.Logger,
) -> None:
    meta_path = join_disk_path(folder, "meta.json")
    payload = None
    try:
        if await storage.exists(meta_path):
            payload = await storage.read_json(meta_path)
    except Exception:
        payload = None

    if payload is None:
        if (auto_meta_mode or "").strip().lower() != "write":
            return
        payload = {
            "title": title,
            "video_path": video_path,
            "texts": [],
            "source": "auto_transcribe",
            "created_at": utc_now_iso(),
        }

    texts = payload.get("texts")
    if not isinstance(texts, list):
        texts = []
    texts.extend(new_texts)
    payload["texts"] = _dedupe_paths(texts)
    payload["video_path"] = payload.get("video_path") or video_path
    payload["title"] = payload.get("title") or title

    try:
        await storage.upload_text(
            meta_path, json.dumps(payload, ensure_ascii=False, indent=2)
        )
    except Exception as exc:
        logger.warning(
            "failed to update meta.json after transcription",
            extra={"folder": folder, "error": str(exc)},
        )


def _segments_to_vtt(segments: list[Any]) -> str:
    lines = ["WEBVTT", ""]
    for idx, segment in enumerate(segments, 1):
        start = _format_vtt_time(segment.start)
        end = _format_vtt_time(segment.end)
        text = (segment.text or "").strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _format_vtt_time(seconds: float) -> str:
    total_ms = int(seconds * 1000)
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def _parse_text_paths(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [normalize_disk_path(item) for item in data if isinstance(item, str) and item.strip()]


def _safe_load_json(value: Any) -> list[str] | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return None
    if isinstance(data, list):
        return data
    return None


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
