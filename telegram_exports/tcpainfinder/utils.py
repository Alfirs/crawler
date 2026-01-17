from __future__ import annotations

import hashlib
import re
from pathlib import Path


_SAFE_CHARS_RE = re.compile(r"[^a-zA-Z0-9а-яА-ЯёЁ]+")


def stable_id(text: str, *, length: int = 8) -> str:
    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()
    return digest[:length]


def sanitize_filename(text: str, *, fallback: str = "chat") -> str:
    cleaned = _SAFE_CHARS_RE.sub("_", text).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned:
        return fallback
    return cleaned[:80]


def infer_chat_key(json_path: Path) -> str:
    parent = json_path.parent.name
    stem = json_path.stem
    basis = parent if parent and parent.lower() not in {"", "exports", "export"} else stem
    basis = basis or "chat"
    safe = sanitize_filename(basis, fallback="chat")
    return safe

