from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tcpainfinder.categorize import categorize_text
from tcpainfinder.detect import classify_intent, compute_fit_for_me_score, compute_money_signal_score
from tcpainfinder.models import AnalysisConfig, ChatExport, ChatMessage
from tcpainfinder.telegram_html import load_html_exports_from_path
from tcpainfinder.text import build_text_pack
from tcpainfinder.utils import infer_chat_key


def _parse_message_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _parse_telegram_datetime(msg: dict[str, Any]) -> datetime | None:
    ts = msg.get("date_unixtime")
    if isinstance(ts, str) and ts.isdigit():
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(ts, int):
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    date_str = msg.get("date")
    if isinstance(date_str, str):
        # Typical Telegram export: "2024-01-01T12:34:56"
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _is_service_message(msg: dict[str, Any]) -> bool:
    if msg.get("type") == "service":
        return True
    text = msg.get("text")
    if text in (None, "", []):
        return True
    # Some exports store service-ish messages as short strings.
    if isinstance(text, str) and text.strip().lower() in {"joined", "left"}:
        return True
    return False


def _looks_like_export(obj: object) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("messages"), list)


def load_export(json_path: Path, *, config: AnalysisConfig) -> ChatExport | None:
    try:
        with json_path.open("r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {json_path} ({exc})") from exc
    except OSError as exc:
        raise ValueError(f"Cannot read file: {json_path} ({exc})") from exc

    if not _looks_like_export(data):
        return None

    chat_key = infer_chat_key(json_path)
    display_name = data.get("name") if isinstance(data.get("name"), str) else chat_key
    messages_raw = data.get("messages", [])
    total_messages = len(messages_raw) if isinstance(messages_raw, list) else 0

    now = datetime.now(tz=timezone.utc)
    since_dt = now - timedelta(days=max(0, int(config.since_days)))

    parsed: list[ChatMessage] = []
    parsed_count = 0
    for item in messages_raw:
        if not isinstance(item, dict):
            continue
        if _is_service_message(item):
            continue

        dt = _parse_telegram_datetime(item)
        if dt is None or dt < since_dt:
            continue

        text_raw = _parse_message_text(item.get("text"))
        author = item.get("from") if isinstance(item.get("from"), str) else None
        pack = build_text_pack(text_raw, lang=config.lang)
        if len(pack.normalized) < config.min_message_length:
            continue

        text_lower = pack.redacted.lower()
        intent_res = classify_intent(text_lower, pack.normalized)
        category = categorize_text(pack.normalized)
        money_score = compute_money_signal_score(text_lower)
        fit_score = compute_fit_for_me_score(pack.normalized, intent=intent_res.intent, category=category)

        parsed.append(
            ChatMessage(
                chat_key=chat_key,
                chat_name=display_name,
                source_path=json_path,
                dt=dt,
                author=author,
                text_raw=text_raw,
                text_redacted=pack.redacted,
                text_norm=pack.normalized,
                tokens=pack.tokens,
                intent=intent_res.intent,
                intent_confidence=round(intent_res.confidence, 3),
                intent_tags=intent_res.tags,
                money_signal_score=money_score,
                fit_for_me_score=fit_score,
                category=category,
            )
        )
        parsed_count += 1

    return ChatExport(
        chat_key=chat_key,
        display_name=display_name,
        source_path=json_path,
        total_messages_in_file=total_messages,
        parsed_messages=parsed_count,
        messages=tuple(parsed),
    )


def _find_json_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        return []
    # Telegram Desktop JSON exports are typically named result.json (or result*.json).
    return sorted([p for p in input_path.rglob("result*.json") if p.is_file()])


def load_exports_from_path(input_path: Path, *, config: AnalysisConfig) -> list[ChatExport]:
    if not input_path.exists():
        raise ValueError(f"Input path does not exist: {input_path}")

    # Prefer machine-readable JSON exports; if none found, fall back to Telegram HTML exports.
    json_files = _find_json_files(input_path)
    if not json_files:
        html_exports = load_html_exports_from_path(input_path, config=config)
        if html_exports:
            logging.info("Loaded Telegram HTML exports: %d", len(html_exports))
            return html_exports
        raise ValueError(
            f"No Telegram exports found in: {input_path} "
            "(expected Telegram Desktop export as JSON with 'messages', or HTML with messages.html)."
        )

    logging.info("JSON files found: %d", len(json_files))

    exports: list[ChatExport] = []
    invalid_json = 0
    for path in json_files:
        try:
            exp = load_export(path, config=config)
        except ValueError as exc:
            # In directory mode, keep going; at the end, fail if nothing loaded.
            invalid_json += 1
            logging.warning("%s", exc)
            continue
        if exp is None:
            continue
        exports.append(exp)

    if not exports:
        raise ValueError(
            "No Telegram chat exports loaded from JSON files. "
            f"Checked {len(json_files)} JSON files; invalid JSON files: {invalid_json}."
        )
    return exports
