"""
Адаптер для генерации изображений в стиле референсного фото.
Поддерживает различные провайдеры AI (NeuroAPI, AITunnel, Replicate, ComfyUI, локальный).
"""

import os
import time
import base64
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.core.config import settings
from app.services.image_gen import generate_image, ProviderModelUnavailable, ProviderRequestFailed
from app.services.img_analysis import analyze_style, build_style_description
from app.services.style_analyzer import analyze_style_from_image, fallback_style
from app.services.neuro_client import get_neuro_client

# Процессный кэш (для одного запуска uvicorn)
_SHARED_BG_CACHE: dict[str, str] = {}

def _shared_bg_key(style_image_path: str, size: str, style_strength: float, prompt: str) -> str:
    """Формирует ключ кэша на основе параметров генерации."""
    return f"{Path(style_image_path).resolve()}|{size}|{round(style_strength or 0.75, 3)}|{hash(prompt)}"


class StyleTransferAdapter:
    """
    Унифицированный адаптер для генерации изображений с переносом стиля.
    
    Поддерживаемые провайдеры (по приоритету):
    1. AITunnel (уже интегрирован в image_gen.py)
    2. Replicate API
    3. ComfyUI API
    4. Stable Diffusion WebUI API
    """
    
    def __init__(self):
        self.provider = self._detect_provider()
    
    def _detect_provider(self) -> str:
        """Определяет доступный провайдер AI на основе переменных окружения."""
        # Проверяем NeuroAPI первым (приоритетный провайдер)
        if os.getenv("NEUROAPI_API_KEY"):
            return "neuroapi"
        
        # Проверяем AITunnel (уже есть в проекте)
        if settings.AITUNNEL_API_KEY:
            return "aitunnel"
        
        # Проверяем Replicate
        if os.getenv("REPLICATE_API_TOKEN"):
            return "replicate"
        
        # Проверяем ComfyUI
        if os.getenv("COMFYUI_API_URL"):
            return "comfyui"
        
        # Проверяем Stable Diffusion WebUI
        if os.getenv("SD_WEBUI_API_URL"):
            return "sd_webui"
        
        return "none"
    
    def generate_images_in_style(
        self,
        style_image_path: str,
        count: int,
        prompt_hint: Optional[str] = None,
        style_strength: float = 0.6,
        seed: Optional[int] = None,
        size: str = "1080x1350"
    ) -> List[Path]:
        """
        Генерирует N изображений в стиле референсного фото.
        
        Args:
            style_image_path: Путь к референсному изображению для переноса стиля
            count: Количество изображений для генерации
            prompt_hint: Подсказка для содержания (опционально)
            style_strength: Насколько сильно переносить стиль (0.0-1.0)
            seed: Seed для воспроизводимости (опционально)
            size: Размер генерируемых изображений
            
        Returns:
            Список путей к сгенерированным изображениям
            
        Raises:
            RuntimeError: Если провайдер не настроен или генерация не удалась
        """
        if not Path(style_image_path).exists():
            raise ValueError(f"Style reference image not found: {style_image_path}")
        
        # Подтверждаем, что все параметры валидны
        count = max(1, min(count, 20))  # Ограничение 1-20
        style_strength = max(0.0, min(1.0, style_strength))  # 0.0-1.0
        
# Убираем отладочные логи
        
        # Перенаправляем на конкретный провайдер
        if self.provider == "neuroapi":
            return self._generate_neuroapi(style_image_path, count, prompt_hint, style_strength, seed, size)
# AITunnel удален - только NeuroAPI
        elif self.provider == "replicate":
            return self._generate_replicate(style_image_path, count, prompt_hint, style_strength, seed, size)
        elif self.provider == "comfyui":
            return self._generate_comfyui(style_image_path, count, prompt_hint, style_strength, seed, size)
        elif self.provider == "sd_webui":
            return self._generate_sd_webui(style_image_path, count, prompt_hint, style_strength, seed, size)
        else:
            raise RuntimeError(
                "No AI provider configured. Please set one of:\n"
                "- NEUROAPI_API_KEY (recommended)\n"
                "- AITUNNEL_API_KEY\n"
                "- REPLICATE_API_TOKEN\n"
                "- COMFYUI_API_URL\n"
                "- SD_WEBUI_API_URL\n"
                "See README.md for setup instructions."
            )
    
    def _generate_neuroapi(
        self,
        style_image_path: str,
        count: int,
        prompt_hint: Optional[str],
        style_strength: float,
        seed: Optional[int],
        size: str
    ) -> List[Path]:
        """Генерация через NeuroAPI (одно изображение для переиспользования)."""
        output_paths = []
        
        try:
            # Генерируем один фон для всех слайдов
            generated_path = generate_single_bg_from_style(style_image_path)
            
            # Добавляем тот же путь для всех слайдов
            for i in range(count):
                output_paths.append(Path(generated_path))
        
        except Exception as e:
            # Прокидываем исключения провайдера как есть
            raise ProviderRequestFailed(f"NeuroAPI generation failed: {e}", status_code=None, retriable=True)
        
        return output_paths
    
