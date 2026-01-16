"""
Image Analyzer Service - анализ изображений и генерация промптов для нейросети
"""
import os
import io
from typing import Dict, Optional
from PIL import Image
import httpx
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host")
API_KEY = os.getenv("NEUROAPI_API_KEY", "")
TEXT_MODEL = os.getenv("NEUROAPI_TEXT_MODEL", "gpt-5-mini")
IMAGE_MODEL = os.getenv("NEUROAPI_IMAGE_MODEL", "gpt-image-1")


async def analyze_image_basic(image: Image.Image) -> Dict[str, any]:
    """
    Базовый анализ изображения (размеры, формат, основные характеристики)
    
    Args:
        image: PIL Image объект
    
    Returns:
        Словарь с информацией об изображении
    """
    info = {
        "size": image.size,  # (width, height)
        "mode": image.mode,  # RGB, RGBA, L и т.д.
        "format": image.format,
        "width": image.width,
        "height": image.height,
        "aspect_ratio": round(image.width / image.height, 2) if image.height > 0 else 0,
    }
    
    # Базовый анализ цветов (доминирующие цвета)
    try:
        colors = image.getcolors(maxcolors=256*256*256)
        if colors:
            # Сортируем по частоте и берём топ-5
            colors_sorted = sorted(colors, key=lambda x: x[0], reverse=True)[:5]
            info["dominant_colors"] = [color[1] for color in colors_sorted]
    except Exception:
        pass
    
    return info


async def analyze_image_with_ai(image_bytes: bytes, description_hint: Optional[str] = None) -> str:
    """
    Анализ изображения с помощью AI для генерации подробного описания
    
    Args:
        image_bytes: Байты изображения
        description_hint: Дополнительная подсказка для анализа
    
    Returns:
        Подробное описание изображения от AI
    """
    if not API_KEY:
        return "Не удалось проанализировать изображение: API ключ не установлен"
    
    # Базовый анализ изображения для получения метаданных
    try:
        image = Image.open(io.BytesIO(image_bytes))
        basic_info = await analyze_image_basic(image)
        
        # Анализ цветовой палитры
        try:
            # Уменьшаем изображение для анализа цветов
            thumbnail = image.copy()
            thumbnail.thumbnail((100, 100))
            colors = thumbnail.getcolors(maxcolors=256)
            color_info = ""
            if colors:
                dominant = sorted(colors, key=lambda x: x[0], reverse=True)[:3]
                color_info = f"Основные цвета: {', '.join([str(c[1]) for c in dominant[:3]])}. "
        except Exception:
            color_info = ""
        
    except Exception as e:
        return f"Ошибка при обработке изображения: {str(e)}"
    
    # Формируем детальный промпт для анализа
    system_prompt = (
        "Ты — профессиональный искусствовед и эксперт по анализу изображений. "
        "Твоя задача — создать подробное, структурированное описание изображения. "
        "Опиши:\n"
        "1. Что конкретно изображено (объекты, персонажи, пейзажи, элементы)\n"
        "2. Композицию (расположение объектов, перспектива, фокус)\n"
        "3. Стиль и технику (реализм, абстракция, цифровой арт, живопись и т.д.)\n"
        "4. Цветовую палитру и освещение\n"
        "5. Атмосферу и настроение\n"
        "6. Детали и особенности\n\n"
        "Будь конкретным и детальным. Описание должно быть достаточно подробным для создания нового изображения на его основе."
    )
    
    user_prompt = (
        f"Проанализируй изображение со следующими техническими характеристиками:\n\n"
        f"Размеры: {basic_info['width']} × {basic_info['height']} пикселей\n"
        f"Формат: {basic_info.get('format', 'unknown')}\n"
        f"Соотношение сторон: {basic_info['aspect_ratio']}:1\n"
        f"{color_info}\n"
    )
    
    if description_hint:
        user_prompt += f"Дополнительная информация от пользователя: {description_hint}\n\n"
    
    user_prompt += (
        "Создай подробное описание этого изображения. "
        "Опиши все видимые элементы, стиль, композицию, цвета и атмосферу. "
        "Описание должно быть на русском языке и достаточно детальным для понимания содержания изображения."
    )
    
    # Вызываем API для анализа с передачей изображения в Vision API
    try:
        from .neuroapi import chat_complete
        
        print(f"[Image Analyzer] Начинаем анализ изображения через Vision API")
        print(f"[Image Analyzer] Размер изображения: {len(image_bytes)} байт")
        print(f"[Image Analyzer] Размеры: {basic_info['width']}x{basic_info['height']}")
        
        # Обновляем user_prompt для Vision API - AI должен анализировать само изображение
        vision_user_prompt = (
            "Проанализируй это изображение. "
            "Опиши подробно всё, что видишь на изображении:\n\n"
            "- Что конкретно изображено (объекты, персонажи, пейзажи, элементы)\n"
            "- Композицию (расположение объектов, перспектива, фокус)\n"
            "- Стиль и технику (реализм, абстракция, цифровой арт, живопись и т.д.)\n"
            "- Цветовую палитру и освещение\n"
            "- Атмосферу и настроение\n"
            "- Детали и особенности\n\n"
        )
        
        if description_hint:
            vision_user_prompt += f"Дополнительная информация от пользователя: {description_hint}\n\n"
        
        vision_user_prompt += (
            "Создай подробное описание этого изображения на русском языке. "
            "Описание должно быть достаточно детальным для создания нового изображения на его основе."
        )
        
        # Передаём изображение напрямую в Vision API
        analysis = await chat_complete(
            system_prompt=system_prompt, 
            user_prompt=vision_user_prompt, 
            temperature=0.3,
            image_bytes=image_bytes  # Передаём изображение для анализа
        )
        
        print(f"[Image Analyzer] Анализ завершён успешно")
        print(f"[Image Analyzer] Длина описания: {len(analysis)} символов")
        
        return analysis
    except Exception as e:
        error_msg = f"Ошибка при анализе через AI: {str(e)}"
        print(f"[Image Analyzer] ОШИБКА: {error_msg}")
        import traceback
        print(f"[Image Analyzer] Traceback: {traceback.format_exc()}")
        return error_msg


