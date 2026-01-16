from __future__ import annotations

import asyncio
import json
import logging
from pathlib import PurePosixPath
from typing import Any

from app.db import dumps_json, utc_now_iso
from app.models import Fingerprint, StorageEntry, VideoMeta, VideoStatus
from app.services.catalog_service import CatalogService
from app.services.fingerprint import build_fingerprint_payload
from app.services.storage_base import StorageBase
from app.utils import disk_basename, join_disk_path, normalize_disk_path


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".flv",
}

SUMMARY_FILENAME = "summary.md"
TRANSCRIPT_FILENAMES = ("transcript.vtt", "transcript.txt")
DESCRIPTION_FILENAMES = ("description.txt",)
TITLE_FILENAME = "title.txt"
LIBRARY_INDEX_FILENAME = "library_index.json"
SUMMARY_EXCERPT_MAX = 600


class ScanJob:
    def __init__(
        self,
        storage: StorageBase,
        catalog: CatalogService,
        root_path: str,
        stability_check_sec: int,
        auto_meta_mode: str,
    ) -> None:
        self._storage = storage
        self._catalog = catalog
        self._root_path = root_path
        self._stability_check_sec = stability_check_sec
        self._auto_meta_mode = auto_meta_mode
        self._logger = logging.getLogger("video_library_bot.scan")

    async def run_once(self) -> dict[str, int]:
        return await scan_yandex_disk_and_update_db(
            self._storage,
            self._catalog,
            self._root_path,
            self._stability_check_sec,
            self._auto_meta_mode,
            self._logger,
        )


