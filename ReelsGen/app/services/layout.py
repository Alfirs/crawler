"""
Layout service - утилиты для работы с текстом и вёрсткой
"""
from typing import List, Tuple, Optional
from PIL import ImageFont, ImageDraw
import re


def smart_split(text: str) -> List[str]:
    """
    Умное разбиение текста по пробелам и дефисам, сохраняя дефисы как часть слов
    
    Args:
        text: Исходный текст
        
    Returns:
        Список токенов (слов, пробелов, дефисов)
    """
    chunks = []
    for token in re.split(r"(\s+)", text):
        if not token:
            continue
        chunks.append(token)
    return chunks


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: Optional[ImageDraw.ImageDraw] = None) -> List[str]:
    """
    Переносит текст по строкам с учётом максимальной ширины
    Улучшенная версия с поддержкой разбиения длинных слов для кириллицы
    
    Args:
        text: Исходный текст
        font: Шрифт для измерения
        max_width: Максимальная ширина в пикселях
        draw: ImageDraw для измерения (опционально, если None - используется font.getbbox)
    
    Returns:
        Список строк после переноса
    """
    parts = text.split()
    lines = []
    cur = []
    
    for w in parts:
        test = (" ".join(cur + [w])).strip()
        
        # Измеряем ширину текста
        try:
            if draw is not None:
                bbox = draw.textbbox((0, 0), test, font=font)
                w_px = bbox[2] - bbox[0]
            else:
                bbox = font.getbbox(test)
                w_px = bbox[2] - bbox[0]
        except AttributeError:
            # Fallback для старых версий Pillow
            if draw is not None:
                w_px = font.getsize(test)[0]
            else:
                w_px = font.getsize(test)[0]
        
        if w_px <= max_width:
            cur.append(w)
        else:
            if not cur:
                # Слово длиннее строки - принудительный перенос по символам с дефисом
                for i in range(len(w), 0, -1):
                    seg = w[:i] + "-"
                    try:
                        if draw is not None:
                            bbox = draw.textbbox((0, 0), seg, font=font)
                            seg_w = bbox[2] - bbox[0]
                        else:
                            bbox = font.getbbox(seg)
                            seg_w = bbox[2] - bbox[0]
                    except AttributeError:
                        seg_w = font.getsize(seg)[0]
                    
                    if seg_w <= max_width:
                        lines.append(seg.rstrip("-"))
                        rest = w[i:]
                        cur = [rest] if rest else []
                        break
                else:
                    # Не смогли разбить - добавляем как есть
                    lines.append(w)
                    cur = []
            else:
                lines.append(" ".join(cur))
                cur = [w]
    
    if cur:
        lines.append(" ".join(cur))
    
    return lines if lines else [text]


def measure_text_block(text: str, font: ImageFont.FreeTypeFont, max_width: int, line_spacing: float = 1.25) -> Tuple[int, List[str]]:
    """
    Измеряет высоту текстового блока с учётом переносов
    
    Args:
        text: Исходный текст
        font: Шрифт для измерения  
        max_width: Максимальная ширина
        line_spacing: Междустрочный интервал (множитель от размера шрифта)
    
    Returns:
        Кортеж (высота_блока, список_строк)
    """
    lines = wrap_text(text, font, max_width)
    
    if not lines:
        return 0, []
    
    # Получаем высоту одной строки
    try:
        bbox = font.getbbox("Ag")  # Используем буквы с выносными элементами
        line_height = bbox[3] - bbox[1]
    except AttributeError:
        # Fallback для старых версий Pillow
        line_height = font.getsize("Ag")[1]
    
    # Рассчитываем общую высоту с учётом межстрочных интервалов
    total_height = int(line_height * len(lines) * line_spacing)
    
    return total_height, lines


def fit_text_to_area(text: str, base_font_path: str, initial_size: int, max_width: int, max_height: int, min_size: int = 24) -> Tuple[ImageFont.FreeTypeFont, List[str]]:
    """
    Подбирает размер шрифта чтобы текст поместился в заданную область
    
    Args:
        text: Исходный текст
        base_font_path: Путь к файлу шрифта
        initial_size: Начальный размер шрифта
        max_width: Максимальная ширина области
        max_height: Максимальная высота области
        min_size: Минимальный размер шрифта
    
    Returns:
        Кортеж (подобранный_шрифт, список_строк)
    """
    current_size = initial_size
    
    while current_size >= min_size:
        try:
            font = ImageFont.truetype(base_font_path, current_size)
            height, lines = measure_text_block(text, font, max_width)
            
            # Если текст помещается - возвращаем результат
            if height <= max_height:
                return font, lines
            
        except (OSError, IOError):
            # Если не удалось загрузить шрифт - используем дефолтный
            font = ImageFont.load_default()
            height, lines = measure_text_block(text, font, max_width)
            return font, lines
        
        # Уменьшаем размер на 2 пт
        current_size -= 2
    
    # Если даже минимальный размер не помещается - возвращаем его
    try:
        font = ImageFont.truetype(base_font_path, min_size)
    except (OSError, IOError):
        font = ImageFont.load_default()
    
    _, lines = measure_text_block(text, font, max_width)
    return font, lines


def calculate_text_position(text_height: int, container_height: int, vertical_align: str = "center") -> int:
    """
    Вычисляет Y-позицию для размещения текста в контейнере
    
    Args:
        text_height: Высота текстового блока
        container_height: Высота контейнера
        vertical_align: Выравнивание ("top", "center", "bottom")
    
    Returns:
        Y-координата для размещения текста
    """
    if vertical_align == "top":
        return 0
    elif vertical_align == "bottom":
        return container_height - text_height
    else:  # center
        return (container_height - text_height) // 2

