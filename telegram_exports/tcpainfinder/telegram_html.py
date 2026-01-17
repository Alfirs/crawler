from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from tcpainfinder.categorize import categorize_text
from tcpainfinder.detect import classify_intent, compute_fit_for_me_score, compute_money_signal_score
from tcpainfinder.models import AnalysisConfig, ChatExport, ChatMessage
from tcpainfinder.text import build_text_pack
from tcpainfinder.utils import sanitize_filename


_MESSAGES_FILE_RE = re.compile(r"^messages(?:(\d+))?\.html$", re.IGNORECASE)
_DATE_TITLE_RE = re.compile(
    r"^(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{4})\s+"
    r"(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})"
    r"(?:\s+UTC(?P<tzsign>[+-])(?P<tzh>\d{2}):(?P<tzm>\d{2}))?$"
)


def _parse_datetime_title(title: str) -> datetime | None:
    title = (title or "").strip()
    m = _DATE_TITLE_RE.match(title)
    if not m:
        return None
    try:
        dt = datetime(
            int(m.group("y")),
            int(m.group("m")),
            int(m.group("d")),
            int(m.group("h")),
            int(m.group("mi")),
            int(m.group("s")),
        )
    except ValueError:
        return None

    tzinfo = timezone.utc
    if m.group("tzsign") and m.group("tzh") and m.group("tzm"):
        sign = 1 if m.group("tzsign") == "+" else -1
        offset = timedelta(hours=int(m.group("tzh")), minutes=int(m.group("tzm"))) * sign
        tzinfo = timezone(offset)
    return dt.replace(tzinfo=tzinfo).astimezone(timezone.utc)


@dataclass(frozen=True)
class _HtmlParseResult:
    total_message_blocks: int
    default_message_blocks: int
    service_message_blocks: int
    extracted_text_messages: list[tuple[datetime, str]]


class _TelegramHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_message = False
        self._message_is_default = False
        self._message_is_service = False
        self._div_stack: list[set[str]] = []

        self._current_dt: datetime | None = None
        self._text_collecting = False
        self._text_div_level: int | None = None
        self._text_buf: list[str] = []
        self._text_segments: list[str] = []

        self.total_message_blocks = 0
        self.default_message_blocks = 0
        self.service_message_blocks = 0
        self.extracted_text_messages: list[tuple[datetime, str]] = []

    @staticmethod
    def _cls_set(attrs: list[tuple[str, str | None]]) -> set[str]:
        for k, v in attrs:
            if k == "class" and v:
                return set(v.split())
        return set()

    @staticmethod
    def _attr(attrs: list[tuple[str, str | None]], key: str) -> str | None:
        for k, v in attrs:
            if k == key:
                return v
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div":
            cls = self._cls_set(attrs)
            if not self._in_message and "message" in cls:
                self._in_message = True
                self._message_is_default = "default" in cls
                self._message_is_service = "service" in cls
                self._div_stack = [cls]

                self.total_message_blocks += 1
                if self._message_is_service:
                    self.service_message_blocks += 1
                if self._message_is_default:
                    self.default_message_blocks += 1
                return

            if self._in_message:
                self._div_stack.append(cls)

                if self._message_is_default and not self._message_is_service:
                    if "date" in cls and "details" in cls:
                        title = self._attr(attrs, "title")
                        if title:
                            dt = _parse_datetime_title(title)
                            if dt is not None:
                                self._current_dt = dt
                    if "text" in cls:
                        self._text_collecting = True
                        self._text_div_level = len(self._div_stack)
                        self._text_buf = []

        if tag == "br" and self._text_collecting:
            self._text_buf.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag != "div" or not self._in_message:
            return

        closing_cls = self._div_stack[-1] if self._div_stack else set()

        # If we are closing a text div, finalize that segment.
        if self._text_collecting and self._text_div_level == len(self._div_stack) and "text" in closing_cls:
            segment = "".join(self._text_buf)
            segment = re.sub(r"\s+", " ", segment).strip()
            if segment:
                self._text_segments.append(segment)
            self._text_collecting = False
            self._text_div_level = None
            self._text_buf = []

        if self._div_stack:
            self._div_stack.pop()

        # Message ends when stack becomes empty.
        if not self._div_stack:
            if self._message_is_default and not self._message_is_service and self._current_dt is not None:
                text = " ".join(self._text_segments).strip()
                text = re.sub(r"\s+", " ", text).strip()
                if text:
                    self.extracted_text_messages.append((self._current_dt, text))

            # Reset message state.
            self._in_message = False
            self._message_is_default = False
            self._message_is_service = False
            self._current_dt = None
            self._text_collecting = False
            self._text_div_level = None
            self._text_buf = []
            self._text_segments = []

    def handle_data(self, data: str) -> None:
        if self._text_collecting and data:
            self._text_buf.append(data)


