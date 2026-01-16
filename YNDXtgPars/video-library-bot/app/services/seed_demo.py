from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.db import utc_now_iso
from app.services.storage_base import StorageBase
from app.utils import join_disk_path, normalize_disk_path


DEMO_ITEMS = [
    {
        "folder": "Руины_катка",
        "summary": (
            "Руины катка: обзор, как выглядят руины и руины после работ. "
            "Подробный разбор: руина, руины, руинами, каток. "
            "Советы по восстановлению и анализу состояния."
        ),
    },
    {
        "folder": "Обзор_инструмента_Перо",
        "summary": (
            "Обзор инструмента Перо: как пользоваться пером, инструмент перо, "
            "векторная графика, контуры и кривые Безье. "
            "Перо как инструмент: применение пера, управление узлами, "
            "векторные контуры и построение форм. "
            "Перо, перо, перо: как пользоваться пером для точных контуров."
        ),
    },
    {
        "folder": "Разбор_мазей",
        "summary": (
            "Разбор мазей: мазь и мази, состав и применение. "
            "Разбор мазей для ухода, рекомендации по использованию."
        ),
    },
    {
        "folder": "Обзор_гайд",
        "summary": (
            "Обзор и инструкция: пошаговый гайд, шаги и контроль результата. "
            "Обзорный гайд для быстрого старта."
        ),
    },
]


async def seed_demo(
    storage: StorageBase,
    settings: Settings,
    logger: Optional[object] = None,
) -> str:
    root = normalize_disk_path(settings.yandex_disk_root)
    video_payload, video_name, source_note, temp_path = _prepare_seed_video(settings, logger)

    created = 0
    skipped = 0
    errors = 0

    for item in DEMO_ITEMS:
        folder = join_disk_path(root, item["folder"])
        title = item["folder"].replace("_", " ").strip()
        try:
            await storage.create_dir(folder)
        except Exception as exc:
            errors += 1
            if logger:
                logger.warning("seed_demo: failed to create folder", extra={"folder": folder, "error": str(exc)})
            continue

        summary_path = join_disk_path(folder, "summary.md")
        try:
            await storage.upload_text(summary_path, item["summary"])
        except Exception as exc:
            errors += 1
            if logger:
                logger.warning("seed_demo: failed to upload summary", extra={"path": summary_path, "error": str(exc)})
            continue

        video_path = join_disk_path(folder, video_name)
        try:
            exists = await storage.exists(video_path)
        except Exception:
            exists = False
        if exists:
            skipped += 1
        else:
            try:
                await storage.upload_file(video_path, video_payload)
                created += 1
            except Exception as exc:
                errors += 1
                if logger:
                    logger.warning(
                        "seed_demo: failed to upload video",
                        extra={"path": video_path, "error": str(exc)},
                    )
        meta_payload = {
            "title": title,
            "video_path": video_path,
            "texts": [summary_path],
            "source": "seed_demo",
            "created_at": utc_now_iso(),
        }
        meta_path = join_disk_path(folder, "meta.json")
        try:
            await storage.upload_text(meta_path, json.dumps(meta_payload, ensure_ascii=False, indent=2))
        except Exception as exc:
            errors += 1
            if logger:
                logger.warning("seed_demo: failed to upload meta", extra={"path": meta_path, "error": str(exc)})

    if temp_path:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass

    note = ""
    if source_note == "placeholder":
        note = "demo videos are placeholder; delivery will be link-only"
        if logger:
            logger.warning(note)
    suffix = f", note={note}" if note else ""
    return f"created={created}, skipped={skipped}, errors={errors}, source={source_note}{suffix}"


def _prepare_seed_video(settings: Settings, logger: Optional[object]):
    sample = (settings.seed_sample_video_path or "").strip()
    if sample and Path(sample).exists():
        name = Path(sample).name
        return sample, name, "sample", None

    if shutil.which("ffmpeg"):
        tmp_dir = Path(settings.data_dir) / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / "seed_demo.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=640x360:d=1",
            "-pix_fmt",
            "yuv420p",
            str(tmp_path),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return str(tmp_path), tmp_path.name, "ffmpeg", str(tmp_path)
        except Exception as exc:
            if logger:
                logger.warning("seed_demo: ffmpeg generation failed", extra={"error": str(exc)})

    placeholder = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41"
    return placeholder, "seed_demo.mp4", "placeholder", None
