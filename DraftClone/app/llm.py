import json
import os
import textwrap
from typing import Any, Dict, List

import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MAX_TITLE_WORDS = 8
MAX_BULLET_LEN = 80
MIN_BULLETS = 3
MAX_BULLETS = 5
MIN_SLIDES = 4
MAX_SLIDES = 12
MAX_SOURCE_CHARS = 4000

SYSTEM_PROMPT = """
Ты — редактор маркетинговых каруселей. Строй чёткий outline под Instagram/Telegram:
- Всегда следуй структуре JSON {"slides":[...]}.
- title ≤ 8 слов, bullets ≤ 80 символов.
- В слайдах с bullets держи 3–5 пунктов, без эмодзи и воды.
- Учитывай исходную идею: сформулируй проблему, решение, цифры, CTA.
""".strip()


class OutlineValidationError(ValueError):
    pass


FALLBACK_TEMPLATE: List[Dict[str, Any]] = [
    {"layout": "cover", "title": "Автоматизация KPI", "subtitle": "Телеграм-бот + n8n"},
    {
        "layout": "problem",
        "title": "Что болит",
        "bullets": [
            "Управление KPI идёт в Excel",
            "Нет единого окна для апдейтов",
            "Рутина съедает время лидов",
        ],
    },
    {
        "layout": "solution",
        "title": "Как решаем",
        "bullets": [
            "Telegram-бот принимает апдейты текстом/голосом",
            "n8n раскладывает данные в CRM/таблицы",
            "Темплейты постов рождаются за 5 минут",
        ],
    },
    {
        "layout": "result",
        "title": "Что получаем",
        "bullets": [
            "-90% ручных сверок",
            "Единый стиль коммуникаций",
            "Прозрачные метрики по отделам",
        ],
    },
    {
        "layout": "cta",
        "title": "Дальше",
        "bullets": [
            "Собери 3 гипотезы для пилота",
            "Подготовь mindmap сценариев",
            "Запусти тест с 1 командой",
        ],
    },
]


def _sanitize_source_text(text: str) -> str:
    candidate = (text or "").strip()
    if not candidate:
        raise OutlineValidationError("source.text is empty")
    if len(candidate) > MAX_SOURCE_CHARS:
        candidate = candidate[:MAX_SOURCE_CHARS].rstrip()
    return candidate


def _normalize_slide_count(slides: int) -> int:
    base = slides or MIN_SLIDES
    return max(MIN_SLIDES, min(base, MAX_SLIDES))


def _clip_title(value: str) -> str:
    words = (value or "").split()
    return " ".join(words[:MAX_TITLE_WORDS]) or "Идея"


def _sanitize_bullets(bullets: Any) -> List[str]:
    cleaned: List[str] = []
    for raw in bullets or []:
        text = (raw or "").strip()
        if not text:
            continue
        cleaned.append(text[:MAX_BULLET_LEN])
        if len(cleaned) == MAX_BULLETS:
            break
    if not cleaned:
        return []
    while len(cleaned) < MIN_BULLETS:
        cleaned.append("—")
    return cleaned[:MAX_BULLETS]


def _normalize_slide(slide: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(slide or {})
    normalized["layout"] = normalized.get("layout") or "idea"
    normalized["title"] = _clip_title(normalized.get("title", ""))
    if normalized.get("subtitle"):
        normalized["subtitle"] = normalized["subtitle"][:MAX_BULLET_LEN]
    if "bullets" in normalized:
        normalized["bullets"] = _sanitize_bullets(normalized.get("bullets"))
    return normalized


def _placeholder_slide(index: int, topic: str) -> Dict[str, Any]:
    snippet = textwrap.shorten(topic, width=MAX_BULLET_LEN, placeholder="…")
    return {
        "layout": "insight",
        "title": _clip_title(f"Идея {index}"),
        "bullets": [
            f"Контекст: {snippet}",
            "Выдели метрику успеха",
            "Сформулируй следующий шаг",
        ],
    }


def _normalize_outline(payload: Any, slides: int, topic: str) -> Dict[str, Any]:
    raw_slides = []
    if isinstance(payload, dict):
        raw = payload.get("slides")
        if isinstance(raw, list):
            raw_slides = raw
    normalized = [_normalize_slide(item) for item in raw_slides[:slides]]
    while len(normalized) < slides:
        normalized.append(_normalize_slide(_placeholder_slide(len(normalized) + 1, topic)))
    return {"slides": normalized}


def _fallback_outline(text: str, slides: int) -> Dict[str, Any]:
    base = [dict(slide) for slide in FALLBACK_TEMPLATE]
    topic_slide = {
        "layout": "insight",
        "title": "Контекст проекта",
        "bullets": [
            textwrap.shorten(text, width=MAX_BULLET_LEN, placeholder="…"),
            "Выдели ключевые KPI",
            "Переведи инсайт в задачу",
        ],
    }
    base.insert(-1, topic_slide)
    return _normalize_outline({"slides": base}, slides, text)


async def _openai_outline(text: str, slides: int) -> Dict[str, Any]:
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Собери {slides} слайдов-карусель по теме: {text}",
            },
        ],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except Exception:
            return _fallback_outline(text, slides)


def build_outline(text: str, slides: int):
    normalized_text = _sanitize_source_text(text)
    slide_count = _normalize_slide_count(slides)
    if not OPENAI_API_KEY:
        return _fallback_outline(normalized_text, slide_count)
    import anyio

    raw_outline = anyio.run(_openai_outline, normalized_text, slide_count)
    return _normalize_outline(raw_outline, slide_count, normalized_text)