# Старые методы для AITunnel удалены - теперь используется только NeuroAPI
    
    def _generate_replicate(self, style_image_path: str, count: int, prompt_hint: Optional[str], 
                           style_strength: float, seed: Optional[int], size: str) -> List[Path]:
        """Генерация через Replicate API (заглушка с инструкциями)."""
        raise NotImplementedError(
            "Replicate integration not yet implemented. To enable:\n"
            "1. Install: pip install replicate\n"
            "2. Set REPLICATE_API_TOKEN env var\n"
            "3. See https://replicate.com/docs for API details\n"
            "Example model: stability-ai/stable-diffusion-img2img"
        )
    
    def _generate_comfyui(self, style_image_path: str, count: int, prompt_hint: Optional[str],
                         style_strength: float, seed: Optional[int], size: str) -> List[Path]:
        """Генерация через ComfyUI API (заглушка с инструкциями)."""
        raise NotImplementedError(
            "ComfyUI integration not yet implemented. To enable:\n"
            "1. Set COMFYUI_API_URL env var (e.g., http://localhost:8188)\n"
            "2. Install ComfyUI with img2img workflow\n"
            "3. See https://github.com/comfyanonymous/ComfyUI for details"
        )
    
    def _generate_sd_webui(self, style_image_path: str, count: int, prompt_hint: Optional[str],
                          style_strength: float, seed: Optional[int], size: str) -> List[Path]:
        """Генерация через Stable Diffusion WebUI API (заглушка с инструкциями)."""
        raise NotImplementedError(
            "Stable Diffusion WebUI integration not yet implemented. To enable:\n"
            "1. Set SD_WEBUI_API_URL env var (e.g., http://localhost:7860)\n"
            "2. Enable API in WebUI settings\n"
            "3. See https://github.com/AUTOMATIC1111/stable-diffusion-webui-api for details"
        )
    
# Старый метод для AITunnel удален - используется _build_prompt_from_style


# Singleton instance
_style_adapter = None


def get_style_adapter() -> StyleTransferAdapter:
    """Возвращает singleton адаптер для переноса стиля."""
    global _style_adapter
    if _style_adapter is None:
        _style_adapter = StyleTransferAdapter()
    return _style_adapter


# Публичный интерфейс для использования из других модулей
def generate_images_in_style(
    style_image_path: str,
    count: int,
    prompt_hint: Optional[str] = None,
    style_strength: float = 0.6,
    seed: Optional[int] = None
) -> List[Path]:
    """
    Удобный интерфейс для генерации изображений в стиле.
    """
    adapter = get_style_adapter()
    return adapter.generate_images_in_style(
        style_image_path=style_image_path,
        count=count,
        prompt_hint=prompt_hint,
        style_strength=style_strength,
        seed=seed
    )


def _shared_bg_key(style_image_path: str) -> str:
    """Генерирует ключ кэша на основе хэша файла обложки."""
    import hashlib
    p = Path(style_image_path)
    try:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        return f"style:{digest}:1080x1350"
    except Exception:
        # Fallback для случая, когда файл недоступен
        return f"style:{p.name}:{int(p.stat().st_mtime)}:1080x1350"

def _extract_palette(path: str, k: int = 5):
    """Извлекает палитру цветов из изображения."""
    try:
        # Используем существующую функцию если есть
        from app.services.img_analysis import dominant_palette
        return dominant_palette(path, k=k)
    except Exception:
        # Простой fallback
        from PIL import Image
        img = Image.open(path).convert("RGB").resize((64, 64))
        colors = img.getcolors(64*64)
        if colors:
            colors = sorted(colors, key=lambda x: -x[0])
            return [c[1] for c in colors[:k]]
        return [(20,22,28), (35,37,45), (60,62,74)]