def _messages_sort_key(path: Path) -> int:
    m = _MESSAGES_FILE_RE.match(path.name)
    if not m:
        return 0
    if not m.group(1):
        return 1
    try:
        return int(m.group(1))
    except ValueError:
        return 0


def _parse_messages_html(path: Path) -> _HtmlParseResult:
    parser = _TelegramHtmlParser()
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for chunk in iter(lambda: f.read(256_000), ""):
                if not chunk:
                    break
                parser.feed(chunk)
    except OSError as exc:
        raise ValueError(f"Cannot read file: {path} ({exc})") from exc

    return _HtmlParseResult(
        total_message_blocks=parser.total_message_blocks,
        default_message_blocks=parser.default_message_blocks,
        service_message_blocks=parser.service_message_blocks,
        extracted_text_messages=parser.extracted_text_messages,
    )


def load_html_export_from_dir(chat_dir: Path, *, config: AnalysisConfig) -> ChatExport | None:
    if not chat_dir.is_dir():
        return None

    html_files = [p for p in chat_dir.glob("messages*.html") if p.is_file() and _MESSAGES_FILE_RE.match(p.name)]
    if not html_files:
        return None

    chat_key = sanitize_filename(chat_dir.name, fallback="chat")
    display_name = chat_dir.name

    now = datetime.now(tz=timezone.utc)
    since_dt = now - timedelta(days=max(0, int(config.since_days)))

    total_blocks = 0
    parsed_messages: list[ChatMessage] = []
    parsed_count = 0

    for path in sorted(html_files, key=_messages_sort_key):
        res = _parse_messages_html(path)
        total_blocks += res.total_message_blocks

        for dt, text_raw in res.extracted_text_messages:
            if dt < since_dt:
                continue

            pack = build_text_pack(text_raw, lang=config.lang)
            if len(pack.normalized) < config.min_message_length:
                continue

            lower = pack.redacted.lower()
            intent_res = classify_intent(lower, pack.normalized)
            category = categorize_text(pack.normalized)
            fit_score = compute_fit_for_me_score(pack.normalized, intent=intent_res.intent, category=category)
            parsed_messages.append(
                ChatMessage(
                    chat_key=chat_key,
                    chat_name=display_name,
                    source_path=path,
                    dt=dt,
                    author=None,
                    text_raw=text_raw,
                    text_redacted=pack.redacted,
                    text_norm=pack.normalized,
                    tokens=pack.tokens,
                    intent=intent_res.intent,
                    intent_confidence=round(intent_res.confidence, 3),
                    intent_tags=intent_res.tags,
                    money_signal_score=compute_money_signal_score(lower),
                    fit_for_me_score=fit_score,
                    category=category,
                )
            )
            parsed_count += 1

    if not parsed_messages:
        # Still return export with 0 messages for visibility? Keep None to avoid noise.
        logging.info("No messages matched filters in: %s", chat_dir)
        return ChatExport(
            chat_key=chat_key,
            display_name=display_name,
            source_path=chat_dir,
            total_messages_in_file=total_blocks,
            parsed_messages=0,
            messages=tuple(),
        )

    return ChatExport(
        chat_key=chat_key,
        display_name=display_name,
        source_path=chat_dir,
        total_messages_in_file=total_blocks,
        parsed_messages=parsed_count,
        messages=tuple(parsed_messages),
    )


def load_html_exports_from_path(input_path: Path, *, config: AnalysisConfig) -> list[ChatExport]:
    if input_path.is_file():
        # Treat a single HTML file as a "chat dir" export with one file.
        if input_path.suffix.lower() != ".html":
            return []
        chat_dir = input_path.parent
        exp = load_html_export_from_dir(chat_dir, config=config)
        return [exp] if exp else []

    if not input_path.is_dir():
        return []

    chat_dirs: set[Path] = set()
    for p in input_path.rglob("messages.html"):
        if p.is_file():
            chat_dirs.add(p.parent)

    exports: list[ChatExport] = []
    for chat_dir in sorted(chat_dirs):
        exp = load_html_export_from_dir(chat_dir, config=config)
        if exp is not None:
            exports.append(exp)

    return exports