async def scan_yandex_disk_and_update_db(
    storage: StorageBase,
    catalog: CatalogService,
    root_path: str,
    stability_check_sec: int,
    auto_meta_mode: str,
    logger: logging.Logger | None = None,
) -> dict[str, int]:
    logger = logger or logging.getLogger("video_library_bot.scan")
    root = normalize_disk_path(root_path)
    logger.info("scan started", extra={"root": root})

    mode = (auto_meta_mode or "write").strip().lower()
    if mode not in {"write", "derive", "off"}:
        mode = "write"

    auto_org_errors: list[dict[str, str]] = []
    try:
        auto_org_errors = await _auto_organize_root_files(storage, root, logger)
    except Exception:
        logger.exception("auto-organize failed", extra={"root": root})

    try:
        folders = await storage.list_folders(root)
    except Exception:
        logger.exception("scan failed: storage error")
        return {}

    total_folders_scanned = len(folders)
    meta_found = 0
    meta_derived = 0
    ready_count = 0
    needs_text_count = 0
    error_count = 0

    existing_index = await catalog.list_video_index()
    folder_set = {normalize_disk_path(folder) for folder in folders}
    seen_ids: set[str] = set()

    for error in auto_org_errors:
        error_count += 1
        folder = error["target_folder"]
        src_path = error["src"]
        error_message = (
            f"failed to move root-level video {src_path} -> "
            f"{error['target_path']}: {error['error']}"
        )
        fingerprint_payload = {
            "error": "NO_PERMISSION_MOVE",
            "message": error_message,
            "video": {"path": src_path},
        }
        entry = StorageEntry(
            folder=folder,
            meta=VideoMeta(
                id=folder,
                title=error["title"],
                video_path=src_path,
                text_paths=[],
                source="auto_scan",
                created_at=utc_now_iso(),
            ),
            fingerprint=Fingerprint(payload=fingerprint_payload),
            error_code="NO_PERMISSION_MOVE",
            error_message=error_message,
        )
        await _upsert_and_log(
            catalog, entry, VideoStatus.ERROR, existing_index, logger, fingerprint_payload
        )
        seen_ids.add(folder)

    for folder in folders:
        folder = normalize_disk_path(folder)
        if folder == root:
            continue
        folder_title = _folder_title(folder)
        try:
            entries = await storage.list_dir(folder)
        except Exception:
            error_count += 1
            logger.exception("scan failed: list_dir error", extra={"folder": folder})
            continue

        files = _collect_folder_files(folder, entries)
        title, description = await _load_title_description(
            storage, files, folder_title, logger, folder
        )
        if not title:
            title = folder_title

        meta_path = files.get("meta.json") or join_disk_path(folder, "meta.json")

        meta: VideoMeta | None = None
        meta_invalid = False
        meta_source = "meta"
        auto_meta_error: str | None = None
        meta_needs_update = False

        has_meta = "meta.json" in files
        if has_meta:
            meta_found += 1
            try:
                meta_raw = await _read_json_with_retry(storage, meta_path, logger, folder)
            except FileNotFoundError:
                logger.info(
                    "meta.json disappeared; will re-scan next cycle",
                    extra={"folder": folder, "path": meta_path},
                )
                has_meta = False
                meta_raw = None
            except ValueError as exc:
                error_count += 1
                error_message = str(exc)
                fingerprint_payload = {"error": "BAD_META_JSON", "message": error_message}
                entry = StorageEntry(
                    folder=folder,
                    meta=VideoMeta(
                        id=folder,
                        title=title,
                        video_path="",
                        text_paths=[],
                        source="meta",
                        created_at=utc_now_iso(),
                    ),
                    fingerprint=Fingerprint(payload=fingerprint_payload),
                    error_code="BAD_META_JSON",
                    error_message=error_message,
                )
                await _upsert_and_log(
                    catalog, entry, VideoStatus.ERROR, existing_index, logger, fingerprint_payload
                )
                seen_ids.add(folder)
                continue
            except Exception as exc:
                error_count += 1
                error_message = str(exc)
                fingerprint_payload = {"error": "NETWORK", "message": error_message}
                entry = StorageEntry(
                    folder=folder,
                    meta=VideoMeta(
                        id=folder,
                        title=title,
                        video_path="",
                        text_paths=[],
                        source="meta",
                        created_at=utc_now_iso(),
                    ),
                    fingerprint=Fingerprint(payload=fingerprint_payload),
                    error_code="NETWORK",
                    error_message=error_message,
                )
                await _upsert_and_log(
                    catalog, entry, VideoStatus.ERROR, existing_index, logger, fingerprint_payload
                )
                seen_ids.add(folder)
                continue
            if has_meta and meta_raw is not None:
                meta, meta_invalid = _parse_meta(meta_raw, folder, title)
                if not meta:
                    error_count += 1
                    error_message = "meta.json missing video_path"
                    fingerprint_payload = {"error": "BAD_META_JSON", "message": error_message}
                    entry = StorageEntry(
                        folder=folder,
                        meta=VideoMeta(
                            id=folder,
                            title=title,
                            video_path="",
                            text_paths=[],
                            source="meta",
                            created_at=utc_now_iso(),
                        ),
                        fingerprint=Fingerprint(payload=fingerprint_payload),
                        error_code="BAD_META_JSON",
                        error_message=error_message,
                    )
                    await _upsert_and_log(
                        catalog,
                        entry,
                        VideoStatus.ERROR,
                        existing_index,
                        logger,
                        fingerprint_payload,
                    )
                    seen_ids.add(folder)
                    continue
            else:
                has_meta = False

        if not has_meta:
            if mode == "off":
                auto_meta_error = "META_REQUIRED"
                meta = VideoMeta(
                    id=folder,
                    title=title,
                    video_path="",
                    text_paths=[],
                    source="auto_scan",
                    created_at=utc_now_iso(),
                )
            else:
                meta, auto_meta_error = _derive_meta_from_files(folder, title, files)
                meta_source = "auto_scan"
                meta_derived += 1
                meta_needs_update = True

        if not meta:
            continue

        if not meta.id:
            meta = meta.model_copy(update={"id": folder})
            meta_needs_update = True

        if meta.title:
            title = meta.title
        elif title:
            meta = meta.model_copy(update={"title": title})
            meta_needs_update = True

        has_video_candidate = _has_video_candidate(files) or bool(meta.video_path)
        if SUMMARY_FILENAME not in files and (has_video_candidate or "meta.json" in files):
            summary_text = _build_summary_text(title, description)
            if summary_text:
                summary_path = join_disk_path(folder, SUMMARY_FILENAME)
                try:
                    await storage.upload_text(summary_path, summary_text)
                    files[SUMMARY_FILENAME] = summary_path
                except Exception as exc:
                    logger.warning(
                        "failed to write summary",
                        extra={"folder": folder, "error": str(exc)},
                    )

        original_texts = _dedupe_paths(meta.text_paths)
        discovered_texts = _collect_text_files(files)
        combined_texts = _dedupe_paths(original_texts + discovered_texts)
        if combined_texts != original_texts:
            meta_needs_update = True
        meta = meta.model_copy(update={"text_paths": combined_texts})

        if auto_meta_error:
            error_count += 1
            status = VideoStatus.ERROR
            error_message = _auto_meta_error_message(auto_meta_error, folder)
            fingerprint_payload = {"error": auto_meta_error, "message": error_message}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code=auto_meta_error,
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue

        if meta_invalid or not meta.video_path:
            error_count += 1
            status = VideoStatus.ERROR
            error_message = "meta.json missing video_path"
            fingerprint_payload = {"error": "BAD_META_JSON", "message": error_message}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code="BAD_META_JSON",
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue

        try:
            resolved_meta = _resolve_meta_paths(meta, folder)
        except ValueError as exc:
            error_count += 1
            status = VideoStatus.ERROR
            error_message = str(exc)
            fingerprint_payload = {"error": "BAD_META_JSON", "message": error_message}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code="BAD_META_JSON",
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue

        meta = resolved_meta
        video_path = meta.video_path

        try:
            exists = await storage.exists(video_path)
        except Exception as exc:
            error_count += 1
            status = VideoStatus.ERROR
            error_message = str(exc)
            fingerprint_payload = {"error": "NETWORK", "message": error_message}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code="NETWORK",
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue

        if not exists:
            error_count += 1
            status = VideoStatus.ERROR
            logger.info(
                "video file not found; marking error",
                extra={"video_id": meta.id, "path": video_path},
            )
            error_message = f"video file not found: {video_path}"
            fingerprint_payload = {"error": "VIDEO_NOT_FOUND", "video": {"path": video_path}}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code="VIDEO_NOT_FOUND",
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue

        try:
            video_stable, video_meta = await _check_stability(
                storage, video_path, stability_check_sec
            )
        except FileNotFoundError:
            error_count += 1
            status = VideoStatus.ERROR
            logger.info(
                "video file not found during stability check",
                extra={"video_id": meta.id, "path": video_path},
            )
            error_message = f"video file not found: {video_path}"
            fingerprint_payload = {"error": "VIDEO_NOT_FOUND", "video": {"path": video_path}}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code="VIDEO_NOT_FOUND",
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue
        except Exception as exc:
            error_count += 1
            status = VideoStatus.ERROR
            error_message = str(exc)
            fingerprint_payload = {"error": "NETWORK", "message": error_message}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
                error_code="NETWORK",
                error_message=error_message,
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            continue

        if not video_stable:
            status = VideoStatus.NEEDS_TEXT
            logger.info(
                "video upload in progress",
                extra={"video_id": meta.id, "path": video_path},
            )
            fingerprint_payload = {"video": {"path": video_path}, "error": "unstable_video"}
            entry = StorageEntry(
                folder=folder,
                meta=meta,
                fingerprint=Fingerprint(payload=fingerprint_payload),
            )
            await _upsert_and_log(
                catalog, entry, status, existing_index, logger, fingerprint_payload
            )
            seen_ids.add(meta.id)
            needs_text_count += 1
            continue

        text_states = await _collect_text_states(
            storage, meta.text_paths, stability_check_sec, logger, meta.id
        )
        stable_texts = [state for state in text_states if state["stable"]]
        text_unstable = any(
            state["exists"] and not state["stable"] for state in text_states
        )

        if text_unstable:
            status = VideoStatus.NEEDS_TEXT
        elif stable_texts:
            status = VideoStatus.READY
        else:
            status = VideoStatus.NEEDS_TEXT

        if mode == "write" and meta_needs_update:
            await _write_meta(storage, folder, meta, meta_source, logger)

        if video_meta:
            fingerprint_payload = build_fingerprint_payload(
                video_path,
                video_meta,
                [(state["path"], state["meta"]) for state in stable_texts],
            )
        else:
            fingerprint_payload = {"error": "missing_video_meta"}

        entry = StorageEntry(
            folder=folder,
            meta=meta,
            fingerprint=Fingerprint(payload=fingerprint_payload),
        )
        await _upsert_and_log(
            catalog, entry, status, existing_index, logger, fingerprint_payload
        )
        seen_ids.add(meta.id)

        if status == VideoStatus.READY:
            ready_count += 1
        elif status == VideoStatus.NEEDS_TEXT:
            needs_text_count += 1
        else:
            error_count += 1

    deleted_ids = [
        video_id
        for video_id, record in existing_index.items()
        if video_id not in seen_ids
        and record.get("disk_folder")
        and normalize_disk_path(record["disk_folder"]) not in folder_set
    ]
    deleted_count = len(deleted_ids)
    if deleted_ids:
        await catalog.mark_deleted(deleted_ids)
        for video_id in deleted_ids:
            logger.info("scan change DELETED", extra={"video_id": video_id})

    try:
        await _update_library_index(storage, catalog, root, logger)
    except Exception:
        logger.exception("failed to update library index", extra={"root": root})

    logger.info(
        "scan report",
        extra={
            "total_folders_scanned": total_folders_scanned,
            "meta_found": meta_found,
            "meta_derived": meta_derived,
            "ready_count": ready_count,
            "needs_text_count": needs_text_count,
            "error_count": error_count,
            "deleted_count": deleted_count,
        },
    )
    return {
        "total_folders_scanned": total_folders_scanned,
        "meta_found": meta_found,
        "meta_derived": meta_derived,
        "ready_count": ready_count,
        "needs_text_count": needs_text_count,
        "error_count": error_count,
        "deleted_count": deleted_count,
    }


