"""
NeuroAPI service - обёртка для работы с chat и image генерацией
"""
import os
import json
import asyncio
import httpx
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Конфигурация NeuroAPI
BASE = os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host")
KEY = os.getenv("NEUROAPI_API_KEY", "")
TEXT_MODEL = os.getenv("NEUROAPI_TEXT_MODEL", "gpt-5-mini")
IMAGE_MODEL = os.getenv("NEUROAPI_IMAGE_MODEL", "gpt-image-1")
DRYRUN = os.getenv("NEUROAPI_DRYRUN", "false").lower() == "true"

# Заголовки для авторизации
HEADERS = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json"
}


async def _retry_request(method: str, url: str, **kw):
    """
    Выполняет HTTP запрос с повторными попытками и улучшенной обработкой ошибок
    
    Args:
        method: HTTP метод (GET, POST, etc.)
        url: URL для запроса
        **kw: Дополнительные параметры для httpx (headers, json, etc.)
    
    Returns:
        httpx.Response объект
    
    Raises:
        RuntimeError: Если запрос не удался после всех попыток
    """
    # Проверяем наличие API ключа
    if not KEY:
        error_msg = "NEUROAPI_API_KEY не установлен в переменных окружения"
        print(f"[Retry Request] ❌ ОШИБКА: {error_msg}")
        raise RuntimeError(error_msg)
    
    # Увеличиваем таймаут для генерации изображений
    is_image_generation = "/images/generations" in url
    timeout_value = 120.0 if is_image_generation else 60.0
    
    delay = 1.0
    max_retries = 3
    
    last_error = None
    last_status = None
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[Retry Request] Попытка {attempt}/{max_retries}: {method} {url}")
            if attempt > 1:
                print(f"[Retry Request] Задержка перед повтором: {delay:.1f} сек")
            
            async with httpx.AsyncClient(timeout=timeout_value) as cli:
                resp = await cli.request(method, url, **kw)
            
            # Логируем статус код
            print(f"[Retry Request] Статус код: {resp.status_code}")
            
            # 2xx - успех
            if 200 <= resp.status_code < 300:
                print(f"[Retry Request] ✅ Запрос успешен")
                return resp
            
            # 4xx ошибки (клиентские) - не повторяем, возвращаем сразу
            if 400 <= resp.status_code < 500:
                error_msg = f"Client error {resp.status_code}: {resp.text[:200]}"
                print(f"[Retry Request] ❌ Клиентская ошибка (не повторяем): {error_msg}")
                
                # Детальная обработка частых ошибок
                if resp.status_code == 401:
                    raise RuntimeError("Неверный API ключ. Проверьте NEUROAPI_API_KEY в .env файле")
                elif resp.status_code == 403:
                    raise RuntimeError("Доступ запрещён. Проверьте права доступа API ключа")
                elif resp.status_code == 404:
                    raise RuntimeError(f"Ресурс не найден: {url}")
                elif resp.status_code == 429:
                    raise RuntimeError("Превышен лимит запросов. Подождите и повторите попытку")
                else:
                    raise RuntimeError(error_msg)
            
            # 5xx ошибки (серверные) - повторяем
            if 500 <= resp.status_code < 600:
                last_status = resp.status_code
                error_text = resp.text[:200] if hasattr(resp, 'text') else "No response text"
                last_error = f"Server error {resp.status_code}: {error_text}"
                print(f"[Retry Request] ⚠️ Серверная ошибка (повторим): {last_error}")
                
                # Если не последняя попытка - ждём перед повтором
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2  # Экспоненциальная задержка
                    continue
                else:
                    # Последняя попытка тоже не удалась
                    raise RuntimeError(f"Серверная ошибка после {max_retries} попыток: {last_error}")
            
            # Другие статусы
            last_status = resp.status_code
            last_error = f"Unexpected status {resp.status_code}: {resp.text[:200]}"
            print(f"[Retry Request] ⚠️ Неожиданный статус: {last_error}")
            
            # Если не последняя попытка - повторяем
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            
        except httpx.TimeoutException as e:
            last_error = f"Timeout после {timeout_value} секунд"
            print(f"[Retry Request] ⚠️ Таймаут запроса: {last_error}")
            
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            else:
                raise RuntimeError(f"Таймаут запроса после {max_retries} попыток: {last_error}") from e
        
        except httpx.NetworkError as e:
            last_error = f"Network error: {str(e)}"
            print(f"[Retry Request] ⚠️ Сетевая ошибка: {last_error}")
            
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            else:
                raise RuntimeError(f"Сетевая ошибка после {max_retries} попыток: {last_error}") from e
        
        except RuntimeError:
            # Пробрасываем RuntimeError (уже обработанные ошибки)
            raise
        
        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}: {str(e)}"
            print(f"[Retry Request] ⚠️ Неожиданная ошибка: {last_error}")
            
            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            else:
                raise RuntimeError(f"Ошибка после {max_retries} попыток: {last_error}") from e
    
    # Если дошли сюда - все попытки исчерпаны
    final_error = last_error or f"Запрос не удался после {max_retries} попыток"
    if last_status:
        final_error += f" (последний статус: {last_status})"
    
    print(f"[Retry Request] ❌ Все попытки исчерпаны: {final_error}")
    raise RuntimeError(final_error)