async def create_image_prompt(image_description: str, style: str, additional_details: Optional[str] = None) -> str:
    """
    Создаёт оптимизированный промпт для генерации изображения на основе анализа
    Специализируется на жёлто-черно-оранжевом стиле с нарисованными эффектами
    
    Args:
        image_description: Описание изображения (что изображено)
        style: Стиль изображения (если не указан, используется жёлто-черно-оранжевый стиль)
        additional_details: Дополнительные детали для промпта
    
    Returns:
        Сформированный промпт для нейросети
    """
    # Определяем базовый стиль по умолчанию
    default_style = (
        "Yellow-black-orange color palette with painted, comic book illustration style. "
        "Bright orange and yellow tones with bold shadows, minimal details, and graphic painted look. "
        "Contrasting shadows and vibrant colors. Stylized, graphic illustration."
    )
    
    # Если стиль не указан или стандартный, используем дефолтный
    use_default_style = not style or style in ("Полуреалистичный цифровой арт", "")
    final_style = default_style if use_default_style else style
    
    # Используем AI для создания оптимизированного промпта
    if API_KEY:
        try:
            from .neuroapi import chat_complete
            
            system_prompt = (
                "Ты — эксперт по созданию промптов для генерации изображений нейросетями. "
                "Твоя задача — преобразовать описание изображения в качественный, детальный промпт "
                "на английском языке для генерации изображения.\n\n"
                "ВАЖНО: Промпт должен создавать изображение в стиле:\n"
                "- Жёлто-черно-оранжевая цветовая палитра (yellow, black, orange)\n"
                "- Нарисованный стиль, как в комиксах или графических иллюстрациях (painted, comic book style)\n"
                "- Яркие оранжевые и жёлтые оттенки с контрастными тенями\n"
                "- Минимальные детали, графический вид\n"
                "- Чёткие линии и выразительные формы\n\n"
                "Промпт должен быть конкретным, включать все важные детали из описания, "
                "композицию, эмоции, действия персонажей, цвета и атмосферу. "
                "Формат: полное предложение на английском языке, 150-250 слов. "
                "Начни с описания сцены, затем укажи стиль и цвета."
            )
            
            user_prompt = (
                f"Создай промпт для генерации изображения на основе следующего описания:\n\n"
                f"ОПИСАНИЕ ИЗОБРАЖЕНИЯ:\n{image_description}\n\n"
            )
            
            if not use_default_style:
                user_prompt += f"Желаемый стиль: {style}\n\n"
            else:
                user_prompt += (
                    "СТИЛЬ: Жёлто-черно-оранжевая палитра с нарисованным эффектом комиксов. "
                    "Яркие цвета, контрастные тени, минимальные детали.\n\n"
                )
            
            if additional_details:
                user_prompt += f"ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ: {additional_details}\n\n"
            
            user_prompt += (
                "Создай детальный промпт на английском языке. "
                "Промпт должен описывать:\n"
                "1. Что происходит на изображении (сцена, персонажи, действия, эмоции)\n"
                "2. Композицию и расположение элементов\n"
                "3. Стиль (comic book illustration, painted, graphic)\n"
                "4. Цветовую палитру (yellow, orange, black с яркими оттенками)\n"
                "5. Эффекты (contrasting shadows, bold colors, minimal details, clear lines)\n\n"
                "Пример формата:\n"
                "\"Illustration of [описание сцены]. The scene should have a bright yellow and orange "
                "color palette with bold shadows and minimal details, reminiscent of a comic book "
                "illustration. The characters should have exaggerated expressions with clear lines and "
                "a graphic, painted look.\""
            )
            
            print(f"[Prompt Generator] Создаём оптимизированный промпт...")
            print(f"[Prompt Generator] Используем стиль по умолчанию: {use_default_style}")
            
            optimized_prompt = await chat_complete(system_prompt, user_prompt, temperature=0.5)
            prompt_result = optimized_prompt.strip()
            
            print(f"[Prompt Generator] Промпт создан, длина: {len(prompt_result)} символов")
            
            return prompt_result
            
        except Exception as e:
            print(f"[Prompt Generator] Не удалось оптимизировать промпт через AI, используем fallback: {e}")
            import traceback
            print(f"[Prompt Generator] Traceback: {traceback.format_exc()}")
            # Fallback на простой промпт
    
    # Простой вариант промпта (fallback) с учётом жёлто-черно-оранжевого стиля
    print(f"[Prompt Generator] Используем fallback промпт")
    
    prompt_parts = []
    
    # Описание сцены (из анализа)
    if image_description:
        # Извлекаем ключевые моменты из описания
        desc_short = image_description[:400] if len(image_description) > 400 else image_description
        # Преобразуем описание в английский стиль промпта
        scene_desc = desc_short.replace("\n", ". ").strip()
        if scene_desc:
            prompt_parts.append(f"Illustration of {scene_desc}")
    
    # Стиль
    if use_default_style:
        prompt_parts.append(final_style)
    else:
        prompt_parts.append(style)
        # Добавляем цветовую палитру, если не указана
        if "yellow" not in style.lower() and "orange" not in style.lower():
            prompt_parts.append("yellow, orange, and black color palette")
    
    # Дополнительные детали
    if additional_details:
        prompt_parts.append(additional_details)
    
    # Технические характеристики для нарисованного стиля
    style_enhancements = [
        "comic book illustration style",
        "painted graphic look",
        "bold contrasting shadows",
        "bright vibrant colors",
        "minimal details with clear lines",
        "stylized exaggerated expressions",
        "high contrast, graphic design"
    ]
    
    # Добавляем улучшения стиля
    for enhancement in style_enhancements:
        if enhancement not in " ".join(prompt_parts).lower():
            prompt_parts.append(enhancement)
    
    result = ". ".join(prompt_parts)
    
    print(f"[Prompt Generator] Fallback промпт создан, длина: {len(result)} символов")
    
    return result


