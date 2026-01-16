#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os
import time
import random
from typing import Tuple

from openai import OpenAI
from openai import APIError, APITimeoutError, APIStatusError

# OpenAI configuration для генерации текста
from app.core.config import settings

OPENAI_API_KEY = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = settings.OPENAI_BASE_URL or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# OpenAI configuration removed - now using NeuroAPI


def _masked(s: str) -> str:
    """Mask sensitive strings in logs."""
    if not s:
        return ""
    if len(s) <= 12:
        return "***"
    return s[:6] + "..." + s[-4:]


def _local_fallback_text(idea: str, slides_count: int) -> str:
    """
    Простая локальная генерация: разбиваем тему на N блоков без сети.
    Чтобы рендер не падал.
    """
    from app.services.nlp_utils import normalize_spaces
    import re

    idea_clean = normalize_spaces(idea.strip() or "Твоя тема")
    topic_lower = idea_clean.lower()
    
    # Извлекаем число из темы (например, "5 ошибок" -> 5)
    number_match = re.search(r'(\d+)', idea_clean)
    extracted_number = int(number_match.group(1)) if number_match else None

    def _keywords(*extra: str) -> list[str]:
        base = [w for w in idea_clean.split() if len(w) > 3][:3]
        ext = [normalize_spaces(x).lower() for x in extra if x]
        result: list[str] = []
        for word in base + ext:
            if word and word not in result:
                result.append(word)
        return result[:5]

    # Построение слайдов с привязкой к теме
    templates = [
        (
            idea_clean,  # обложка — сама тема
            [
                f"Разберём {topic_lower} по шагам",
                "Главные ошибки и как их избежать",
                "Конкретные действия для результата",
            ],
            _keywords("цель", "старт"),
        ),
        (
            f"{extracted_number} главных ошибок" if extracted_number and extracted_number in [3, 4, 5, 6, 7] else "Главные ошибки",
            [
                "Размытые формулировки вместо чётких целей",
                "Отсутствие конкретного плана действий",
                "Игнорирование промежуточных результатов",
                "Откладывание важных решений на потом",
                "Сравнение себя с другими вместо фокуса на своём пути",
            ],
            _keywords("ошибки", "провалы"),
        ),
        (
            f"Правильный подход: {idea_clean}",
            [
                "Ставь конкретные измеримые цели",
                "Разбивай большие задачи на маленькие шаги",
                "Фиксируй прогресс и корректируй курс",
            ],
            _keywords("метод", "система"),
        ),
        (
            "Что делать прямо сейчас",
            [
                "Выбери один маленький шаг для старта",
                "Запланируй конкретное время в календаре",
                "Убери отвлекающие факторы на время работы",
            ],
            _keywords("действия", "шаг"),
        ),
        (
            "Как удержать темп и мотивацию",
            [
                "Ставь еженедельные чек-поинты",
                "Держи короткий список приоритетов",
                "Отмечай маленькие победы регулярно",
            ],
            _keywords("темп", "регулярность"),
        ),
    ]

    slides: list[dict] = []
    for idx in range(slides_count):
        template_item = templates[idx % len(templates)]
        title = template_item[0]
        bullets_raw = template_item[1]
        keywords = template_item[2]
        
        # Если bullets - это lambda/функция, вызываем её; иначе используем как есть
        if callable(bullets_raw):
            bullets = bullets_raw()
        else:
            bullets = bullets_raw
        
        # Для слайда с "Главные ошибки" и если в теме есть число, ограничиваем количество
        if "главные ошибки" in title.lower() and extracted_number and 2 <= extracted_number <= 7:
            bullets = bullets[:extracted_number]
        
        slides.append({
            "title": title,
            "bullets": bullets,
            "keywords": keywords,
        })

    return json.dumps({"slides": slides}, ensure_ascii=False, indent=2)