async def chat_completion(
    model: str,
    messages: list,
    **kwargs
) -> dict:
    """
    Вызывает Chat API для генерации текста
    
    Args:
        model: Модель для генерации
        messages: Список сообщений в формате OpenAI
        **kwargs: Дополнительные параметры (temperature, etc.)
    
    Returns:
        JSON ответ от API
    """
    url = f"{BASE}/v1/chat/completions"
    
    payload = {
        "model": model,
        "messages": messages,
        **kwargs
    }
    
    has_image = any(
        isinstance(msg.get("content"), list) and 
        any(item.get("type") == "image_url" for item in msg.get("content", []) if isinstance(item, dict))
        for msg in messages
    )
    
    print(f"[Chat API] Отправляем запрос к модели: {model}")
    print(f"[Chat API] Количество сообщений: {len(messages)}")
    print(f"[Chat API] Включено изображение: {has_image}")
    
    resp = await _retry_request("POST", url, headers=HEADERS, json=payload)
    
    if resp.status_code != 200:
        error_msg = f"Chat API error {resp.status_code}: {resp.text[:400]}"
        print(f"[Chat API] ❌ {error_msg}")
        raise RuntimeError(error_msg)
    
    return resp.json()


async def chat_complete(
    system_prompt: str, 
    user_prompt: str, 
    temperature: float = 0.4,
    image_bytes: Optional[bytes] = None
) -> str:
    """
    Генерирует текст через NeuroAPI chat completion
    Поддерживает vision API для анализа изображений
    
    Args:
        system_prompt: Системный промпт
        user_prompt: Пользовательский промпт  
        temperature: Температура для генерации (0.0-1.0)
        image_bytes: Байты изображения для vision анализа (опционально)
    
    Returns:
        Сгенерированный текст
    """
    if DRYRUN:
        # Мини JSON по умолчанию для тестирования
        return json.dumps({
            "slides": [
                {"idx": 1, "role": "cover", "headline": "Обложка (stub)"},
                {"idx": 2, "role": "content", "headline": "Пункт 1", "bullets": ["Идея", "Шаги"]},
                {"idx": 3, "role": "content", "headline": "Пункт 2", "bullets": ["Идея", "Шаги"]}
            ],
            "style": {"tone": "простой", "target": "IG", "cta": "Листай"}
        }, ensure_ascii=False)
    
    # Формируем сообщения
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Если есть изображение - добавляем его в формате vision API
    if image_bytes:
        import base64
        
        # Конвертируем изображение в base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Определяем MIME тип изображения
        from PIL import Image
        import io
        try:
            img = Image.open(io.BytesIO(image_bytes))
            mime_type = f"image/{img.format.lower()}" if img.format else "image/png"
        except Exception:
            mime_type = "image/png"  # Fallback
        
        # Формируем сообщение с изображением в формате OpenAI vision
        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_base64}"
                    }
                }
            ]
        }
        messages.append(user_message)
        
        print(f"[Vision API] Отправляем изображение для анализа:")
        print(f"  Размер изображения: {len(image_bytes)} байт")
        print(f"  Base64 размер: {len(image_base64)} символов")
        print(f"  MIME тип: {mime_type}")
    else:
        # Обычное текстовое сообщение
        messages.append({"role": "user", "content": user_prompt})
    
    try:
        data = await chat_completion(
            model=TEXT_MODEL,
            messages=messages,
            temperature=temperature
        )
        
        # Логируем полный ответ от API
        print("API response:", json.dumps(data, indent=2, ensure_ascii=False))
        
        # Проверяем, что 'choices' есть в ответе
        if 'choices' not in data:
            error_msg = f"API response does not contain 'choices'. Response keys: {list(data.keys())}"
            print(f"Error: {error_msg}")
            print(f"Full response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            raise ValueError(error_msg)
        
        # Проверяем, что массив choices не пуст
        if not data["choices"] or len(data["choices"]) == 0:
            error_msg = "API response contains empty 'choices' array"
            print(f"Error: {error_msg}")
            raise ValueError(error_msg)
        
        # Проверяем наличие message и content
        choice = data["choices"][0]
        if "message" not in choice:
            error_msg = f"Choice does not contain 'message'. Choice keys: {list(choice.keys())}"
            print(f"Error: {error_msg}")
            raise ValueError(error_msg)
        
        if "content" not in choice["message"]:
            error_msg = f"Message does not contain 'content'. Message keys: {list(choice['message'].keys())}"
            print(f"Error: {error_msg}")
            raise ValueError(error_msg)
        
        # Возвращаем нужный контент
        return choice["message"]["content"]
    
    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response: {str(e)}"
        print(f"Error: {error_msg}")
        raise RuntimeError(error_msg) from e
    
    except Exception as e:
        # Логируем ошибку и выводим информацию о проблемах
        error_msg = f"Error occurred in chat_complete: {str(e)}"
        print(f"Error: {error_msg}")
        print(f"Error type: {type(e).__name__}")
        
        # Если это httpx ошибка, логируем дополнительную информацию
        if hasattr(e, 'request'):
            print(f"Request URL: {getattr(e.request, 'url', 'unknown')}")
            print(f"Request method: {getattr(e.request, 'method', 'unknown')}")
        
        raise RuntimeError(error_msg) from e


async def image_generation(
    model: str,
    prompt: str,
    size: str = "1024x1024",
    **kwargs
) -> dict:
    """
    Вызывает Image API для генерации изображений
    
    Args:
        model: Модель для генерации изображений
        prompt: Промпт для генерации
        size: Размер изображения (например "1024x1024")
        **kwargs: Дополнительные параметры (n, etc.)
    
    Returns:
        JSON ответ от API
    """
    url = f"{BASE}/v1/images/generations"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        **kwargs
    }
    
    # Для некоторых моделей может понадобиться n=1 явно
    if model == "gpt-image-1" and "n" not in payload:
        payload["n"] = 1
    
    print(f"[Image API] Включено изображение: True | model={model} | size={size}")
    print(f"[Image API] Промпт (первые 100 символов): {prompt[:100]}...")
    
    resp = await _retry_request("POST", url, headers=HEADERS, json=payload)
    
    if resp.status_code != 200:
        error_msg = f"Image API error {resp.status_code}: {resp.text[:400]}"
        print(f"[Image API] ❌ {error_msg}")
        
        # Обработка ошибки размера - пробуем fallback на 1024x1024
        if resp.status_code == 500:
            try:
                error_data = resp.json()
                if error_data.get("error", {}).get("param") == "size" and size != "1024x1024":
                    print(f"[Image API] ⚠️ Ошибка размера {size}, пробуем fallback на 1024x1024")
                    # Повторяем запрос с размером 1024x1024
                    payload["size"] = "1024x1024"
                    resp = await _retry_request("POST", url, headers=HEADERS, json=payload)
                    if resp.status_code == 200:
                        print(f"[Image API] ✅ Успешно с размером 1024x1024")
                    else:
                        # Если и это не помогло - пробрасываем ошибку
                        error_msg = f"Image API error {resp.status_code} even with 1024x1024: {resp.text[:400]}"
            except Exception:
                pass  # Если не удалось распарсить - пробрасываем исходную ошибку
        
        if resp.status_code != 200:
            # Детальная обработка частых ошибок
            if resp.status_code == 401:
                raise RuntimeError("Неверный API ключ. Проверьте NEUROAPI_API_KEY в .env файле. Используйте формат 'sk-or-v1-...'")
            elif resp.status_code == 403:
                raise RuntimeError("Доступ запрещён. Проверьте права доступа API ключа")
            elif resp.status_code == 404:
                raise RuntimeError(f"Эндпоинт не найден (404). Проверьте NEUROAPI_BASE_URL в .env файле")
            elif resp.status_code == 422:
                raise RuntimeError(f"Неверные параметры запроса (422): {resp.text[:400]}")
            else:
                raise RuntimeError(error_msg)
    
    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        error_msg = f"Не удалось распарсить JSON ответ: {str(e)}"
        print(f"[Image API] ❌ {error_msg}")
        print(f"[Image API] Ответ сервера: {resp.text[:500]}")
        raise RuntimeError(error_msg) from e
    
    return data


