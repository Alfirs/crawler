from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath


_CYRILLIC_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}



def normalize_disk_path(path: str) -> str:
    normalized = (path or "").strip().replace("\\", "/")
    if normalized.startswith("/"):
        normalized = normalized[1:]
    if normalized.startswith("disk:"):
        normalized = normalized[len("disk:") :]
        if normalized.startswith("/"):
            normalized = normalized[1:]
    if not normalized:
        return "disk:/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return f"disk:{normalized}"


def join_disk_path(base: str, suffix: str) -> str:
    base_norm = normalize_disk_path(base)
    suffix_norm = (suffix or "").strip().replace("\\", "/")
    if suffix_norm.startswith("disk:") or suffix_norm.startswith("/disk:"):
        return normalize_disk_path(suffix_norm)
    if suffix_norm.startswith("/"):
        suffix_norm = suffix_norm[1:]
    base_part = base_norm[len("disk:") :]
    if suffix_norm:
        combined = f"{base_part.rstrip('/')}/{suffix_norm}"
    else:
        combined = base_part
    return normalize_disk_path(combined)


def disk_basename(path: str) -> str:
    normalized = normalize_disk_path(path)
    path_part = normalized[len("disk:") :]
    return PurePosixPath(path_part).name


def slugify(value: str, max_len: int = 60) -> str:
    text = (value or "").strip().lower()
    translit = []
    for char in text:
        if char in _CYRILLIC_MAP:
            translit.append(_CYRILLIC_MAP[char])
        else:
            translit.append(char)
    text = "".join(translit)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        text = "video"
    return text[:max_len].strip("-")


def safe_filename(
    filename: str,
    fallback: str = "video",
    default_ext: str = ".mp4",
    max_len: int = 80,
) -> str:
    name = (filename or "").strip()
    if not name:
        return f"{fallback}{default_ext}"
    if "." in name:
        base, ext = name.rsplit(".", 1)
        ext = f".{ext.lower()}"
    else:
        base, ext = name, default_ext
    base_slug = slugify(base)
    safe_ext = re.sub(r"[^a-z0-9.]", "", ext.lower())
    if not safe_ext.startswith("."):
        safe_ext = default_ext
    if not base_slug:
        base_slug = fallback
    base_slug = base_slug.strip(". ")
    if not base_slug:
        base_slug = fallback
    if base_slug.upper() in _RESERVED_NAMES:
        base_slug = f"{base_slug}_file"
    if max_len > 0 and len(base_slug) > max_len:
        base_slug = base_slug[:max_len].rstrip("-")
        if not base_slug:
            base_slug = fallback
    return f"{base_slug}{safe_ext}"


def acquire_run_lock(lock_path: Path) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.exists():
        pid = _read_pid(lock_path)
        if pid and _pid_running(pid):
            return False
        try:
            lock_path.unlink()
        except OSError:
            return False
    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        return False
    return True


def release_run_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            lock_path.unlink()
    except OSError:
        pass


def _read_pid(lock_path: Path) -> int:
    try:
        content = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return 0
    try:
        return int(content)
    except ValueError:
        return 0


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