async def run_scan_loop(job: ScanJob, interval_sec: int) -> None:
    while True:
        await job.run_once()
        await asyncio.sleep(interval_sec)


def _parse_meta(
    meta_raw: Any, default_id: str, default_title: str
) -> tuple[VideoMeta | None, bool]:
    if not isinstance(meta_raw, dict):
        return None, True
    video_value = _coerce_str(meta_raw.get("video_path")) or _coerce_str(
        meta_raw.get("video")
    )
    text_paths = []
    raw_texts = meta_raw.get("texts") or meta_raw.get("text_paths") or []
    if isinstance(raw_texts, list):
        for item in raw_texts:
            if isinstance(item, str) and item.strip():
                text_paths.append(item.strip())
    summary_value = _coerce_optional_str(meta_raw.get("summary"))
    transcript_value = _coerce_optional_str(meta_raw.get("transcript"))
    if summary_value:
        text_paths.append(summary_value)
    if transcript_value:
        text_paths.append(transcript_value)
    text_paths = _dedupe_paths(text_paths)
    meta = VideoMeta(
        id=_coerce_str(meta_raw.get("id")) or default_id,
        title=_coerce_str(meta_raw.get("title")) or default_title,
        video_path=video_value or "",
        text_paths=text_paths,
        tags=_coerce_tags(meta_raw.get("tags")),
        lang=_coerce_optional_str(meta_raw.get("lang")),
        source=_coerce_optional_str(meta_raw.get("source")),
        created_at=_coerce_optional_str(meta_raw.get("created_at")),
    )
    return meta, not bool(video_value)


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return _coerce_str(value)


