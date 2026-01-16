"""
Унифицированный провайдер для генерации изображений по промту
Централизует все вызовы генерации изображений в одном месте
"""
from __future__ import annotations

import os
import io
import base64
import asyncio
from typing import Optional

import httpx
from PIL import Image

from .neuroapi import image_generation, IMAGE_MODEL


async def generate_image_bytes(
    prompt: str, 
    width: int = 1080, 
    height: int = 1350, 
    **kwargs
) -> bytes:
    """
    Унифицирует генерацию изображения по промту.
    Возвращает raw bytes изображения (PNG/JPEG).
    Бросает исключение при ошибке (с понятным сообщением).
    
    Args:
        prompt: Текстовый промпт для генерации
        width: Ширина изображения (по умолчанию 1080)
        height: Высота изображения (по умолчанию 1350)
        **kwargs: Дополнительные параметры (например, model, size)
    
    Returns:
        bytes: Raw bytes изображения (PNG/JPEG)
    
    Raises:
        RuntimeError: Если генерация не удалась
        ValueError: Если промпт невалиден
    """
    # Защита от регрессий: проверяем что не используется chat_completion
    if "chat_completion" in str(kwargs) or "chat" in str(kwargs).lower():
        raise RuntimeError("Image generation attempted via Chat API — use image_generation()")
    
    # Жёсткая валидация промпта
    assert prompt and isinstance(prompt, str), "prompt must be a non-empty string"
    prompt = prompt.strip()
    assert prompt, "Empty prompt for image generation"
    
    # Получаем модель из env
    model = os.getenv("NEUROAPI_IMAGE_MODEL", "gpt-image-1")
    
    # Преобразуем width x height в строку размера (поддерживаемые форматы API)
    # Для gpt-image-1 используем только проверенные размеры: "1024x1024" (безопасный вариант)
    # Если нужны другие размеры - нужно проверять поддержку конкретной модели
    size_str = kwargs.get("size")
    if not size_str:
        # Для gpt-image-1 используем квадратный формат (самый надежный)
        # Можно попробовать другие размеры, но 1024x1024 гарантированно работает
        if model == "gpt-image-1":
            size_str = "1024x1024"  # Безопасный размер для gpt-image-1
        else:
            # Для других моделей пробуем сохранить ориентацию
            if height > width:
                # Вертикальный - используем квадрат для совместимости
                size_str = "1024x1024"
            elif width > height:
                # Горизонтальный - используем квадрат для совместимости
                size_str = "1024x1024"
            else:
                # Квадратный
                size_str = "1024x1024"
    
    # Логируем запрос
    print(f"[image_provider] prompt='{prompt[:120]}{'...' if len(prompt) > 120 else ''}'")
    print(f"[image_provider] model={model} size={size_str} (requested: {width}x{height})")
    
    # Ретраи с экспоненциальной паузой
    max_retries = 3
    delay = 1.0
    last_error = None
    
    # Для gpt-image-1 принудительно используем 1024x1024
    if model == "gpt-image-1" and size_str != "1024x1024":
        print(f"[image_provider] ⚠️ Для gpt-image-1 принудительно используем размер 1024x1024 (запрошен: {size_str})")
        size_str = "1024x1024"
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[image_provider] Попытка {attempt}/{max_retries}...")
            
            # Вызываем image_generation() напрямую
            data = await image_generation(
                model=model,
                prompt=prompt,
                size=size_str,
                **{k: v for k, v in kwargs.items() if k != "model" and k != "size"}
            )
            
            # Парсим ответ (поддерживаем base64 и URL)
            raw_bytes = None
            
            # Вариант 1: {"data": [{"b64_json": "..."}]}
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                item = data["data"][0]
                if "b64_json" in item:
                    raw_bytes = base64.b64decode(item["b64_json"])
                    print(f"[image_provider] ✅ Decoded base64 image: {len(raw_bytes)} bytes")
                elif "url" in item:
                    # Скачиваем по URL
                    async with httpx.AsyncClient(timeout=60.0) as cli:
                        img_resp = await cli.get(item["url"])
                        if img_resp.status_code == 200:
                            raw_bytes = img_resp.content
                            print(f"[image_provider] ✅ Downloaded image from URL: {len(raw_bytes)} bytes")
                        else:
                            raise RuntimeError(f"Failed to download image: HTTP {img_resp.status_code}")
            
            # Вариант 2: прямой формат
            if raw_bytes is None:
                if "b64_json" in data:
                    raw_bytes = base64.b64decode(data["b64_json"])
                elif "url" in data:
                    async with httpx.AsyncClient(timeout=60.0) as cli:
                        img_resp = await cli.get(data["url"])
                        if img_resp.status_code == 200:
                            raw_bytes = img_resp.content
                        else:
                            raise RuntimeError(f"Failed to download image: HTTP {img_resp.status_code}")
            
            if raw_bytes is None:
                raise RuntimeError("No image data found in API response")
            
            print(f"[image_provider] generated background ok (bytes={len(raw_bytes)})")
            break  # Успешно - выходим из цикла
            
        except RuntimeError as e:
            last_error = e
            if attempt < max_retries:
                print(f"[image_provider] ⚠️ Ошибка (попытка {attempt}/{max_retries}): {e}")
                print(f"[image_provider] Ждём {delay:.1f} сек перед повтором...")
                await asyncio.sleep(delay)
                delay *= 2  # Экспоненциальная пауза
            else:
                print(f"[image_provider] ❌ Все попытки исчерпаны: {e}")
                raise
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"[image_provider] ⚠️ Неожиданная ошибка (попытка {attempt}/{max_retries}): {type(e).__name__}: {e}")
                await asyncio.sleep(delay)
                delay *= 2
            else:
                error_msg = f"Ошибка генерации изображения: {type(e).__name__}: {str(e)}"
                print(f"[image_provider] ❌ {error_msg}")
                raise RuntimeError(error_msg) from e
    
    # Если дошли сюда без raw_bytes - ошибка
    if raw_bytes is None:
        raise RuntimeError(f"Не удалось получить изображение после {max_retries} попыток: {last_error}")
    
    try:
        
        # Валидируем что это действительно изображение
        img_test = Image.open(io.BytesIO(raw_bytes))
        img_test.verify()
        # Переоткрываем после verify (verify закрывает файл)
        img_test = Image.open(io.BytesIO(raw_bytes))
        print(f"[image_provider] ✅ Image verified: {img_test.size} mode={img_test.mode}")
        
        return raw_bytes
        
    except Exception as e:
        print(f"[image_provider] ❌ Ошибка валидации изображения: {e}")
        raise RuntimeError(f"Полученные байты не являются валидным изображением: {e}") from e

