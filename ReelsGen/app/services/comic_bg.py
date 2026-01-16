"""
Comic background generation service - генерация комикс-фонов по промту
"""
from __future__ import annotations

import os
import io
import glob
import logging
import hashlib
import asyncio
from typing import List, Optional

from PIL import Image

from .utils_io import cover_fit, CANVAS_SIZE, slugify
from .image_provider import generate_image_bytes

logger = logging.getLogger(__name__)

# Единый стиль промта под комикс
COMIC_STYLE = (
    "в стиле комикса, иллюстрация, clean lineart, flat shading, expressive faces, "
    "soft lighting, no text, no captions, no logos, no watermark, instagram vertical"
)


def build_prompt(user_prompt: str) -> str:
    """
    Строит финальный промпт для генерации комикс-фона
    
    Args:
        user_prompt: Пользовательский промпт
        
    Returns:
        Финальный промпт со стилем
    """
    user_prompt = (user_prompt or "").strip()
    if not user_prompt:
        return COMIC_STYLE
    
    prompt_full = f"{user_prompt}. {COMIC_STYLE}".strip(". ")
    
    # Логируем промпт
    print(f"[comic_bg] prompt={prompt_full[:200]}...")
    
    return prompt_full


def build_image_prompt_from_slide_text(headline: str, bullets: List[str] = None) -> str:
    """
    Создает промпт для генерации изображения на основе текста слайда
    Вариант A: прямая подстановка текста слайда + COMIC_STYLE
    
    Args:
        headline: Заголовок слайда
        bullets: Список пунктов (опционально)
        
    Returns:
        Промпт для генерации изображения
    """
    headline = (headline or "").strip()
    
    # Собираем текст слайда
    slide_text = headline
    if bullets:
        bullets_text = ", ".join([b.strip() for b in bullets if b.strip()])
        if bullets_text:
            slide_text = f"{slide_text}. {bullets_text}"
    
    # Добавляем стиль комикса
    prompt = f"{slide_text}. {COMIC_STYLE}".strip(". ")
    
    print(f"[comic_bg] slide prompt: {prompt[:200]}...")
    
    return prompt


def get_slide_text_hash(headline: str, bullets: List[str] = None) -> str:
    """
    Создает хеш для текста слайда (для кеширования)
    
    Args:
        headline: Заголовок слайда
        bullets: Список пунктов
        
    Returns:
        MD5 хеш строки
    """
    text = headline or ""
    if bullets:
        text += "|" + "|".join([b.strip() for b in bullets if b.strip()])
    
    return hashlib.md5(text.encode('utf-8')).hexdigest()


async def generate_comic_background(prompt: str, size: tuple = (1080, 1350)) -> Optional[Image.Image]:
    """
    Генерирует одну картинку в стиле комиксов по промту
    
    Args:
        prompt: Пользовательский промпт
        size: Размер изображения (width, height)
        
    Returns:
        PIL.Image (RGBA) или None при ошибке
    """
    width, height = size
    prompt_full = build_prompt(prompt)
    
    try:
        raw_bytes = await generate_image_bytes(
            prompt_full,
            width=width,
            height=height
        )
        
        if not raw_bytes or len(raw_bytes) == 0:
            print(f"[comic_bg] ❌ Empty bytes received")
            return None
        
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        img = cover_fit(img, CANVAS_SIZE)
        
        print(f"[comic_bg] ✅ Generated background ({img.size[0]}x{img.size[1]}) mode={img.mode}")
        return img
        
    except Exception as e:
        print(f"[comic_bg] ❌ Image generation failed: {type(e).__name__}: {e}")
        import traceback
        print(f"[comic_bg] Traceback: {traceback.format_exc()}")
        return None


async def generate_comic_backgrounds(prompt: str, n: int = 4) -> List[Image.Image]:
    """
    Генерирует n картинок в стиле комиксов по промту
    
    Args:
        prompt: Пользовательский промпт
        n: Количество изображений для генерации
        
    Returns:
        Список PIL.Image (RGBA 1080x1350)
        При ошибке — пустой список (fallback должен быть в вызывающем коде)
    """
    results: List[Image.Image] = []
    
    print(f"[comic_bg] Generating {n} comic backgrounds for prompt: '{prompt[:80]}...'")
    
    for idx in range(max(1, n)):
        img = await generate_comic_background(prompt, size=(1080, 1350))
        if img:
            results.append(img)
    
    print(f"[comic_bg] Generated {len(results)}/{n} backgrounds successfully")
    
    if len(results) == 0:
        print(f"[comic_bg] ⚠️ WARNING: No backgrounds generated, caller should use fallback")
    
    return results