async def generate_image_from_prompt(prompt: str, size: str = "1024x1024") -> bytes:
    """
    Генерирует изображение на основе промпта
    
    Args:
        prompt: Промпт для генерации
        size: Размер изображения (например "1024x1024")
    
    Returns:
        Байты сгенерированного изображения
    """
    # Парсим размер из строки (например "1024x1024" -> width=1024, height=1024)
    try:
        width, height = map(int, size.split("x"))
    except (ValueError, AttributeError):
        width, height = 1024, 1024
    
    from .image_provider import generate_image_bytes
    return await generate_image_bytes(prompt, width=width, height=height)


async def analyze_and_generate(image_bytes: bytes, style: str, additional_details: Optional[str] = None) -> Dict[str, any]:
    """
    Полный цикл: анализ изображения и генерация нового на его основе
    
    Args:
        image_bytes: Байты исходного изображения
        style: Желаемый стиль для новой картины
        additional_details: Дополнительные детали
    
    Returns:
        Словарь с результатами анализа и сгенерированным изображением
    """
    
    # Анализ изображения
    description = await analyze_image_with_ai(image_bytes)
    
    # Создание промпта
    prompt = await create_image_prompt(description, style, additional_details)
    
    # Генерация нового изображения
    try:
        generated_image_bytes = await generate_image_from_prompt(prompt, size="1024x1024")
        
        return {
            "original_description": description,
            "prompt": prompt,
            "generated_image_bytes": generated_image_bytes,
            "success": True
        }
    except Exception as e:
        return {
            "original_description": description,
            "prompt": prompt,
            "error": str(e),
            "success": False
        }