def _build_struct_prompt(idea: str, slides_count: int) -> str:
    idea_clean = idea.strip()
    topic_terms = " ".join(w for w in idea_clean.lower().split() if len(w) > 3)[:60]
    return f"""
Ты помогаешь создать карусель для Instagram на тему: "{idea_clean}"

ВАЖНО:
- Тема СТРОГо "{idea_clean}" — никаких других сюжетов.
- Количество слайдов: {slides_count}.
- Верни ТОЛЬКО валидный JSON без лишнего текста.

Формат JSON:
{{
  "slides": [
    {{"title": "...", "bullets": ["...", "..."], "keywords": ["..."]}},
    ...
  ]
}}

СТРОГИЕ ТРЕБОВАНИЯ:
1. Контент строго по теме «{idea_clean}». Используй ключевые слова темы: {topic_terms}
2. Ровно {slides_count} слайдов.
   - Слайд 1 (обложка): емкий лозунг + 2–3 буллета-анонса.
   - Слайды 2..{slides_count}: разные грани темы без повторов.
3. Заголовок ≤ 8 слов, конкретный и связанный с темой.
4. Буллеты: 3–4 штуки, каждый ≤ 18 слов, конкретные действия/мысли.
5. "keywords": 2–4 ключевых слова (1–2 слова), отражающих суть слайда.
6. Стиль: русский язык, обращение на «ты», без эмодзи, без CTA.
7. Формат: чистый JSON, без Markdown и комментариев.

Пример структуры для темы "Как не просрать жизнь":
{{
  "slides": [
    {{"title": "Как не просрать жизнь: постановка целей", "bullets": ["Ставь цели осознанно", "Разбивай большие цели на шаги", "Следи за прогрессом регулярно"], "keywords": ["цели", "план"]}},
    {{"title": "Главные ошибки", "bullets": ["Размытые формулировки", "Игнорируешь дедлайны", "Не фиксируешь прогресс"], "keywords": ["ошибки"]}},
    {{"title": "Как действовать", "bullets": ["Записывай конкретный план", "Разбей на этапы", "Отмечай результаты"], "keywords": ["план", "шаги"]}}
  ]
}}

Теперь создай карусель по теме "{idea_clean}" на {slides_count} слайдов:
"""


def _openai_chat_complete(user_prompt: str, *, slides_count: int, idea: str, max_retries: int = 5, timeout: int = 30) -> str:
    """Генерирует текст карусели через OpenAI API."""
    if not OPENAI_API_KEY:
        print("OpenAI: no API key, using fallback")
        return _local_fallback_text(idea, slides_count)

    system_prompt = (
        "Ты помогаешь подготовить карусель Instagram. "
        "Отвечай СТРОГО в JSON формате без дополнительного текста и комментариев. "
        "Русский язык. Без эмодзи, без CTA, без ссылок. "
        "Не трать токены на внутренние рассуждения — сразу верни готовый JSON."
    )
    user_payload = _build_struct_prompt(idea, slides_count)

    base_url = OPENAI_BASE_URL.rstrip("/") + "/" if OPENAI_BASE_URL else None
    client_timeout = max(timeout, 60)
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=base_url, timeout=client_timeout)
    
    print(f"OpenAI TEXT: model={OPENAI_MODEL}, base_url={base_url or 'default'}")

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            max_tokens_attempt = min(4000, 2000 + (attempt - 1) * 800)
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens_attempt,
                temperature=0.6,
                top_p=0.9,
            )

            usage = getattr(response, "usage", None)
            print(f"OpenAI attempt {attempt}: usage={usage}")

            text = ""
            if response.choices:
                message = response.choices[0].message
                content = getattr(message, "content", "")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts: list[str] = []
                    for part in content:
                        if isinstance(part, dict):
                            parts.append(str(part.get("text", "")))
                        elif isinstance(part, str):
                            parts.append(part)
                    text = "".join(parts)

            finish_reason = response.choices[0].finish_reason if response.choices else None

            if text:
                text = text.strip()
                print(f"OpenAI raw response (len={len(text)}):")
                print("=" * 80)
                print(text[:1000])
                print("=" * 80)

                try:
                    json_data = json.loads(text)
                except json.JSONDecodeError as exc:
                    last_err = exc
                    print(f"OpenAI JSON decode error on attempt {attempt}: {exc}")
                    print(f"Failed chunk: {text[:300]}")
                    continue

                if isinstance(json_data, dict) and "slides" in json_data:
                    slides_list = json_data.get("slides", [])
                    print(
                        f"OpenAI OK: model={OPENAI_MODEL}, attempt={attempt}, slides count={len(slides_list)}"
                    )
                    return text

                last_err = RuntimeError("Invalid JSON structure from OpenAI")
                print(
                    "OpenAI error: missing 'slides' in JSON. Keys present:",
                    list(json_data.keys()) if isinstance(json_data, dict) else json_data,
                )
                continue

            if finish_reason == "length" and attempt < max_retries:
                last_err = RuntimeError("OpenAI response truncated (finish_reason=length)")
                print("OpenAI notice: model stopped due to token limit, increasing max_tokens and retrying")
                continue

            last_err = RuntimeError("Empty content from OpenAI")
            print("OpenAI DEBUG: empty content in response")
            print(f"Response payload: {response}")

        except (APITimeoutError, APIStatusError, APIError) as exc:
            last_err = exc
            status_code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
            error_text = str(getattr(exc, "message", "")) or str(exc)
            print(
                f"OpenAI error on attempt {attempt}/{max_retries}: {type(exc).__name__}"
                f" status={status_code} message={error_text}"
            )

            error_response = getattr(exc, "response", None)
            if error_response is not None:
                try:
                    print(f"OpenAI error response: {error_response}")
                except Exception:
                    pass

            retryable = status_code in {408, 409, 429, 500, 502, 503, 504} or isinstance(exc, APITimeoutError)
            if retryable and attempt < max_retries:
                sleep_s = min(2 ** attempt, 16) + random.uniform(0, 0.6)
                print(f"Retrying in {sleep_s:.1f}s")
                time.sleep(sleep_s)
                continue
            break
        except Exception as exc:
            last_err = exc
            print(
                f"OpenAI unexpected error on attempt {attempt}/{max_retries}: {type(exc).__name__} - {exc}"
            )
            if attempt < max_retries:
                sleep_s = min(2 ** attempt, 16) + random.uniform(0, 0.6)
                print(f"Retrying in {sleep_s:.1f}s")
                time.sleep(sleep_s)
                continue
            break

    print("="*80)
    print(f"OpenAI FAILED after {max_retries} retries")
    print(f"Last error: {type(last_err).__name__ if last_err else 'unknown'}: {last_err}")
    print(f"Falling back to local text generation for idea: '{idea}'")
    print("="*80)
    return _local_fallback_text(idea, slides_count)


# _detect_mode is no longer used - kept for backward compatibility if needed elsewhere
# def _detect_mode(idea: str) -> str:
#     """Detect mode from idea text: 'advice' if contains advice markers, otherwise 'mistakes'."""
#     idea_low = idea.lower()
#     advice_markers = (
#         "лайфхак",
#         "лайфхаки",
#         "совет",
#         "советы",
#         "как сделать",
#         "пошагово",
#         "работающий способ",
#         "что делать",
#         "план",
#         "алгоритм",
#     )
#     for marker in advice_markers:
#         if marker in idea_low:
#             return "advice"
#     return "mistakes"


def _build_user_prompt(idea: str, slides_count: int) -> str:
    """Build prompt for free-format Instagram carousel content without fixed templates."""
    return f"""
Ты создаёшь текст для Instagram-карусели по теме: "{idea.strip()}".

Цель — написать {slides_count} коротких слайдов, каждый из которых легко читается и помещается на отдельную карточку (1080×1350).  
Формат — минималистичный, выразительный и визуально структурированный, как у сильных инфографических постов в Instagram.

💡 Правила:
1. **Каждый слайд — отдельная мысль.**
   В начале — короткий заголовок (1–2 строки), потом 2–4 подпункта или коротких предложения.
2. **Не используй слова "Ошибка", "Шаг", "Совет", "Обложка", "Вывод", "Итог" и прочие шаблоны.**  
   Просто пиши живой, понятный, структурированный текст.
3. **Не добавляй вступления, обложки или призывы к действию.**  
   Без "подписывайся", "пиши мне", "читай дальше".
4. **Пиши на русском языке, обращайся к читателю на "ты".**
5. **Тон:**
   - Конкретный, уверенный, немного разговорный.
   - Без канцелярщины и воды.
   - Можно слегка провокационно, но без агрессии.
6. **Ограничения по длине:**
   - Заголовок до 100 символов.
   - Каждый подпункт до 120 символов.
   - 2–4 пункта на слайд.

🎨 Визуальное оформление (опционально):
Ты можешь использовать простую разметку для акцентов:
- [[текст]] для выделения акцентным цветом (используй умеренно, только для ключевых слов)
- **текст** для жирного начертания (для важных терминов)
- __текст__ для подчёркивания (редко, только если это важно)

Не злоупотребляй разметкой — используй её только там, где это действительно усиливает смысл.

📋 Формат вывода:
Каждый слайд — это отдельный блок, разделён пустой строкой.  
Пример структуры (для ориентира):

Первая мысль
- короткое уточнение
- ещё одно уточнение с [[важным акцентом]]

Вторая мысль
- факт **ключевое слово**
- пример
- пояснение

Не добавляй слова "Слайд 1", "Слайд 2" в итоговый текст.  
Просто выведи блоки подряд с пустой строкой между ними.

Теперь сгенерируй ровно {slides_count} таких блоков.
Пиши грамотно, без орфографических ошибок.
""".strip()


def generate_carousel_text(idea: str, slides_count: int = 5, mode: str | None = None) -> str:
    """
    Генерирует текст для карусели. ВРЕМЕННО использует только локальный fallback
    (заглушка, пока нет OpenAI токена).
    """
    idea_clean = idea.strip()
    if not idea_clean:
        return ""

    # ВРЕМЕННАЯ ЗАГЛУШКА: всегда используем локальную генерацию
    print(f"TEXT_GEN: Using local fallback (OpenAI disabled for now), idea='{idea_clean}', slides={slides_count}")
    return _local_fallback_text(idea_clean, slides_count)

    # TODO: Раскомментировать когда будет OpenAI токен
    # user_prompt = _build_struct_prompt(idea_clean, slides_count)
    # try:
    #     result_text = _openai_chat_complete(user_prompt, slides_count=slides_count, idea=idea_clean)
    #     return (result_text or "").strip() or idea_clean
    # except Exception as exc:
    #     print(f"WARN Exception in generate_carousel_text: {type(exc).__name__}: {exc}")
    #     return _local_fallback_text(idea_clean, slides_count)