def cache_dir_for_prompt(base_dir: str, prompt: str) -> str:
    """
    Получает путь к директории кеша для промта
    
    Args:
        base_dir: Базовая директория кеша
        prompt: Промпт
        
    Returns:
        Путь к директории кеша
    """
    d = os.path.join(base_dir, slugify(prompt))
    os.makedirs(d, exist_ok=True)
    return d


def load_cached_images(base_dir: str, prompt: str, limit: int) -> List[Image.Image]:
    """
    Загружает изображения из кеша
    
    Args:
        base_dir: Базовая директория кеша
        prompt: Промпт
        limit: Максимальное количество изображений
        
    Returns:
        Список PIL.Image
    """
    d = cache_dir_for_prompt(base_dir, prompt)
    paths = sorted(glob.glob(os.path.join(d, "*.*")))
    # Фильтруем только изображения
    image_paths = [p for p in paths if p.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    imgs = []
    for p in image_paths[:limit]:
        try:
            img = Image.open(p).convert("RGBA")
            img = cover_fit(img, CANVAS_SIZE)  # Применяем cover_fit
            imgs.append(img)
        except Exception:
            pass
    
    return imgs


def save_images_to_cache(base_dir: str, prompt: str, imgs: List[Image.Image]) -> None:
    """
    Сохраняет изображения в кеш
    
    Args:
        base_dir: Базовая директория кеша
        prompt: Промпт
        imgs: Список изображений для сохранения
    """
    d = cache_dir_for_prompt(base_dir, prompt)
    
    for i, im in enumerate(imgs, start=1):
        # Находим свободный номер
        existing = glob.glob(os.path.join(d, "bg_*.png"))
        max_num = 0
        for ex in existing:
            try:
                num = int(os.path.basename(ex).replace("bg_", "").replace(".png", ""))
                max_num = max(max_num, num)
            except:
                pass
        
        filename = f"bg_{max_num + i:02d}.png"
        im.save(os.path.join(d, filename), "PNG")


def cache_dir_for_slide_text(base_dir: str, title: str, slide_text_hash: str) -> str:
    """
    Получает путь к директории кеша для текста слайда
    Структура: base_dir/slide_cache/{title_slug}/{slide_text_hash}/
    
    Args:
        base_dir: Базовая директория кеша
        title: Название карусели (для группировки)
        slide_text_hash: Хеш текста слайда
        
    Returns:
        Путь к директории кеша
    """
    # Создаем папку под каждый круг генерации (по title)
    title_slug = slugify(title)[:50]  # Ограничиваем длину
    cache_root = os.path.join(base_dir, "slide_cache", title_slug)
    d = os.path.join(cache_root, slide_text_hash)
    os.makedirs(d, exist_ok=True)
    return d


def load_cached_slide_background(base_dir: str, title: str, headline: str, bullets: List[str] = None) -> Optional[Image.Image]:
    """
    Загружает кешированное изображение фона для слайда
    
    Args:
        base_dir: Базовая директория кеша
        title: Название карусели
        headline: Заголовок слайда
        bullets: Список пунктов
        
    Returns:
        PIL.Image или None если нет в кеше
    """
    slide_hash = get_slide_text_hash(headline, bullets)
    cache_dir = cache_dir_for_slide_text(base_dir, title, slide_hash)
    
    # Ищем первое изображение в папке
    image_paths = glob.glob(os.path.join(cache_dir, "*.png"))
    image_paths.extend(glob.glob(os.path.join(cache_dir, "*.jpg")))
    image_paths.extend(glob.glob(os.path.join(cache_dir, "*.jpeg")))
    
    if image_paths:
        try:
            img = Image.open(image_paths[0]).convert("RGBA")
            img = cover_fit(img, CANVAS_SIZE)
            print(f"[comic_bg] ✅ Loaded cached background for slide: {headline[:50]}...")
            return img
        except Exception as e:
            print(f"[comic_bg] ⚠️ Failed to load cached image: {e}")
    
    return None


def save_slide_background_to_cache(base_dir: str, title: str, headline: str, bullets: List[str] = None, img: Image.Image = None) -> None:
    """
    Сохраняет изображение фона слайда в кеш
    
    Args:
        base_dir: Базовая директория кеша
        title: Название карусели
        headline: Заголовок слайда
        bullets: Список пунктов
        img: Изображение для сохранения
    """
    if img is None:
        return
    
    slide_hash = get_slide_text_hash(headline, bullets)
    cache_dir = cache_dir_for_slide_text(base_dir, title, slide_hash)
    
    # Сохраняем как bg.png (один файл на слайд)
    cache_path = os.path.join(cache_dir, "bg.png")
    try:
        img.save(cache_path, "PNG")
        print(f"[comic_bg] 💾 Saved to cache: {cache_path}")
    except Exception as e:
        print(f"[comic_bg] ⚠️ Failed to save to cache: {e}")


async def generate_slide_background(
    headline: str,
    bullets: List[str] = None,
    cache_dir: Optional[str] = None,
    title: Optional[str] = None,
    use_cache: bool = True
) -> Optional[Image.Image]:
    """
    Генерирует фон для одного слайда на основе его текста
    
    Args:
        headline: Заголовок слайда
        bullets: Список пунктов
        cache_dir: Директория кеша (опционально)
        title: Название карусели (для кеша)
        use_cache: Использовать кеш (по умолчанию True)
        
    Returns:
        PIL.Image или None при ошибке
    """
    # Проверяем кеш
    if use_cache and cache_dir and title:
        cached = load_cached_slide_background(cache_dir, title, headline, bullets)
        if cached:
            return cached
    
    # Создаем промпт
    prompt = build_image_prompt_from_slide_text(headline, bullets)
    
    # Генерируем изображение
    img = await generate_comic_background(prompt)
    
    # Сохраняем в кеш
    if img and use_cache and cache_dir and title:
        save_slide_background_to_cache(cache_dir, title, headline, bullets, img)
    
    return img


async def generate_all_slide_backgrounds(
    slides: List[dict],
    cache_dir: Optional[str] = None,
    title: Optional[str] = None,
    use_cache: bool = True
) -> List[Optional[Image.Image]]:
    """
    Параллельно генерирует фоны для всех контент-слайдов
    
    Args:
        slides: Список слайдов (словари с headline, bullets)
        cache_dir: Директория кеша (опционально)
        title: Название карусели (для кеша)
        use_cache: Использовать кеш
        
    Returns:
        Список PIL.Image (по одному на каждый контент-слайд, None если ошибка)
    """
    # Фильтруем только контент-слайды (пропускаем обложку)
    # Обложка: role="cover" или type="cover" или idx=1
    content_slides = [
        s for s in slides 
        if s.get("role") != "cover" 
        and s.get("type") not in ("cover", None)
        and s.get("idx", 999) != 1  # Первый слайд всегда обложка
    ]
    
    if not content_slides:
        print(f"[comic_bg] No content slides to generate backgrounds for")
        return []
    
    print(f"[comic_bg] Generating {len(content_slides)} backgrounds in parallel...")
    
    # Создаем задачи для параллельного выполнения
    tasks = []
    for slide in content_slides:
        headline = slide.get("headline") or slide.get("title") or ""
        bullets = slide.get("bullets") or slide.get("points") or []
        
        task = generate_slide_background(
            headline=headline,
            bullets=bullets,
            cache_dir=cache_dir,
            title=title,
            use_cache=use_cache
        )
        tasks.append(task)
    
    # Выполняем параллельно
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Обрабатываем результаты
    backgrounds = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[comic_bg] ❌ Background generation failed for slide {i+1}: {type(result).__name__}: {result}")
            backgrounds.append(None)
        elif result is None:
            print(f"[comic_bg] ⚠️ Background generation returned None for slide {i+1}")
            backgrounds.append(None)
        else:
            backgrounds.append(result)
    
    success_count = sum(1 for bg in backgrounds if bg is not None)
    print(f"[comic_bg] ✅ Generated {success_count}/{len(content_slides)} backgrounds successfully")
    
    return backgrounds

