from __future__ import annotations

import hashlib
from typing import Any, Iterable


def build_fingerprint_payload(
    video_path: str,
    video_meta: dict[str, Any],
    text_metas: Iterable[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    video_sig = _signature(video_meta)
    text_entries = []
    for path, meta in sorted(text_metas, key=lambda item: item[0]):
        sig = _signature(meta)
        text_entries.append({"path": path, **sig})
    pieces = [_signature_string(video_sig)]
    for entry in text_entries:
        pieces.append(_signature_string(entry))
    fingerprint = hashlib.sha256("".join(pieces).encode("utf-8")).hexdigest()
    return {
        "hash": fingerprint,
        "video": {"path": video_path, **video_sig},
        "texts": text_entries,
    }


def _signature(meta: dict[str, Any]) -> dict[str, Any]:
    etag = meta.get("etag") or meta.get("sha256") or meta.get("md5") or ""
    size = meta.get("size")
    mtime = meta.get("modified") or meta.get("mtime") or ""
    try:
        size_value = int(size) if size is not None else 0
    except (TypeError, ValueError):
        size_value = 0
    return {
        "etag": str(etag) if etag else "",
        "size": size_value,
        "mtime": str(mtime) if mtime else "",
    }


def _signature_string(sig: dict[str, Any]) -> str:
    return f"{sig.get('etag','')}|{sig.get('size','')}|{sig.get('mtime','')}"