def _coerce_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result


def _folder_title(folder: str) -> str:
    name = disk_basename(folder)
    return name or folder


def _collect_folder_files(folder: str, entries: list[dict[str, Any]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for item in entries:
        if item.get("type") != "file":
            continue
        name = item.get("name") or ""
        if not name:
            path_value = item.get("path") or ""
            name = PurePosixPath(path_value).name
        if not name:
            continue
        path = item.get("path") or join_disk_path(folder, name)
        files[name.lower()] = normalize_disk_path(path)
    return files


def _collect_text_files(files: dict[str, str]) -> list[str]:
    text_paths = []
    if SUMMARY_FILENAME in files:
        text_paths.append(files[SUMMARY_FILENAME])
    for name in TRANSCRIPT_FILENAMES:
        if name in files:
            text_paths.append(files[name])
    return text_paths


def _has_video_candidate(files: dict[str, str]) -> bool:
    return any(_is_video_file(name) for name in files.keys())


def _derive_meta_from_files(
    folder: str, title: str, files: dict[str, str]
) -> tuple[VideoMeta, str | None]:
    video_candidates = [path for name, path in files.items() if _is_video_file(name)]
    if len(video_candidates) == 0:
        return (
            VideoMeta(
                id=folder,
                title=title,
                video_path="",
                text_paths=[],
                source="auto_scan",
                created_at=utc_now_iso(),
            ),
            "NO_VIDEO",
        )
    if len(video_candidates) > 1:
        return (
            VideoMeta(
                id=folder,
                title=title,
                video_path="",
                text_paths=[],
                source="auto_scan",
                created_at=utc_now_iso(),
            ),
            "MULTIPLE_VIDEOS",
        )
    text_paths = _collect_text_files(files)
    summary_path, transcript_path = _select_summary_transcript(text_paths)
    return (
        VideoMeta(
            id=folder,
            title=title,
            video_path=video_candidates[0],
            summary_path=summary_path,
            transcript_path=transcript_path,
            text_paths=text_paths,
            source="auto_scan",
            created_at=utc_now_iso(),
        ),
        None,
    )


def _is_video_file(name: str) -> bool:
    ext = PurePosixPath(name).suffix.lower()
    return ext in VIDEO_EXTENSIONS


def _resolve_meta_paths(meta: VideoMeta, folder: str) -> VideoMeta:
    video_path = _resolve_path(folder, meta.video_path)
    text_paths = []
    for text_path in meta.text_paths:
        text_paths.append(_resolve_path(folder, text_path))
    text_paths = _dedupe_paths(text_paths)
    summary_path, transcript_path = _select_summary_transcript(text_paths)
    return meta.model_copy(
        update={
            "video_path": video_path,
            "text_paths": text_paths,
            "summary_path": summary_path,
            "transcript_path": transcript_path,
        }
    )


def _select_summary_transcript(text_paths: list[str]) -> tuple[str | None, str | None]:
    summary_path = None
    transcript_vtt = None
    transcript_txt = None
    for path in text_paths:
        name = PurePosixPath(_strip_disk_prefix(path)).name.lower()
        if name.endswith(".md") and not summary_path:
            summary_path = path
        if name.endswith(".vtt") and not transcript_vtt:
            transcript_vtt = path
        if name.endswith(".txt") and not transcript_txt:
            transcript_txt = path
    return summary_path, transcript_vtt or transcript_txt


def _strip_disk_prefix(path: str) -> str:
    normalized = normalize_disk_path(path)
    return normalized[len("disk:") :]


def _resolve_path(folder: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("empty path in meta.json")
    cleaned = value.strip().replace("\\", "/")
    parts = PurePosixPath(cleaned).parts
    if ".." in parts:
        raise ValueError("path traversal in meta.json")
    if cleaned.startswith("disk:") or cleaned.startswith("/disk:") or cleaned.startswith("/"):
        return normalize_disk_path(cleaned)
    return join_disk_path(folder, cleaned)


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


def _build_summary_text(title: str, description: str) -> str:
    title = (title or "").strip()
    description = (description or "").strip()
    if title and description:
        return f"{title}\n\n{description}"
    return title or description


async def _load_title_description(
    storage: StorageBase,
    files: dict[str, str],
    default_title: str,
    logger: logging.Logger,
    folder: str,
) -> tuple[str, str]:
    title = default_title
    description = ""

    title_path = files.get(TITLE_FILENAME)
    if title_path:
        try:
            title_text = await _read_text_with_retry(storage, title_path)
            _log_if_replacement(title_text, logger, folder, title_path)
            candidate = _first_non_empty_line(title_text)
            if candidate:
                title = candidate
        except FileNotFoundError:
            logger.info(
                "title.txt disappeared; will re-scan next cycle",
                extra={"folder": folder, "path": title_path},
            )
        except Exception as exc:
            logger.warning(
                "failed to read title.txt",
                extra={"folder": folder, "error": str(exc)},
            )

    for name in DESCRIPTION_FILENAMES:
        desc_path = files.get(name)
        if not desc_path:
            continue
        try:
            description = (await _read_text_with_retry(storage, desc_path)).strip()
            _log_if_replacement(description, logger, folder, desc_path)
        except FileNotFoundError:
            logger.info(
                "description.txt disappeared; will re-scan next cycle",
                extra={"folder": folder, "path": desc_path},
            )
        except Exception as exc:
            logger.warning(
                "failed to read description.txt",
                extra={"folder": folder, "error": str(exc)},
            )
        break

    return title, description


def _first_non_empty_line(text: str) -> str:
    for line in (text or "").splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


async def _read_text_with_retry(storage: StorageBase, path: str, attempts: int = 2) -> str:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return await storage.read_text(path)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                raise FileNotFoundError(path) from exc
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(0.2)
                continue
            break
    if last_exc:
        raise last_exc
    return ""


async def _read_json_with_retry(
    storage: StorageBase, path: str, logger: logging.Logger, folder: str, attempts: int = 2
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            text = await storage.read_text(path)
            _log_if_replacement(text, logger, folder, path)
            return json.loads(text)
        except ValueError as exc:
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(0.2)
                continue
            raise ValueError(f"Invalid JSON in {path}") from exc
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                raise FileNotFoundError(path) from exc
            last_exc = exc
            if attempt < attempts - 1:
                await asyncio.sleep(0.2)
                continue
            raise
    if last_exc:
        raise last_exc
    return {}


def _log_if_replacement(text: str, logger: logging.Logger, folder: str, path: str) -> None:
    if "\ufffd" in (text or ""):
        logger.warning(
            "non-utf8 text replaced",
            extra={"folder": folder, "path": path},
        )


async def _auto_organize_root_files(
    storage: StorageBase,
    root: str,
    logger: logging.Logger,
) -> list[dict[str, str]]:
    entries = await storage.list_dir(root)
    errors: list[dict[str, str]] = []
    for item in entries:
        if item.get("type") != "file":
            continue
        name = item.get("name") or ""
        if not name:
            path_value = item.get("path") or ""
            name = PurePosixPath(path_value).name
        if not name:
            continue
        if not _is_video_file(name):
            continue
        stem = PurePosixPath(name).stem.strip()
        if not stem:
            continue
        src_path = item.get("path") or join_disk_path(root, name)
        src_path = normalize_disk_path(src_path)
        target_folder = join_disk_path(root, stem)
        target_path = join_disk_path(target_folder, name)
        if src_path == target_path:
            continue
        try:
            await storage.create_dir(target_folder)
        except Exception as exc:
            errors.append(
                {
                    "src": src_path,
                    "target_folder": target_folder,
                    "target_path": target_path,
                    "title": stem,
                    "error": str(exc),
                }
            )
            logger.warning(
                "auto-organize create_dir failed",
                extra={"src": src_path, "dst": target_path, "error": str(exc)},
            )
            continue
        try:
            await storage.move(src_path, target_path, overwrite=False)
            logger.info(
                "auto-organize moved",
                extra={"src": src_path, "dst": target_path},
            )
        except Exception as exc:
            errors.append(
                {
                    "src": src_path,
                    "target_folder": target_folder,
                    "target_path": target_path,
                    "title": stem,
                    "error": str(exc),
                }
            )
            logger.warning(
                "auto-organize move failed",
                extra={"src": src_path, "dst": target_path, "error": str(exc)},
            )
    return errors


def _auto_meta_error_message(code: str, folder: str) -> str:
    if code == "NO_VIDEO":
        return f"no video file found in {folder}"
    if code == "MULTIPLE_VIDEOS":
        return f"multiple video files found in {folder}"
    if code == "META_REQUIRED":
        return "meta.json is required when AUTO_META_MODE=off"
    return code


async def _check_stability(
    storage: StorageBase, path: str, stability_check_sec: int
) -> tuple[bool, dict[str, Any]]:
    first = await storage.get_meta(path)
    if stability_check_sec <= 0:
        return True, first
    await asyncio.sleep(stability_check_sec)
    second = await storage.get_meta(path)
    stable = (
        first.get("size") == second.get("size")
        and first.get("modified") == second.get("modified")
    )
    return stable, second


async def _collect_text_states(
    storage: StorageBase,
    text_paths: list[str],
    stability_check_sec: int,
    logger: logging.Logger,
    video_id: str,
) -> list[dict[str, Any]]:
    states = []
    for path in text_paths:
        try:
            exists = await storage.exists(path)
        except Exception as exc:
            logger.warning(
                "text exists check failed",
                extra={"video_id": video_id, "path": path, "error": str(exc)},
            )
            continue
        if not exists:
            continue
        stable = False
        meta: dict[str, Any] | None = None
        try:
            stable, meta = await _check_stability(storage, path, stability_check_sec)
        except FileNotFoundError:
            logger.warning(
                "text missing during stability check",
                extra={"video_id": video_id, "path": path},
            )
            continue
        except Exception as exc:
            logger.warning(
                "text stability check failed",
                extra={"video_id": video_id, "path": path, "error": str(exc)},
            )
            continue
        if not stable:
            logger.info(
                "text upload in progress",
                extra={"video_id": video_id, "path": path},
            )
        states.append(
            {
                "path": path,
                "stable": stable,
                "exists": exists,
                "meta": meta or {},
                "type": _classify_text_path(path),
            }
        )
    return states


def _classify_text_path(path: str) -> str:
    name = PurePosixPath(_strip_disk_prefix(path)).name.lower()
    if name.endswith(".vtt") or name.endswith(".txt"):
        return "transcript"
    if name.endswith(".md"):
        return "summary"
    return "other"


async def _write_meta(
    storage: StorageBase,
    folder: str,
    meta: VideoMeta,
    meta_source: str,
    logger: logging.Logger,
) -> None:
    payload = {
        "title": meta.title,
        "video_path": meta.video_path,
        "texts": meta.text_paths,
        "source": meta.source or meta_source or "auto_scan",
        "created_at": meta.created_at or utc_now_iso(),
    }
    meta_path = join_disk_path(folder, "meta.json")
    try:
        await storage.upload_text(
            meta_path, json.dumps(payload, ensure_ascii=False, indent=2)
        )
    except Exception as exc:
        logger.warning(
            "failed to write meta.json",
            extra={"folder": folder, "error": str(exc)},
        )


async def _update_library_index(
    storage: StorageBase,
    catalog: CatalogService,
    root: str,
    logger: logging.Logger,
) -> None:
    records = await catalog.list_all_videos()
    payload_items = []
    for record in records:
        text_paths = _parse_text_paths_json(record.text_paths_json)
        if record.summary_path:
            text_paths.append(record.summary_path)
        if record.transcript_path:
            text_paths.append(record.transcript_path)
        text_paths = _dedupe_paths(text_paths)

        summary_excerpt = await _load_excerpt(
            storage, record.summary_path, text_paths, logger
        )
        fingerprint_hash = _extract_fingerprint_hash(record.fingerprint_json)

        payload_items.append(
            {
                "video_id": record.video_id,
                "title": record.title,
                "video_path": record.video_path,
                "texts": text_paths,
                "summary_excerpt": summary_excerpt,
                "fingerprint": fingerprint_hash,
                "updated_at": record.updated_at,
                "status": record.status.value,
                "error_code": record.error_code,
                "error_message": record.error_message,
            }
        )

    payload = json.dumps(
        {
            "schema_version": 1,
            "generated_at": utc_now_iso(),
            "items": payload_items,
        },
        ensure_ascii=False,
        indent=2,
    )
    index_path = join_disk_path(root, LIBRARY_INDEX_FILENAME)
    tmp_path = join_disk_path(root, f"{LIBRARY_INDEX_FILENAME}.tmp")
    try:
        await storage.upload_text(tmp_path, payload)
        await storage.move(tmp_path, index_path, overwrite=True)
    except Exception as exc:
        logger.warning(
            "failed to write library index",
            extra={"path": index_path, "error": str(exc)},
        )
        try:
            await storage.upload_text(index_path, payload)
        except Exception as fallback_exc:
            logger.warning(
                "failed to write library index fallback",
                extra={"path": index_path, "error": str(fallback_exc)},
            )


async def _load_excerpt(
    storage: StorageBase,
    summary_path: str | None,
    text_paths: list[str],
    logger: logging.Logger,
) -> str:
    candidates = []
    if summary_path:
        candidates.append(summary_path)
    for path in text_paths:
        if summary_path and path == summary_path:
            continue
        candidates.append(path)
    for path in candidates:
        try:
            text = await storage.read_text(path)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                logger.info(
                    "text disappeared; will re-scan next cycle",
                    extra={"path": path},
                )
            else:
                logger.debug(
                    "failed to read excerpt",
                    extra={"path": path, "error": str(exc)},
                )
            continue
        cleaned = " ".join((text or "").split())
        if cleaned:
            return cleaned[:SUMMARY_EXCERPT_MAX]
    return ""


def _extract_fingerprint_hash(fingerprint_json: str) -> str:
    if not fingerprint_json:
        return ""
    try:
        data = json.loads(fingerprint_json)
    except ValueError:
        return ""
    if isinstance(data, dict):
        return str(data.get("hash") or "")
    return ""


def _parse_text_paths_json(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [normalize_disk_path(item) for item in data if isinstance(item, str) and item.strip()]


async def _upsert_and_log(
    catalog: CatalogService,
    entry: StorageEntry,
    status: VideoStatus,
    existing_index: dict[str, dict[str, str | None]],
    logger: logging.Logger,
    fingerprint_payload: dict[str, Any],
) -> None:
    fingerprint_json = dumps_json(fingerprint_payload)
    existing = existing_index.get(entry.meta.id)
    if existing is None:
        logger.info("scan change NEW", extra={"video_id": entry.meta.id})
    else:
        changed = (
            existing.get("fingerprint_json") != fingerprint_json
            or existing.get("status") != status.value
            or normalize_disk_path(existing.get("disk_folder") or "")
            != normalize_disk_path(entry.folder)
        )
        if changed:
            logger.info("scan change UPDATED", extra={"video_id": entry.meta.id})
    if status == VideoStatus.ERROR:
        logger.info("scan change ERROR", extra={"video_id": entry.meta.id})
    await catalog.upsert_entry(entry, status=status)