async def image_generate(prompt: str, size: str = "1024x1024") -> bytes:
    """
    Генерирует изображение через NeuroAPI с валидацией и улучшенной обработкой ошибок
    
    Args:
        prompt: Промпт для генерации изображения
        size: Размер изображения (например "1024x1024")
    
    Returns:
        Байты PNG изображения
    
    Raises:
        RuntimeError: Если генерация не удалась
        ValueError: Если промпт невалиден
    """
    # Проверка режима DRYRUN
    if DRYRUN:
        print(f"[Image Generator] 🔧 DRYRUN режим: создаём заглушку")
        from PIL import Image, ImageDraw
        import io
        
        im = Image.new("RGB", (1024, 1024), (28, 28, 28))
        d = ImageDraw.Draw(im)
        d.text((40, 40), "STUB IMAGE", fill=(230, 230, 230))
        
        buff = io.BytesIO()
        im.save(buff, format="PNG")
        return buff.getvalue()
    
    # Валидация промпта
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Промпт должен быть непустой строкой")
    
    prompt = prompt.strip()
    if len(prompt) == 0:
        raise ValueError("Промпт не может быть пустым")
    
    # Проверка длины промпта (лимиты могут отличаться, но обычно 1000+ символов)
    MAX_PROMPT_LENGTH = 2000
    if len(prompt) > MAX_PROMPT_LENGTH:
        print(f"[Image Generator] ⚠️ Промпт слишком длинный ({len(prompt)} символов), обрезаем до {MAX_PROMPT_LENGTH}")
        prompt = prompt[:MAX_PROMPT_LENGTH].rsplit(' ', 1)[0]  # Обрезаем по последнему слову
    
    # Валидация размера
    valid_sizes = ["256x256", "512x512", "1024x1024", "1024x1792", "1792x1024"]
    if size not in valid_sizes:
        print(f"[Image Generator] ⚠️ Размер {size} не в списке допустимых, используем 1024x1024")
        size = "1024x1024"
    
    # Проверка API ключа
    if not KEY:
        raise RuntimeError("NEUROAPI_API_KEY не установлен. Проверьте .env файл")
    
    # Проверка модели
    if not IMAGE_MODEL:
        raise RuntimeError("NEUROAPI_IMAGE_MODEL не установлена. Проверьте .env файл")
    
    # Для gpt-image-1 принудительно используем 1024x1024 (размер 1024x1792 не поддерживается)
    if IMAGE_MODEL == "gpt-image-1" and size != "1024x1024":
        print(f"[Image Generator] ⚠️ Для gpt-image-1 используем размер 1024x1024 (запрошен: {size})")
        size = "1024x1024"
    
    try:
        # Используем новую функцию image_generation
        data = await image_generation(
            model=IMAGE_MODEL,
            prompt=prompt,
            size=size
        )
        
        # Логируем структуру ответа для отладки
        print(f"[Image Generator] Структура ответа: {list(data.keys())}")
        
        # Проверяем наличие поля "data"
        if "data" not in data:
            error_msg = f"Ответ API не содержит поле 'data'. Доступные ключи: {list(data.keys())}"
            print(f"[Image Generator] ❌ ОШИБКА: {error_msg}")
            print(f"[Image Generator] Полный ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # Проверяем наличие ошибки в ответе
            if "error" in data:
                api_error = data["error"]
                error_msg = f"API вернул ошибку: {api_error.get('message', 'Unknown error')} (type: {api_error.get('type', 'unknown')})"
                print(f"[Image Generator] ❌ ОШИБКА API: {error_msg}")
            
            raise RuntimeError(error_msg)
        
        # Проверяем, что массив data не пустой
        if not data["data"] or len(data["data"]) == 0:
            error_msg = "Ответ API содержит пустой массив 'data'"
            print(f"[Image Generator] ❌ ОШИБКА: {error_msg}")
            print(f"[Image Generator] Полный ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
            raise RuntimeError(error_msg)
        
        # Пробуем разные варианты структуры ответа
        item = None
        
        # Вариант 1: OpenAI-совместимый формат {"data": [{"b64_json": "..."}]}
        if "data" in data:
            data_list = data.get("data") or []
            if data_list and len(data_list) > 0:
                item = data_list[0]
                print(f"[Image Generator] Found item in data array, keys: {list(item.keys())}")
        
        # Вариант 2: Прямой формат {"b64_json": "..."} или {"url": "..."}
        if item is None:
            if "b64_json" in data or "url" in data:
                item = data
                print(f"[Image Generator] Found direct format, keys: {list(item.keys())}")
        
        # Если ничего не нашли
        if item is None:
            error_msg = f"Unexpected image response format. Response keys: {list(data.keys())}"
            print(f"[Image Generator] ❌ {error_msg}")
            print(f"[Image Generator] Full response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            raise RuntimeError(error_msg)
        
        # Base64 вариант
        if "b64_json" in item:
            import base64
            b64_str = item["b64_json"]
            print(f"[Image Generator] Decoding base64 (len={len(b64_str)} chars)")
            try:
                image_bytes = base64.b64decode(b64_str)
                print(f"[Image Generator] ✅ Image decoded (base64): {len(image_bytes)} bytes")
                return image_bytes
            except Exception as e:
                print(f"[Image Generator] ❌ Base64 decode failed: {e}")
                raise RuntimeError(f"Failed to decode base64 image: {e}") from e
        
        # URL вариант - скачиваем изображение
        if "url" in item:
            image_url = item["url"]
            print(f"[Image Generator] Downloading image from URL: {image_url}")
            try:
                async with httpx.AsyncClient(timeout=60.0) as cli:
                    img_resp = await cli.get(image_url)
                    if img_resp.status_code == 200:
                        image_bytes = img_resp.content
                        print(f"[Image Generator] ✅ Image downloaded (URL): {len(image_bytes)} bytes")
                        return image_bytes
                    else:
                        raise RuntimeError(f"Failed to download image from URL: status {img_resp.status_code}")
            except Exception as e:
                print(f"[Image Generator] ❌ URL download failed: {e}")
                raise RuntimeError(f"Failed to download image from URL: {e}") from e
        
        # Если структура неожиданная - выводим её для отладки
        error_msg = f"Unexpected image response format. Item keys: {list(item.keys())}"
        print(f"[Image Generator] ❌ {error_msg}")
        print(f"[Image Generator] Full response: {json.dumps(data, indent=2, ensure_ascii=False)}")
        raise RuntimeError(error_msg)
        
    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"Error generating image: {type(e).__name__}: {str(e)}"
        print(f"[Image Generator] ❌ ОШИБКА: {error_msg}")
        import traceback
        print(f"[Image Generator] Traceback: {traceback.format_exc()}")
        raise RuntimeError(error_msg) from e
