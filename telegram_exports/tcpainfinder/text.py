from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)\S+|\b(?:t\.me|telegram\.me|vk\.com|instagram\.com|fb\.com)/\S+"
)
_MENTION_RE = re.compile(r"(?<![\w.])@([a-z0-9_]{4,})\b", re.IGNORECASE)
_PHONE_CANDIDATE_RE = re.compile(r"(?<!\w)(\+?\d[\d\s\-().]{8,}\d)(?!\w)")

_TG_BOT_TOKEN_RE = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b")
_KEY_VALUE_TOKEN_RE = re.compile(
    r"(?i)\b(api[_-]?key|apikey|token|access[_-]?token|secret|password|pass|pwd)\b\s*[:=]\s*([A-Za-z0-9._-]{8,})"
)
_HEX_TOKEN_RE = re.compile(r"(?i)\b[a-f0-9]{32,}\b")
_GENERIC_LONG_TOKEN_RE = re.compile(r"\b(?=[A-Za-z0-9_-]{24,}\b)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_-]{24,}\b")

_WORD_RE = re.compile(r"[a-zа-яё0-9]{2,}", re.IGNORECASE)

# Minimal RU stopwords (keep small, avoid overfiltering).
_RU_STOPWORDS = {
    "и",
    "в",
    "во",
    "на",
    "по",
    "к",
    "ко",
    "с",
    "со",
    "а",
    "но",
    "или",
    "да",
    "же",
    "то",
    "ли",
    "не",
    "ни",
    "что",
    "это",
    "я",
    "мы",
    "вы",
    "он",
    "она",
    "они",
    "оно",
    "ты",
    "у",
    "от",
    "до",
    "за",
    "про",
    "для",
    "как",
    "так",
    "там",
    "тут",
    "вот",
    "еще",
    "ещё",
    "уже",
    "бы",
    "быть",
    "будет",
    "буду",
    "будем",
    "есть",
    "нет",
    "пожалуйста",
    "спасибо",
    "привет",
    "добрый",
    "день",
    "вечер",
    "утро",
    "ребят",
    "ребята",
    "коллеги",
    # Common request words (keep as stopwords to make clustering less noisy).
    "подскажите",
    "скажите",
    "нужен",
    "нужна",
    "нужно",
    "надо",
    "ищу",
    "ищем",
    "кто",
    "может",
    "есть",
    "ли",
    "сколько",
    "стоит",
    # Redaction placeholders.
    "link",
    "mention",
    "redacted",
    "email",
    "phone",
    "token",
}


@dataclass(frozen=True)
class TextPack:
    raw: str
    redacted: str
    normalized: str
    tokens: tuple[str, ...]


def _redact_phone_match(match: re.Match[str]) -> str:
    candidate = match.group(1)
    digits = re.sub(r"\D+", "", candidate)
    if len(digits) >= 10:
        return "[REDACTED_PHONE]"
    return candidate


def redact_sensitive(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00A0", " ")
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _URL_RE.sub("[LINK]", text)
    text = _MENTION_RE.sub("[MENTION]", text)
    text = _TG_BOT_TOKEN_RE.sub("[REDACTED_TOKEN]", text)

    def _kv_repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return f"{key}=[REDACTED_TOKEN]"

    text = _KEY_VALUE_TOKEN_RE.sub(_kv_repl, text)
    text = _HEX_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = _GENERIC_LONG_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = _PHONE_CANDIDATE_RE.sub(_redact_phone_match, text)
    return text


def _strip_emoji(text: str) -> str:
    # Conservative emoji/symbol removal: removes "Symbol, Other" + variation selectors.
    out: list[str] = []
    for ch in text:
        if ch in {"\uFE0F", "\u200D"}:
            continue
        cat = unicodedata.category(ch)
        if cat == "So":
            continue
        out.append(ch)
    return "".join(out)


def normalize_text(text: str, *, lang: str = "ru") -> str:
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.lower()
    text = _strip_emoji(text)
    # Replace most punctuation with spaces; keep unicode word chars (incl. Cyrillic) + digits.
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    # Treat underscores as separators (common in hashtags and usernames).
    text = text.replace("_", " ")
    # Split latin/cyrillic/digit boundaries (common in hashtags like "3dвизуализатор", "tildaразработчик").
    text = re.sub(r"(?<=\d)(?=[a-zа-яё])", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[a-z])(?=\d)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[a-z])(?=[а-яё])", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=[а-яё])(?=[a-z])", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str, *, lang: str = "ru") -> tuple[str, ...]:
    if not text:
        return ()
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    if lang.lower() == "ru":
        tokens = [t for t in tokens if t not in _RU_STOPWORDS]
    return tuple(tokens)


def strip_hashtags(text: str) -> str:
    if not text:
        return ""
    # Keep the word, remove '#' to reduce noise in titles/snippets.
    return text.replace("#", " ")


def to_one_line(text: str, *, max_len: int = 180) -> str:
    text = (text or "").replace("\r", " ").replace("\n", " ")
    text = strip_hashtags(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


def build_text_pack(text_raw: str, *, lang: str = "ru") -> TextPack:
    redacted = redact_sensitive(text_raw)
    normalized = normalize_text(redacted, lang=lang)
    tokens = tokenize(normalized, lang=lang)
    return TextPack(raw=text_raw, redacted=redacted, normalized=normalized, tokens=tokens)


def top_keywords(tokens: Iterable[str], *, k: int = 8) -> list[str]:
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    return [t for t, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]
