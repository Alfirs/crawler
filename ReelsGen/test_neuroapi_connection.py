"""
Скрипт для проверки подключения к NeuroAPI и диагностики проблем
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host")
KEY = os.getenv("NEUROAPI_API_KEY", "")
IMAGE_MODEL = os.getenv("NEUROAPI_IMAGE_MODEL", "gpt-image-1")
TEXT_MODEL = os.getenv("NEUROAPI_TEXT_MODEL", "gpt-5-mini")

HEADERS = {"Authorization": f"Bearer {KEY}"}


async def test_api_connection():
    """Тестирует подключение к NeuroAPI"""
    
    print("=" * 60)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЯ К NEUROAPI")
    print("=" * 60)
    
    # Проверка 1: Наличие API ключа
    print("\n[1] Проверка API ключа...")
    if not KEY:
        print("   [FAIL] NEUROAPI_API_KEY не установлен в .env")
        return False
    print(f"   [OK] API ключ найден: {'*' * (len(KEY) - 8) + KEY[-8:]}")
    
    # Проверка 2: Проверка базового URL
    print(f"\n[2] Проверка базового URL...")
    print(f"   [INFO] BASE_URL: {BASE}")
    
    # Проверка 3: Проверка доступности API
    print(f"\n[3] Проверка доступности API...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as cli:
            resp = await cli.get(f"{BASE}/health", headers=HEADERS)
            print(f"   [INFO] Статус /health: {resp.status_code}")
    except Exception as e:
        print(f"   [WARN] /health недоступен: {e}")
    
    # Проверка 4: Получение списка моделей
    print(f"\n[4] Получение списка доступных моделей...")
    try:
        url = f"{BASE}/v1/models"
        async with httpx.AsyncClient(timeout=30.0) as cli:
            resp = await cli.get(url, headers=HEADERS)
            if resp.status_code == 200:
                models = resp.json()
                if "data" in models:
                    model_ids = [m.get("id", "") for m in models["data"]]
                    print(f"   [OK] Получено моделей: {len(model_ids)}")
                    
                    # Проверяем наличие нужных моделей
                    has_text_model = any(TEXT_MODEL in m for m in model_ids)
                    has_image_model = any(IMAGE_MODEL in m for m in model_ids)
                    
                    print(f"   [{'OK' if has_text_model else 'FAIL'}] Текстовая модель '{TEXT_MODEL}': {'найдена' if has_text_model else 'НЕ найдена'}")
                    print(f"   [{'OK' if has_image_model else 'FAIL'}] Модель изображений '{IMAGE_MODEL}': {'найдена' if has_image_model else 'НЕ найдена'}")
                    
                    if not has_text_model:
                        print(f"   [INFO] Доступные текстовые модели: {[m for m in model_ids if 'gpt' in m.lower() or 'text' in m.lower()][:5]}")
                    if not has_image_model:
                        print(f"   [INFO] Доступные модели изображений: {[m for m in model_ids if 'image' in m.lower() or 'dall' in m.lower()][:5]}")
                else:
                    print(f"   [WARN] Неожиданная структура ответа: {list(models.keys())}")
            else:
                print(f"   [FAIL] Статус код: {resp.status_code}")
                print(f"   [FAIL] Ответ: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"   [FAIL] Ошибка при получении моделей: {e}")
        return False
    
    # Проверка 5: Тест текстового запроса
    print(f"\n[5] Тест текстового запроса (chat completion)...")
    try:
        url = f"{BASE}/v1/chat/completions"
        payload = {
            "model": TEXT_MODEL,
            "messages": [{"role": "user", "content": "Hello, test message"}],
            "max_tokens": 10
        }
        async with httpx.AsyncClient(timeout=30.0) as cli:
            resp = await cli.post(url, headers=HEADERS, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                print(f"   [OK] Текстовый запрос успешен")
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    print(f"   [OK] Ответ: {content[:50]}...")
            else:
                print(f"   [FAIL] Статус код: {resp.status_code}")
                print(f"   [FAIL] Ответ: {resp.text[:300]}")
                return False
    except Exception as e:
        print(f"   [FAIL] Ошибка текстового запроса: {e}")
        return False
    
    # Проверка 6: Тест генерации изображения (короткий промпт)
    print(f"\n[6] Тест генерации изображения...")
    print(f"   [INFO] Модель: {IMAGE_MODEL}")
    print(f"   [INFO] Промпт: 'A simple test image'")
    try:
        url = f"{BASE}/v1/images/generations"
        payload = {
            "model": IMAGE_MODEL,
            "prompt": "A simple test image, yellow and orange colors",
            "size": "1024x1024"
        }
        if IMAGE_MODEL == "gpt-image-1":
            payload["n"] = 1
        
        async with httpx.AsyncClient(timeout=120.0) as cli:
            print(f"   [INFO] Отправляем запрос (таймаут 120 сек)...")
            resp = await cli.post(url, headers=HEADERS, json=payload)
            
            if resp.status_code == 200:
                data = resp.json()
                print(f"   [OK] Генерация изображения успешна")
                if "data" in data and len(data["data"]) > 0:
                    item = data["data"][0]
                    if "b64_json" in item:
                        print(f"   [OK] Изображение получено в base64")
                    elif "url" in item:
                        print(f"   [OK] Изображение по URL: {item['url']}")
                else:
                    print(f"   [WARN] Неожиданная структура ответа: {list(data.keys())}")
            else:
                print(f"   [FAIL] Статус код: {resp.status_code}")
                print(f"   [FAIL] Ответ: {resp.text[:500]}")
                return False
    except httpx.TimeoutException:
        print(f"   [FAIL] Таймаут запроса (120 секунд)")
        return False
    except Exception as e:
        print(f"   [FAIL] Ошибка генерации изображения: {e}")
        import traceback
        print(f"   [FAIL] Traceback: {traceback.format_exc()}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ УСПЕШНО")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_api_connection())
    exit(0 if success else 1)

