"""
Watermark service - добавление водяных знаков на изображения
"""
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
import io


def normalize_username(s: str) -> str:
    """
    Нормализует username для watermark
    
    Args:
        s: Исходная строка (может быть с @ или без)
    
    Returns:
        Нормализованный username с @ или пустая строка
    """
    s = (s or "").strip().replace(" ", "")
    return "" if not s else "@" + s.lstrip("@")


def apply_text_watermark(img: Image.Image, text: str, opacity: int = 153) -> Image.Image:
    """
    Добавляет текстовый водяной знак в правый нижний угол
    
    Args:
        img: Исходное изображение
        text: Текст водяного знака
        opacity: Прозрачность (0-255), 153 = ~60%
    
    Returns:
        Изображение с водяным знаком
    """
    if not text or not text.strip():
        return img
    
    # Создаём копию изображения
    watermarked = img.copy()
    
    # Создаём слой для водяного знака
    overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Подбираем размер шрифта (примерно 4% от ширины изображения)
    font_size = max(16, img.width // 25)
    
    try:
        # Пытаемся использовать системный шрифт
        font = ImageFont.truetype("arial.ttf", font_size)
    except (OSError, IOError):
        try:
            # Fallback на другие шрифты
            font = ImageFont.truetype("app/assets/fonts/Inter-Regular.ttf", font_size)
        except (OSError, IOError):
            # Дефолтный шрифт
            font = ImageFont.load_default()
    
    # Измеряем размер текста
    try:
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # Fallback для старых версий Pillow
        text_width, text_height = font.getsize(text)
    
    # Позиция в правом нижнем углу с отступами
    margin = 20
    x = img.width - text_width - margin
    y = img.height - text_height - margin
    
    # Рисуем тень для лучшей читаемости
    shadow_offset = 2
    draw.text((x + shadow_offset, y + shadow_offset), text, 
              font=font, fill=(0, 0, 0, opacity // 2))
    
    # Рисуем основной текст
    draw.text((x, y), text, font=font, fill=(255, 255, 255, opacity))
    
    # Накладываем водяной знак
    watermarked = Image.alpha_composite(watermarked.convert('RGBA'), overlay)
    
    return watermarked.convert('RGB')


def apply_png_watermark(img: Image.Image, png_bytes: bytes, opacity: int = 153) -> Image.Image:
    """
    Добавляет PNG водяной знак в правый нижний угол
    
    Args:
        img: Исходное изображение
        png_bytes: Байты PNG файла с альфа-каналом
        opacity: Прозрачность (0-255), 153 = ~60%
    
    Returns:
        Изображение с водяным знаком
    """
    try:
        # Загружаем PNG водяной знак
        watermark_img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
        
        # Масштабируем водяной знак до 25% ширины основного изображения
        target_width = img.width // 4
        ratio = target_width / watermark_img.width
        target_height = int(watermark_img.height * ratio)
        
        watermark_resized = watermark_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Применяем дополнительную прозрачность
        if opacity < 255:
            alpha = watermark_resized.split()[-1]  # Получаем альфа-канал
            alpha = alpha.point(lambda p: int(p * opacity / 255))  # Уменьшаем прозрачность
            watermark_resized.putalpha(alpha)
        
        # Создаём копию изображения
        watermarked = img.copy().convert('RGBA')
        
        # Позиция в правом нижнем углу с отступами
        margin = 20
        x = img.width - target_width - margin
        y = img.height - target_height - margin
        
        # Накладываем водяной знак
        watermarked.paste(watermark_resized, (x, y), watermark_resized)
        
        return watermarked.convert('RGB')
        
    except Exception as e:
        # Если не удалось применить PNG водяной знак - возвращаем оригинал
        print(f"Ошибка применения PNG водяного знака: {e}")
        return img


def add_watermark(img: Image.Image, text_watermark: Optional[str] = None, 
                  png_watermark: Optional[bytes] = None) -> Image.Image:
    """
    Добавляет водяной знак (приоритет у PNG над текстом)
    Защита от повторного наложения через проверку флага
    
    Args:
        img: Исходное изображение
        text_watermark: Текстовый водяной знак
        png_watermark: PNG водяной знак в байтах
    
    Returns:
        Изображение с водяным знаком
    """
    # Защита от повторного наложения
    if hasattr(img, '_wm_applied') and img._wm_applied:
        print(f"[watermark] ⚠️ Watermark уже применён, пропускаем")
        return img
    
    # Нормализуем текстовый watermark
    if text_watermark:
        text_watermark = normalize_username(text_watermark)
        if not text_watermark:
            text_watermark = None
    
    # Приоритет у PNG водяного знака
    result = img
    if png_watermark:
        result = apply_png_watermark(img, png_watermark)
        result._wm_applied = True
        print(f"[watermark] ✅ PNG watermark applied")
    elif text_watermark:
        result = apply_text_watermark(img, text_watermark)
        result._wm_applied = True
        print(f"[watermark] ✅ Text watermark applied: {text_watermark}")
    else:
        print(f"[watermark] No watermark to apply")
    
    return result

