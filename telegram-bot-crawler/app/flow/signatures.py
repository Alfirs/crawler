from __future__ import annotations

import hashlib
import re
from typing import Iterable

_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"\d+")
_EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]")


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_numbers(text: str) -> str:
    return _NUMBER_RE.sub("#", text)


def normalize_text(text: str, replace_numbers: bool = True) -> str:
    result = normalize_whitespace(text).lower()
    if replace_numbers:
        result = normalize_numbers(result)
    return result


def normalize_action_text(text: str) -> str:
    result = _EMOJI_RE.sub("", text)
    return normalize_whitespace(result).lower()


def compute_button_signature(buttons: Iterable[Iterable[str]]) -> str:
    rows = ["|".join(row) for row in buttons]
    return ";".join(rows)


def compute_screen_signature(
    text: str,
    buttons: Iterable[Iterable[str]],
    has_media: bool = False,
) -> str:
    normalized_text = normalize_text(text, replace_numbers=True)
    button_sig = compute_button_signature(buttons)
    media_flag = "M" if has_media else "_"
    combined = f"{normalized_text}||{button_sig}||{media_flag}"
    hash_bytes = hashlib.sha256(combined.encode("utf-8")).digest()
    return hash_bytes[:8].hex()
