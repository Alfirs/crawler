"""
Text overlay service - качественный рендер текста с обводкой и плашками
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageStat
from typing import Tuple, Optional, Dict, Any, List
import io
import os
import re

# Константы
SAFE = 64  # соответствует текущей логике SAFE_MARGIN
DEFAULT_CANVAS = (1024, 1024)


def _avg_luma(img: Image.Image, bbox: Optional[Tuple[int, int, int, int]] = None) -> float:
    """Return average luminance 0..1 optionally limited by bbox."""
    region = img.crop(bbox) if bbox else img
    if region.mode != "L":
        region = region.convert("L")
    stat = ImageStat.Stat(region)
    if not stat.mean:
        return 0.0
    return min(1.0, max(0.0, stat.mean[0] / 255.0))


def load_font(font_candidates: List[str], size: int) -> ImageFont.FreeTypeFont:
    """Load font with graceful fallback chain (project assets -> system -> Pillow default)."""
    paths = [p for p in font_candidates if p]

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
    fonts_dir = os.path.join(base_dir, "assets", "fonts")

    local_priority = [
        "Inter-Bold.ttf",
        "Inter-Regular.ttf",
        "Manrope-Bold.ttf",
        "Manrope-Regular.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ]

    for name in local_priority:
        path = os.path.join(fonts_dir, name)
        if os.path.exists(path):
            paths.append(path)

    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]

    for sys_font in system_fonts:
        if os.path.exists(sys_font):
            paths.append(sys_font)

    seen = set()
    unique_paths = []
    for p in paths:
        if p and p not in seen:
            unique_paths.append(p)
            seen.add(p)

    for p in unique_paths:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def hex_to_rgba(color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    """Конвертирует hex цвет в RGBA"""
    c = color.lstrip("#")
    if len(c) == 3:
        r, g, b = [int(v * 2, 16) for v in c]
    else:
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
    return (r, g, b, alpha)


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """
    Точное измерение текста через textbbox
    
    Args:
        draw: ImageDraw объект
        text: Текст для измерения
        font: Шрифт
        
    Returns:
        (ширина, высота) в пикселях
    """
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except AttributeError:
        # Fallback для старых версий Pillow
        width, height = font.getsize(text)
        return width, height


def fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_candidates: List[str],
    max_w: int,
    max_h: int,
    min_px: int = 20,
    max_px: int = 128,
    step: int = 2
) -> ImageFont.FreeTypeFont:
    """
    Подбирает размер шрифта бинарным поиском
    
    Args:
        draw: ImageDraw объект
        text: Текст для измерения
        font_candidates: Список путей к шрифтам
        max_w: Максимальная ширина
        max_h: Максимальная высота
        min_px: Минимальный размер
        max_px: Максимальный размер
        step: Шаг уменьшения
        
    Returns:
        Подобранный шрифт
    """
    lo, hi = min_px, max_px
    best = load_font(font_candidates, lo)
    
    while lo <= hi:
        mid = (lo + hi) // 2
        font = load_font(font_candidates, mid)
        w, h = text_bbox(draw, text, font)
        
        if w <= max_w and h <= max_h:
            best = font
            lo = mid + step
        else:
            hi = mid - step
    
    return best


def draw_rounded_plate(
    img: Image.Image,
    bbox: Tuple[int, int, int, int],
    radius: int = 18,
    alpha: int = 165,
    blur: int = 0
) -> None:
    """
    Рисует скруглённую плашку для текста
    
    Args:
        img: Изображение (должно быть RGBA)
        bbox: (x0, y0, x1, y1) область плашки
        radius: Радиус скругления
        alpha: Прозрачность (0-255)
        blur: Размытие (0 = без размытия)
    """
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    
    if width <= 0 or height <= 0:
        return
    
    plate = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pd.rounded_rectangle((0, 0, width, height), radius=radius, fill=(0, 0, 0, alpha))
    
    if blur > 0:
        plate = plate.filter(ImageFilter.GaussianBlur(blur))
    
    # Убеждаемся что изображение RGBA
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    img.alpha_composite(plate, (x0, y0))


def draw_with_stroke(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_width: int = 2,
    stroke_fill: Tuple[int, int, int, int] = (0, 0, 0, 220),
    anchor: str = "la",
    align: str = "left"
) -> None:
    """
    Рисует текст с обводкой
    
    Args:
        draw: ImageDraw объект
        xy: Позиция (x, y)
        text: Текст
        font: Шрифт
        fill: Цвет текста (RGBA)
        stroke_width: Толщина обводки
        stroke_fill: Цвет обводки (RGBA)
        anchor: Якорь позиционирования
        align: Выравнивание
    """
    try:
        # Pillow 10.0+ поддерживает stroke_width
        draw.text(
            xy, text, font=font, fill=fill,
            stroke_width=stroke_width, stroke_fill=stroke_fill,
            anchor=anchor, align=align
        )
    except TypeError:
        # Fallback для старых версий - только без stroke
        draw.text(xy, text, font=font, fill=fill, anchor=anchor, align=align)


def smart_wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    draw: ImageDraw.ImageDraw
) -> List[str]:
    """
    Умный перенос текста с разбиением длинных слов для кириллицы
    Обрабатывает явные переносы строк (\n) как разделители
    
    Args:
        text: Исходный текст
        font: Шрифт для измерения
        max_width: Максимальная ширина
        draw: ImageDraw для измерения
        
    Returns:
        Список строк
    """
    # Сначала обрабатываем явные переносы строк
    paragraphs = text.split('\n')
    all_lines = []
    
    for para in paragraphs:
        if not para.strip():
            all_lines.append("")
            continue
        
        parts = para.split()
        lines = []
        cur = []
        
        for w in parts:
            test = (" ".join(cur + [w])).strip()
            try:
                bbox = draw.textbbox((0, 0), test, font=font)
                w_px = bbox[2] - bbox[0]
            except AttributeError:
                w_px = font.getsize(test)[0]
            
            if w_px <= max_width:
                cur.append(w)
            else:
                if not cur:
                    # Слово длиннее строки - принудительный перенос по символам
                    for i in range(len(w), 0, -1):
                        seg = w[:i] + "-"
                        try:
                            bbox = draw.textbbox((0, 0), seg, font=font)
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
        
        all_lines.extend(lines)
    
    return all_lines if all_lines else [text]


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    draw: ImageDraw.ImageDraw
) -> List[str]:
    """
    Обертка для smart_wrap_text для совместимости
    
    Args:
        text: Исходный текст
        font: Шрифт для измерения
        max_width: Максимальная ширина
        draw: ImageDraw для измерения
        
    Returns:
        Список строк
    """
    return smart_wrap_text(text, font, max_width, draw)


def render_block(
    img: Image.Image,
    text: str,
    box: Tuple[int, int, int, int],  # (x0, y0, x1, y1)
    align: str = "left",
    font_candidates: Optional[List[str]] = None,
    prefer_bold: bool = True,
    color: str = "#FFFFFF",
    stroke: Optional[Dict[str, Any]] = None,
    plate: Optional[Dict[str, Any]] = None,
    line_spacing: float = 1.15,
    max_font_size: int = 140,
    min_font_size: int = 20,
    safe_pad: int = 64,
) -> None:
    """
    Рендерит текстовый блок с обводкой и плашкой
    
    Args:
        img: Изображение (будет конвертировано в RGBA если нужно)
        text: Текст для рендера
        box: (x0, y0, x1, y1) область внутри safe-zone
        align: Выравнивание ("left", "center")
        font_candidates: Список путей к шрифтам
        prefer_bold: Предпочитать жирные шрифты
        color: Цвет текста (hex)
        stroke: Настройки обводки {"width": 2, "color": "#000000", "alpha": 220}
        plate: Настройки плашки {"enabled": True, "padding": 28, "alpha": 165, "radius": 18, "blur": 0}
        line_spacing: Межстрочный интервал
        max_font_size: Максимальный размер шрифта
        min_font_size: Минимальный размер шрифта
    """
    if not text or not text.strip():
        return
    
    # Убеждаемся что изображение RGBA
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size
    x0, y0, x1, y1 = box
    x0 = max(x0, safe_pad)
    y0 = max(y0, safe_pad)
    x1 = min(x1, img_w - safe_pad)
    y1 = min(y1, img_h - safe_pad)
    max_w = x1 - x0
    max_h = min(y1 - y0, int(img_h * 0.65))
    
    if max_w <= 0 or max_h <= 0:
        return
    
    # Подготовка списка шрифтов
    if font_candidates is None:
        font_candidates = []
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fonts_dir = os.path.join(base_dir, "assets", "fonts")
    
    # Добавляем стандартные пути если их нет
    if not font_candidates:
        if prefer_bold:
            font_candidates.extend([
                os.path.join(fonts_dir, "Inter-Bold.ttf"),
                os.path.join(fonts_dir, "Manrope-Bold.ttf"),
            ])
        else:
            font_candidates.extend([
                os.path.join(fonts_dir, "Inter-Regular.ttf"),
                os.path.join(fonts_dir, "Manrope-Regular.ttf"),
            ])
    
    # Первоначальный подбор размера по одной строке
    font = fit_font_size(
        draw, text, font_candidates, max_w, max_h,
        min_px=min_font_size, max_px=max_font_size
    )
    
    # Умный перенос по ширине
    lines = smart_wrap_text(text, font, max_w, draw)
    
    # Измеряем высоту
    try:
        line_h = text_bbox(draw, "Hg", font)[1]
    except Exception:
        current_font_size = getattr(font, 'size', 24)
        line_h = current_font_size * 1.2
    
    height_total = int(len(lines) * line_h * line_spacing)
    
    # Если высота не влазит - уменьшаем шрифт и пересчитываем
    current_size = getattr(font, 'size', max_font_size)
    while height_total > max_h and current_size > min_font_size:
        current_size -= 2
        font = load_font(font_candidates, current_size)
        lines = smart_wrap_text(text, font, max_w, draw)
        try:
            line_h = text_bbox(draw, "Hg", font)[1]
        except Exception:
            current_font_size = getattr(font, 'size', current_size)
            line_h = current_font_size * 1.2
        height_total = int(len(lines) * line_h * line_spacing)
    
    # Рисуем плашку если нужно
    text_rect = (x0, y0, x0 + max_w, y0 + height_total)
    if plate and plate.get("enabled"):
        pad = int(plate.get("padding", 24))
        px0 = max(x0 - pad, 0)
        py0 = max(y0 - pad, 0)
        px1 = min(x0 + max_w + pad, img.size[0])
        py1 = min(y0 + height_total + pad, img.size[1])
        draw_rounded_plate(
            img,
            (px0, py0, px1, py1),
            radius=int(plate.get("radius", 18)),
            alpha=int(plate.get("alpha", 165)),
            blur=int(plate.get("blur", 0)),
        )
    else:
        luma = _avg_luma(img, text_rect)
        if luma > 0.7:
            pad = 24
            px0 = max(x0 - pad, 0)
            py0 = max(y0 - pad, 0)
            px1 = min(x0 + max_w + pad, img.size[0])
            py1 = min(y0 + height_total + pad, img.size[1])
            draw_rounded_plate(
                img,
                (px0, py0, px1, py1),
                radius=20,
                alpha=90,
                blur=0,
            )
            stroke = {"width": 1, "color": "#000000", "alpha": 200}
            color = "#FFFFFF"

    # Выравнивание
    cx = x0 if align == "left" else x0 + max_w // 2
    cy = y0
    
    # Подготовка цветов
    rgba_text = hex_to_rgba(color, 255)
    
    # Настройки обводки
    if stroke is None:
        stroke = {"width": 2, "color": "#000000", "alpha": 220}
    
    s_w = int(stroke.get("width", 2))
    s_col = stroke.get("color", "#000000")
    s_alpha = int(stroke.get("alpha", 220))
    rgba_stroke = hex_to_rgba(s_col, s_alpha)
    
    # Рисуем строки
    for i, ln in enumerate(lines):
        ty = int(cy + i * line_h * line_spacing)
        
        if align == "left":
            draw_with_stroke(
                draw, (x0, ty), ln, font,
                fill=rgba_text, stroke_width=s_w, stroke_fill=rgba_stroke,
                anchor="la", align="left"
            )
        else:
            draw_with_stroke(
                draw, (cx, ty), ln, font,
                fill=rgba_text, stroke_width=s_w, stroke_fill=rgba_stroke,
                anchor="ma", align="center"
            )


def preset_box(img_size: Tuple[int, int], preset: str = "center") -> Tuple[int, int, int, int]:
    """
    Создаёт стандартную область для текста
    
    Args:
        img_size: (ширина, высота) изображения
        preset: "top", "center", "bottom"
        
    Returns:
        (x0, y0, x1, y1) область внутри safe-zone
    """
    W, H = img_size
    x0 = SAFE
    x1 = W - SAFE
    
    if preset == "bottom":
        y0 = H - SAFE - int(H * 0.30)
        y1 = H - SAFE
    elif preset == "top":
        y0 = SAFE
        y1 = SAFE + int(H * 0.30)
    else:  # center
        block_h = int(H * 0.40)
        y0 = (H - block_h) // 2
        y1 = y0 + block_h
    
    return (x0, y0, x1, y1)


def render_slide(
    img: Image.Image,
    slide_type: str,
    content: Dict[str, Any],
    safe_pad: int = 64,
) -> Image.Image:
    """Render slide according to preset type or custom template blocks."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    draw = ImageDraw.Draw(img)
    W, H = img.size

    default_stroke = {"width": 2, "color": "#000000", "alpha": 180}
    default_plate = {"enabled": True, "padding": 24, "alpha": 140, "radius": 16, "blur": 0}

    def resolve_box(box_data: Dict[str, Any]) -> Tuple[int, int, int, int]:
        return (
            int(box_data.get("x0", SAFE)),
            int(box_data.get("y0", SAFE)),
            int(box_data.get("x1", W - SAFE)),
            int(box_data.get("y1", H - SAFE)),
        )

    if slide_type == "cover":
        title_box = (safe_pad, H - 420, W - safe_pad, H - safe_pad)
        render_block(
            img=img,
            text=content.get("title", "").strip(),
            box=title_box,
            align="left",
            font_candidates=["app/assets/fonts/Inter-Bold.ttf"],
            prefer_bold=True,
            color=content.get("color", "#FFFFFF"),
            stroke=content.get("stroke", default_stroke),
            plate=content.get("plate", default_plate),
            line_spacing=1.15,
            max_font_size=140,
            min_font_size=48,
            safe_pad=safe_pad,
        )

        swipe_font = load_font(["app/assets/fonts/Inter-Regular.ttf"], 40)
        swipe_text = content.get("swipe", "Листай дальше →")
        draw.text((SAFE, H - 80), swipe_text, fill="#D0D0D0", font=swipe_font)

    elif slide_type == "content":
        header_font = load_font(["app/assets/fonts/Inter-Regular.ttf"], 40)
        if content.get("page_num"):
            draw.text((W - 150, 60), content["page_num"], fill="#9E9E9E", font=header_font)

        title_box = (safe_pad, 200, W - safe_pad, 600)
        render_block(
            img=img,
            text=content.get("title", "").strip(),
            box=title_box,
            align="left",
            font_candidates=["app/assets/fonts/Inter-Bold.ttf"],
            prefer_bold=True,
            color=content.get("title_color", "#111111"),
            stroke=content.get("title_stroke", default_stroke),
            plate=content.get("title_plate", default_plate),
            line_spacing=1.15,
            max_font_size=90,
            min_font_size=70,
            safe_pad=safe_pad,
        )

        if content.get("body"):
            body_box = (safe_pad, 640, W - safe_pad, H - 200)
            render_block(
                img=img,
                text=content.get("body", "").strip(),
                box=body_box,
                align="left",
                font_candidates=["app/assets/fonts/Inter-Regular.ttf"],
                prefer_bold=False,
                color=content.get("body_color", "#111111"),
                stroke=content.get("body_stroke", default_stroke),
                plate=content.get("body_plate", default_plate),
                line_spacing=content.get("line_spacing", 1.2),
                max_font_size=48,
                min_font_size=42,
                safe_pad=safe_pad,
            )

        swipe_font = load_font(["app/assets/fonts/Inter-Regular.ttf"], 36)
        swipe_text = content.get("swipe", "Листай дальше →")
        draw.text((SAFE, H - 80), swipe_text, fill="#D0D0D0", font=swipe_font)

    elif slide_type == "color":
        title_box = (safe_pad, 400, W - safe_pad, H - 250)
        render_block(
            img=img,
            text=content.get("title", "").strip(),
            box=title_box,
            align="left",
            font_candidates=["app/assets/fonts/Inter-Bold.ttf"],
            prefer_bold=True,
            color=content.get("title_color", "#FFFFFF"),
            stroke=content.get("title_stroke", default_stroke),
            plate=content.get("title_plate", default_plate),
            line_spacing=1.15,
            max_font_size=140,
            min_font_size=48,
            safe_pad=safe_pad,
        )

        if content.get("body"):
            body_box = (safe_pad, 650, W - safe_pad, H - 120)
            render_block(
                img=img,
                text=content.get("body", "").strip(),
                box=body_box,
                align="left",
                font_candidates=["app/assets/fonts/Inter-Regular.ttf"],
                prefer_bold=False,
                color=content.get("body_color", "#FFFFFF"),
                stroke=content.get("body_stroke", default_stroke),
                plate=content.get("body_plate", default_plate),
                line_spacing=content.get("line_spacing", 1.2),
                max_font_size=60,
                min_font_size=42,
                safe_pad=safe_pad,
            )

        swipe_font = load_font(["app/assets/fonts/Inter-Regular.ttf"], 36)
        swipe_text = content.get("swipe", "Листай дальше →")
        draw.text((SAFE, H - 80), swipe_text, fill="#D0D0D0", font=swipe_font)

    elif slide_type == "custom":
        blocks = content.get("blocks", [])
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type", "text")
            box_data = block.get("box", {})
            if not isinstance(box_data, dict):
                continue
            box_tuple = resolve_box(box_data)

            style = block.get("style", {}) or {}
            stroke = style.get("stroke", default_stroke)
            plate = style.get("plate", default_plate)

            if block_type == "text":
                text_value = block.get("text", "")
                weight = style.get("weight", "bold")
                prefer_bold = weight == "bold"

                candidates = []
                font_path = style.get("font_path")
                if font_path:
                    candidates.append(font_path)
                family = style.get("font_family")
                if family == "Inter":
                    candidates.append("app/assets/fonts/Inter-Bold.ttf" if prefer_bold else "app/assets/fonts/Inter-Regular.ttf")
                candidates.append("app/assets/fonts/DejaVuSans-Bold.ttf" if prefer_bold else "app/assets/fonts/DejaVuSans.ttf")

                render_block(
                    img=img,
                    text=text_value,
                    box=box_tuple,
                    align=block.get("align", "left"),
                    font_candidates=candidates,
                    prefer_bold=prefer_bold,
                    color=style.get("color", "#FFFFFF" if prefer_bold else "#111111"),
                    stroke=stroke,
                    plate=plate,
                    line_spacing=style.get("line_spacing", 1.15),
                    max_font_size=style.get("max_font_size", 120),
                    min_font_size=style.get("min_font_size", 32),
                    safe_pad=safe_pad,
                )
            elif block_type == "image":
                source = block.get("source")
                if not source:
                    continue
                try:
                    if isinstance(source, (bytes, bytearray)):
                        block_img = Image.open(io.BytesIO(source)).convert("RGBA")
                    elif isinstance(source, str) and os.path.exists(source):
                        block_img = Image.open(source).convert("RGBA")
                    else:
                        continue

                    target_w = box_tuple[2] - box_tuple[0]
                    target_h = box_tuple[3] - box_tuple[1]
                    block_img = block_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                    img.alpha_composite(block_img, (box_tuple[0], box_tuple[1]))
                except Exception:
                    continue

    return img
