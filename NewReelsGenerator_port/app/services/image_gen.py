import base64
import os
from pathlib import Path
from typing import Optional
import time
import requests

# Кэш детектированной модели
_SELECTED_MODEL_CACHE = None  # Кэш выбранной модели на процесс

# NeuroAPI configuration - убираем статические переменные, используем динамическое чтение


class ProviderModelUnavailable(Exception):
    """Модель провайдера недоступна."""
    def __init__(self, model: str, fallback: Optional[str] = None, message: str = ""):
        self.model = model
        self.fallback = fallback
        self.message = message
        super().__init__(f"Provider model unavailable: {model} (fallback: {fallback}). {message}")


class ProviderRequestFailed(Exception):
    """Запрос к провайдеру завершился ошибкой."""
    def __init__(self, message: str, status_code: int | None = None, retriable: bool = True):
        self.message = message
        self.status_code = status_code
        self.retriable = retriable
        super().__init__(f"Provider request failed: {message}")


def get_selected_model() -> str:
    """
    Возвращает выбранную модель из ENV без HTTP-пробинга.
    
    Кэширует результат в _SELECTED_MODEL_CACHE на сессию процесса.
    """
    global _SELECTED_MODEL_CACHE
    
    if _SELECTED_MODEL_CACHE:
        return _SELECTED_MODEL_CACHE
    
    # Проверяем NeuroAPI динамически
    from app.services.neuro_client import neuroapi_enabled
    if neuroapi_enabled():
        _SELECTED_MODEL_CACHE = "gpt-image-1"
        print(f"[NeuroAPI] Using model: {_SELECTED_MODEL_CACHE}")
        return _SELECTED_MODEL_CACHE
    
    # Fallback без ключа
    _SELECTED_MODEL_CACHE = "gpt-image-1"
    return _SELECTED_MODEL_CACHE


def generate_image_via_neuroapi(
    prompt: str, 
    image_ref: Optional[str] = None,
    size: str = "1024x1536"
) -> Optional[str]:
    """
    Генерирует изображение через NeuroAPI.
    
    Args:
        prompt: Текстовый промпт для генерации
        image_ref: Путь к референсному изображению (для style transfer)
        size: Размер изображения (по умолчанию 1024x1536, поддерживаемый gpt-image-1)
        
    Returns:
        Путь к сгенерированному PNG файлу или None при ошибке
    """
    import threading
    from app.services.neuro_client import neuroapi_enabled, neuroapi_request
    
    CACHE_SHARED_BG = "output/cache/style_from_photo/bg_shared.png"
    
    # Проверка на повторный вызов
    if getattr(generate_image_via_neuroapi, "_in_progress", False):
        print("[NeuroAPI] Second call ignored; reuse shared bg")
        return CACHE_SHARED_BG
    
    if not neuroapi_enabled():
        print("[NeuroAPI] Skipped: API key missing or disabled.")
        raise ProviderModelUnavailable("gpt-image-1", message="NEUROAPI_API_KEY is not set")
    
    # Устанавливаем флаг блокировки
    generate_image_via_neuroapi._in_progress = True
    lock = threading.Lock()
    
    payload = {
        "model": "gpt-image-1",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "quality": "low"  # Экономия
    }
    
    # Если есть референсное изображение, добавляем его как image_url
    if image_ref and Path(image_ref).exists():
        try:
            with open(image_ref, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            payload["image_url"] = f"data:image/jpeg;base64,{image_data}"
        except Exception as e:
            print(f"[NeuroAPI] Failed to encode reference image: {e}")
    
    try:
        with lock:
            # Защита от повторного вызова (оставляем для дополнительной безопасности)
            import traceback
            if hasattr(generate_image_via_neuroapi, "_called_once"):
                raise RuntimeError("⚠️ NeuroAPI double-call detected!\n" + "".join(traceback.format_stack()[-5:]))
            generate_image_via_neuroapi._called_once = True
            print("[NeuroAPI] DEBUG: image generation started")
            
            # Существующий код NeuroAPI
        response = neuroapi_request("images/generations", payload)
        data = response.json()
        
        print(f"[NeuroAPI] image: generated (size={size})")
        
        # Извлекаем изображение из ответа
        if "data" in data and len(data["data"]) > 0:
            image_obj = data["data"][0]
            
            # Создаем директорию для кэша
            cache_dir = Path("output/cache/style_from_photo")
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Генерируем имя файла
            timestamp = int(time.time())
            output_path = cache_dir / f"bg_{timestamp}.png"
            
            # Сохраняем изображение
            if "b64_json" in image_obj:
                # Base64 формат
                image_data = base64.b64decode(image_obj["b64_json"])
                with open(output_path, "wb") as f:
                    f.write(image_data)
            elif "url" in image_obj:
                # URL формат - скачиваем
                img_response = requests.get(image_obj["url"], timeout=30)
                img_response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(img_response.content)
            else:
                raise ProviderRequestFailed("No image data found in response")
            
            return str(output_path)
        else:
            raise ProviderRequestFailed("No data in response")
            
    except Exception as e:
        error_msg = str(e)
        print(f"[NeuroAPI] Generation failed: {error_msg}")
        
        if "NEUROAPI_API_KEY is not set" in error_msg:
            raise ProviderModelUnavailable("gpt-image-1", message=error_msg)
        elif "400" in error_msg or "500" in error_msg:
            # HTTP ошибки - возможно неподдерживаемый размер или другая проблема API
            raise ProviderRequestFailed(f"NeuroAPI HTTP error: {error_msg}", retriable=False)
        else:
            raise ProviderRequestFailed(f"NeuroAPI error: {error_msg}", retriable=True)
    
    finally:
        generate_image_via_neuroapi._in_progress = False
        print("[NeuroAPI] DEBUG: generation finished, lock released")


def fit_center_crop_to_1080x1350(input_path: str, output_path: str):
    """
    Ресайзит и кропит изображение до размера 1080x1350.
    Масштабирует по высоте, затем центрирует кроп по ширине.
    """
    from PIL import Image
    im = Image.open(input_path).convert("RGB")
    target_w, target_h = 1080, 1350
    # масштаб по высоте
    scale = target_h / im.height
    new_w = int(im.width * scale)
    im = im.resize((new_w, target_h), Image.LANCZOS)
    # центр-кроп по ширине
    left = max(0, (new_w - target_w) // 2)
    im = im.crop((left, 0, left + target_w, target_h))
    im.save(output_path, "PNG", optimize=True)


# Backward compatibility - алиас для старого кода
def generate_image(*args, **kwargs) -> Optional[str]:
    """
    DEPRECATED: Обратная совместимость - теперь должна использоваться generate_single_bg_from_style
    """
    print("[DEPRECATED] generate_image called - should use generate_single_bg_from_style instead")
    
    # Переадресуем на единую функцию генерации фона если есть style_image_path
    style_image_path = kwargs.get('style_image_path')
    if style_image_path:
        from app.services.image_style_adapter import generate_single_bg_from_style
        bg_path = generate_single_bg_from_style(style_image_path)
        return bg_path
    
    # Если нет style_image_path - используем прямой вызов (deprecated)
    prompt = kwargs.get('prompt') or kwargs.get('img_prompt', '')
    if not prompt:
        prompt = "фон для карусели без текста"
    
    try:
        return generate_image_via_neuroapi(prompt, image_ref=style_image_path)
    except Exception as e:
        print(f"[NeuroAPI] Generation failed: {e}")
        return None