def _make_local_bg_from_palette(style_image_path: str, out_path: Path):
    """Создает локальный фон на основе палитры изображения."""
    from PIL import Image, ImageDraw, ImageFilter
    
    palette = _extract_palette(style_image_path, k=3)
    if not palette or len(palette) < 2:
        palette = [(20,22,28), (35,37,45), (60,62,74)]
    
    w, h = 1080, 1350
    base = Image.new("RGB", (w, h), palette[0])
    draw = ImageDraw.Draw(base)
    
    # Линейный градиент от первого к второму цвету палитры
    for i in range(h):
        t = i / max(1, h-1)
        r = int(palette[0][0] * (1-t) + palette[1][0] * t)
        g = int(palette[0][1] * (1-t) + palette[1][1] * t) 
        b = int(palette[0][2] * (1-t) + palette[1][2] * t)
        draw.line([(0, i), (w, i)], fill=(r, g, b))
    
    # Небольшое размытие для сглаживания
    base = base.filter(ImageFilter.GaussianBlur(radius=2))
    base.save(out_path, "PNG", optimize=True)

def _build_prompt_from_style(style: Dict[str, Any]) -> str:
    """Строит простой промпт на основе анализа стиля."""
    palette = ", ".join(style.get("palette", [])[:3])  # Только первые 3 цвета
    lighting = style.get("lighting", "dark")
    mood = style.get("mood", "minimalism")
    texture = style.get("texture", "gradient")
    
    return (
        f"Abstract background. Colors: {palette}. "
        f"{lighting} lighting, {mood} {texture}. "
        f"NO text, NO faces, NO objects. Pure gradient."
    )

def generate_single_bg_from_style(style_image_path: str) -> str:
    """Создает один фон в стиле изображения и кэширует его."""
    key = Path(style_image_path).stem
    cached = _SHARED_BG_CACHE.get(key)
    if cached and Path(cached).exists():
        print(f"[BG] reuse cached background: {cached}")
        return cached

    print("[BG] Generating single background via NeuroAPI...")
    out_path = Path("output/cache/style_from_photo/bg_shared.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Проверяем доступность NeuroAPI
    from app.services.neuro_client import neuroapi_enabled
    if not neuroapi_enabled():
        print("[BG] NeuroAPI not available, using fallback.")
        _make_local_bg_from_palette(style_image_path, str(out_path))
        _SHARED_BG_CACHE[key] = str(out_path)
        print(f"[BG] single background ready: {out_path} (source: fallback)")
        print("[BG] DEBUG: single background generation finished")
        return str(out_path)

    # Генерируем через NeuroAPI
    try:
        from app.services.image_gen import generate_image_via_neuroapi, fit_center_crop_to_1080x1350
        from app.services.img_analysis import dominant_palette
        
        # Извлекаем палитру для усиленного промпта
        hex_palette = []
        try:
            pals = dominant_palette(style_image_path, k=5)  # [(r,g,b),...]
            hex_palette = [f"#{r:02x}{g:02x}{b:02x}" for (r,g,b) in pals]
        except Exception:
            hex_palette = []

        palette_hint = (", ".join(hex_palette)) if hex_palette else "use same dark/contrast palette as reference"

        prompt = (
            "Create a background image ONLY (no objects, no text, no logos). "
            "Match EXACT style of the reference: lighting, texture, contrast. "
            f"Use EXACT color palette: {palette_hint}. "
            "Make it suitable for Instagram carousel inner slide background: subtle, clean, high-contrast for white text."
        )
        
        bg_tmp = generate_image_via_neuroapi(
            prompt=prompt,
            image_ref=style_image_path,
            size="1024x1536"
        )

        if bg_tmp and Path(bg_tmp).exists():
            # Обрезаем до нужного размера и сохраняем как bg_shared.png
            fit_center_crop_to_1080x1350(bg_tmp, str(out_path))
            _SHARED_BG_CACHE[key] = str(out_path)
            print(f"[BG] single background ready: {out_path} (source: neuro)")
            print("[BG] DEBUG: single background generation finished")
            return str(out_path)
        else:
            raise RuntimeError("NeuroAPI generation failed")
            
    except Exception as e:
        print(f"[BG] NeuroAPI generation failed: {e}, fallback to clean background.")
        _make_local_bg_from_palette(style_image_path, str(out_path))
        _SHARED_BG_CACHE[key] = str(out_path)
        print(f"[BG] single background ready: {out_path} (source: fallback)")
        print("[BG] DEBUG: single background generation finished")
        return str(out_path)