# Утилита для работы с локальными файлами
def load_image_from_path(image_path: str) -> Image.Image:
    """
    Загружает изображение с локального пути или URL
    
    Args:
        image_path: Путь к файлу или URL
    
    Returns:
        PIL Image объект
    """
    if image_path.startswith(('http://', 'https://')):
        # Загрузка с URL
        response = requests.get(image_path)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    else:
        # Загрузка с локального пути
        return Image.open(image_path)


async def analyze_image_from_bytes(image_bytes: bytes, style: str = "", details: Optional[str] = None) -> Dict[str, any]:
    """
    Анализирует изображение из байтов и создаёт промпт для генерации
    
    Args:
        image_bytes: Байты изображения
        style: Стиль для новой картины
        details: Дополнительные детали для промпта
    
    Returns:
        Результаты анализа и промпт
    """
    try:
        # Загружаем изображение из байтов
        image = Image.open(io.BytesIO(image_bytes))
        
        # Анализируем изображение
        description = await analyze_image_with_ai(image_bytes)
        
        # Создаём промпт с учетом деталей
        prompt = await create_image_prompt(description, style, details)
        
        # Получаем базовую информацию
        image_info = await analyze_image_basic(image)
        
        return {
            "image_info": image_info,
            "description": description,
            "prompt": prompt,
            "style": style,
            "success": True
        }
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }


async def analyze_image_file(image_path: str, style: str = "Полуреалистичный цифровой арт", details: Optional[str] = None) -> Dict[str, any]:
    """
    Анализирует изображение из файла и создаёт промпт для генерации
    
    Args:
        image_path: Путь к файлу или URL
        style: Стиль для новой картины
        details: Дополнительные детали для промпта
    
    Returns:
        Результаты анализа и промпт
    """
    
    # Загружаем изображение
    try:
        image = load_image_from_path(image_path)
        
        # Конвертируем в байты для анализа
        img_bytes = io.BytesIO()
        # Сохраняем в том же формате, что и оригинал, или PNG
        save_format = image.format if image.format in ['PNG', 'JPEG', 'WEBP'] else 'PNG'
        image.save(img_bytes, format=save_format)
        image_bytes = img_bytes.getvalue()
        
        # Используем общую функцию для анализа из байтов
        return await analyze_image_from_bytes(image_bytes, style, details)
        
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }
