# app/services/style_analyzer.py
import base64
import json
import os
import requests
from pathlib import Path
from typing import Dict, Any

# NeuroAPI configuration - используем динамическое чтение через neuro_client

# Vision модель для анализа стиля
_TEXT_MODEL = "gpt-4o-mini"  # vision-модель на NeuroAPI

_STYLE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "style_analysis",
        "schema": {
            "type": "object",
            "properties": {
                "palette": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "До 6 цветов в HEX"
                },
                "lighting": {"type": "string", "description":"dark или light"},
                "mood": {"type":"string", "description":"одно слово: минимализм, уют, строгость и т.д."},
                "texture": {"type":"string", "description":"gradient, noise, или smooth"}
            },
            "required": ["palette","lighting","mood","texture"],
            "additionalProperties": False
        }
    }
}

def _img_to_data_url(image_path: str) -> str:
    p = Path(image_path)
    b = p.read_bytes()
    b64 = base64.b64encode(b).decode("utf-8")
    # data URL для совместимости vision-контента
    ext = p.suffix.lstrip('.').lower()
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b64}"

def analyze_style_from_image(image_path: str) -> Dict[str, Any]:
    """
    Анализирует стиль изображения через NeuroAPI vision модель.
    """
    from app.services.neuro_client import neuroapi_enabled, neuroapi_request
    
    if not neuroapi_enabled():
        raise RuntimeError("NEUROAPI_API_KEY is not set")
    
    data_url = _img_to_data_url(image_path)

    # Сообщения в формате NeuroAPI с vision-контентом
    messages = [{
        "role": "user",
        "content": [
            {"type": "input_text", "text":
             "Опиши стилистику изображения для дальнейшей генерации фона карусели. "
             "Верни JSON с полями: palette (массив HEX цветов, до 6 штук), "
             "mood (настроение одним словом), lighting (освещение: dark/light), "
             "texture (тип текстуры: gradient/noise/smooth). "
             "Фокус на цветовой гамме и общей атмосфере."
            },
            {"type": "input_image", "image_url": data_url}
        ]
    }]

    payload = {
        "model": _TEXT_MODEL,
        "messages": messages,
        "temperature": 0,
        "response_format": _STYLE_SCHEMA
    }

    try:
        response = neuroapi_request("chat/completions", payload)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        if isinstance(content, str):
            result = json.loads(content)
        else:
            result = content
            
# Убираем отладочные логи
        return result
        
    except Exception as e:
        raise

def fallback_style(image_path: str) -> Dict[str, Any]:
    """
    Ультра-дешёвый локальный анализ: вытаскиваем несколько доминирующих цветов
    и собираем безопасный промпт. Минимум зависимостей.
    """
    try:
        from PIL import Image
        from collections import Counter

        im = Image.open(image_path).convert("RGB").resize((64, 80))
        pixels = list(im.getdata())
        common = Counter(pixels).most_common(6)
        def to_hex(rgb): return "#{:02x}{:02x}{:02x}".format(*rgb)

        palette = [to_hex(c[0]) for c in common]
        # Простейшие эврики:
        lighting = "dark, contrast: medium"
        mood = "строгий минимализм"
        texture = "мягкий градиент с лёгким шумом"
        negative = ["лица", "текст", "логотипы", "объекты", "здания", "небо", "вода"]

        bg_prompt = (
            "Абстрактный тёмный фон для слайда Instagram-карусели, "
            "читаемый под белый текст; мягкие градиентные переходы, "
            "аккуратные абстрактные формы без узнаваемых объектов."
        )

        return {
            "palette": palette,
            "lighting": lighting,
            "mood": mood,
            "texture": texture,
        }
    except Exception as e:
        print(f"[NeuroAPI] fallback_style error: {e}")
        # Ещё более простой fallback
        return {
            "palette": ["#0f0f12", "#1a1a22", "#2a2a35"],
            "lighting": "dark",
            "mood": "минимализм",
            "texture": "gradient",
        }

