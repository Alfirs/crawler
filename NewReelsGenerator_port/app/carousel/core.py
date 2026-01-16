from __future__ import annotations
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageFilter
import random, datetime, re
import math

W, H = 1080, 1350
SAFE = 72
WHITE = (255, 255, 255)
CONTENT_Y = SAFE + 160  # For list/text slides
CONTENT_Y_COVER = int(H * 0.62)  # For cover slide

def _load_font(size: int):
    """Подбор шрифта по списку приоритетов: Inter -> Arial -> fallback."""
    candidates = [
        Path("fonts/Inter-SemiBold.ttf"),
        Path("fonts/Inter.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return ImageFont.truetype(str(p), size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def _font_big() -> ImageFont.FreeTypeFont:
    return _load_font(78)


def _font_body() -> ImageFont.FreeTypeFont:
    return _load_font(44)


def _font_small() -> ImageFont.FreeTypeFont:
    return _load_font(36)


def _apply_bottom_gradient(img: Image.Image, strength: float = 0.6, bottom_ratio: float = 0.45) -> Image.Image:
    """Adds a black-to-transparent gradient from bottom. strength controls opacity, bottom_ratio controls height."""
    strength = min(strength, 0.65)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    grad = Image.new("L", (1, H), color=0)
    fade_start_y = int(H * (1 - bottom_ratio))
    fade_range = H - fade_start_y
    for y in range(H):
        if y >= fade_start_y:
            # From fade_start_y to bottom: gradient from transparent to opaque
            progress = (y - fade_start_y) / fade_range if fade_range > 0 else 1.0
            alpha = int(255 * strength * progress)
        else:
            alpha = 0
        grad.putpixel((0, y), alpha)
    alpha = grad.resize(img.size)
    overlay.putalpha(alpha)
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

def _apply_vignette(img: Image.Image, strength: float = 0.3) -> Image.Image:
    """Adds a subtle vignette effect to the image."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    center_x, center_y = W / 2, H / 2
    max_dist = math.sqrt(center_x**2 + center_y**2)
    
    for y in range(H):
        for x in range(W):
            dist = math.sqrt((x - center_x)**2 + (y - center_y)**2)
            # Normalize to 0..1
            normalized = min(dist / max_dist, 1.0)
            # Vignette: darker at edges
            alpha = int(255 * strength * (normalized ** 2))
            overlay.putpixel((x, y), (0, 0, 0, alpha))
    
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _gradient(base=(31, 107, 67)):
    img = Image.new("RGB", (W, H), base)
    overlay = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(overlay)
    for y in range(H):
        a = int(160 * (y / H))
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.paste(overlay, (0, 0), overlay)
    return img

def _bg_photo(path: str, apply_darkening: bool = True) -> Optional[Image.Image]:
    """Load and prepare a photo background. Returns RGB Image."""
    p = Path(path)
    if p.is_file():
        pics = [p]
    else:
        pics = [x for x in p.glob("*") if x.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not pics:
        return None
    im = Image.open(random.choice(pics)).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    x = (im.width - W) // 2
    y = (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H))
    if apply_darkening:
        im = Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.35)
    return im

def _extract_palette(img: Image.Image, k: int = 4) -> List[Tuple[int, int, int]]:
    """Extract dominant colors from image using simple histogram method (no kmeans dependency)."""
    # Resize for faster processing
    small = img.resize((200, 200), Image.LANCZOS)
    pixels = list(small.getdata())
    
    # Simple color quantization: group similar colors
    color_buckets = {}
    for r, g, b in pixels:
        # Quantize to 16 levels
        qr, qg, qb = r // 16, g // 16, b // 16
        key = (qr, qg, qb)
        if key not in color_buckets:
            color_buckets[key] = []
        color_buckets[key].append((r, g, b))
    
    # Get most frequent buckets
    sorted_buckets = sorted(color_buckets.items(), key=lambda x: len(x[1]), reverse=True)
    
    palette = []
    for (qr, qg, qb), pixel_list in sorted_buckets[:k * 2]:  # Get more candidates
        # Average colors in bucket
        avg_r = sum(p[0] for p in pixel_list) // len(pixel_list)
        avg_g = sum(p[1] for p in pixel_list) // len(pixel_list)
        avg_b = sum(p[2] for p in pixel_list) // len(pixel_list)
        palette.append((avg_r, avg_g, avg_b))
    
    # Deduplicate similar colors and limit to k
    final_palette = []
    for color in palette[:k * 2]:
        is_duplicate = False
        for existing in final_palette:
            # Check if colors are too similar (within 30 RGB units)
            if abs(color[0] - existing[0]) + abs(color[1] - existing[1]) + abs(color[2] - existing[2]) < 90:
                is_duplicate = True
                break
        if not is_duplicate:
            final_palette.append(color)
            if len(final_palette) >= k:
                break
    
    return final_palette[:k] if final_palette else [(30, 30, 40), (50, 50, 60), (20, 20, 30)]

def _generate_clean_bg(palette: List[Tuple[int, int, int]]) -> Image.Image:
    """Generate a clean gradient background from palette colors."""
    if not palette:
        palette = [(30, 30, 40), (50, 50, 60), (20, 20, 30)]
    
    # Улучшаем палитру: сохраняем стилистику, но делаем фон видимым
    # Для темно-синих/черных тонов (как в шаблоне) сохраняем стилистику, но немного осветляем
    def _enhance_color(color: Tuple[int, int, int], min_brightness: int = 50, max_brightness: int = 120) -> Tuple[int, int, int]:
        """Улучшает цвет, сохраняя стилистику: для темных цветов немного осветляет, но не меняет оттенок."""
        r, g, b = color
        brightness = (r + g + b) / 3
        
        # Если цвет слишком темный, делаем его немного ярче, сохраняя оттенок
        if brightness < min_brightness:
            # Осветляем пропорционально, сохраняя соотношение цветов
            if brightness > 0:
                factor = min_brightness / brightness
            else:
                factor = 2.0
            
            # Ограничиваем осветление, чтобы не потерять стилистику
            factor = min(factor, 1.8)
            
            r = min(255, int(r * factor))
            g = min(255, int(g * factor))
            b = min(255, int(b * factor))
        
        # Если цвет слишком яркий, немного затемняем
        elif brightness > max_brightness:
            factor = max_brightness / brightness
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
        
        return (r, g, b)
    
    # Применяем улучшение к палитре - сохраняем стилистику (темно-синий, черный), но делаем видимым
    enhanced_palette = [_enhance_color(c, min_brightness=45, max_brightness=130) for c in palette[:5]]
    print(f"DEBUG _generate_clean_bg: original palette={palette[:3]}, enhanced={enhanced_palette[:3]}")
    
    # Используем улучшенные цвета (сохраняем стилистику темно-синий/черный)
    colors = enhanced_palette[:min(3, len(enhanced_palette))]
    if len(colors) == 0:
        colors = [(50, 50, 60), (70, 70, 80)]
    elif len(colors) == 1:
        # Создаем второй цвет на основе первого (немного ярче)
        base = colors[0]
        colors = [base, (min(255, base[0] + 30), min(255, base[1] + 30), min(255, base[2] + 30))]
    
    bg = Image.new("RGB", (W, H), colors[0])
    draw = ImageDraw.Draw(bg)
    
    # Создаем вертикальный градиент
    for y in range(H):
        progress = y / H
        if len(colors) == 2:
            r = int(colors[0][0] * (1 - progress) + colors[1][0] * progress)
            g = int(colors[0][1] * (1 - progress) + colors[1][1] * progress)
            b = int(colors[0][2] * (1 - progress) + colors[1][2] * progress)
        elif len(colors) >= 3:
            # Используем средний цвет в центре
            if progress < 0.5:
                p = progress * 2
                r = int(colors[0][0] * (1 - p) + colors[1][0] * p)
                g = int(colors[0][1] * (1 - p) + colors[1][1] * p)
                b = int(colors[0][2] * (1 - p) + colors[1][2] * p)
            else:
                p = (progress - 0.5) * 2
                r = int(colors[1][0] * (1 - p) + colors[2][0] * p)
                g = int(colors[1][1] * (1 - p) + colors[2][1] * p)
                b = int(colors[1][2] * (1 - p) + colors[2][2] * p)
        else:
            r, g, b = colors[0]
        
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    
    # Добавляем тонкую текстуру (очень слабо)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for _ in range(30):  # Меньше точек для более чистой текстуры
        x = random.randint(0, W-1)
        y = random.randint(0, H-1)
        overlay_draw.ellipse([x-2, y-2, x+2, y+2], fill=(255, 255, 255, 5))
    
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    return bg

def _ensure_readability(img: Image.Image, text_area: Tuple[int, int, int, int]) -> float:
    """Check contrast in text area and return required overlay strength (0.0-1.0)."""
    x0, y0, x1, y1 = text_area
    crop = img.crop((x0, y0, min(x1, W), min(y1, H)))
    
    # Blur to check overall brightness
    blurred = crop.filter(ImageFilter.GaussianBlur(radius=10))
    pixels = list(blurred.getdata())
    
    # Calculate average luminance
    luminances = []
    for r, g, b in pixels:
        # Relative luminance formula
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
        luminances.append(lum)
    
    avg_lum = sum(luminances) / len(luminances) if luminances else 128
    std_lum = math.sqrt(sum((l - avg_lum)**2 for l in luminances) / len(luminances)) if len(luminances) > 1 else 0
    
    # Threshold for low contrast detection
    contrast_threshold = 25
    
    # If average is too bright (>180) or contrast too low, need more overlay
    if avg_lum > 180:
        return 0.8  # Strong overlay needed
    elif avg_lum > 140:
        return 0.7  # Increased from 0.6
    elif std_lum < contrast_threshold:  # Low contrast - increase gradient
        return 0.65  # Increased from 0.5
    else:
        return 0.5  # Increased default from 0.4

def _bg_from_cfg(cfg: dict | None, style_hint: str = "", palette_cache: List[Tuple[int, int, int]] | None = None) -> Image.Image:
    """Load background from config. Supports 'photo', 'clean', and 'solid' modes."""
    cfg = cfg or {}
    mode = cfg.get("mode", "solid")
    hint = (style_hint or "").lower()
    wants_orange = "orange" in hint or "оранж" in hint
    
    if mode == "photo" and cfg.get("path"):
        im = _bg_photo(cfg["path"], apply_darkening=False)  # Don't darken cover photos
        if im:
            return im
    
    if mode == "clean":
        # Use palette from config or cache
        palette = cfg.get("palette") or palette_cache
        print(f"DEBUG _bg_from_cfg: mode=clean, palette from cfg={cfg.get('palette')}, palette_cache={palette_cache}, final palette={palette}")
        if not palette:
            print("WARN: No palette in _bg_from_cfg, using default")
            palette = [(30, 30, 40), (50, 50, 60), (20, 20, 30)]
        if not isinstance(palette, list) or len(palette) == 0:
            print("WARN: Invalid palette format, using default")
            palette = [(30, 30, 40), (50, 50, 60), (20, 20, 30)]
        return _generate_clean_bg(palette)
    
    if mode == "solid":
        base = (120, 40, 10) if wants_orange else ImageColor.getrgb(cfg.get("color", "#1f6b43"))
        return _gradient(base)
    
    return _gradient((120, 40, 10) if wants_orange else (31, 107, 67))

def _font_semibold(size: int = 44) -> ImageFont.FreeTypeFont:
    """Load semibold font for bold text rendering."""
    candidates = [
        Path("fonts/Inter-SemiBold.ttf"),
        Path("fonts/Inter-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
    for p in candidates:
        try:
            if p.exists():
                return ImageFont.truetype(str(p), size=size)
        except Exception:
            pass
    return _load_font(size)  # Fallback to regular

def _parse_markup(text: str) -> List[Tuple[str, str]]:
    """Parse text with markup [[accent]], __underline__, **bold** into tokens.
    Returns list of (type, content) where type is 'normal', 'accent', 'underline', 'bold'.
    """
    if not text:
        return [("normal", "")]
    
    tokens = []
    remaining = text
    
    # Simple regex-based parsing
    import re
    # Find all markup patterns
    pattern = r'(\[\[.*?\]\])|(__.*?__)|(\*\*.*?\*\*)'
    parts = re.split(pattern, remaining)
    
    for part in parts:
        if not part:
            continue
        if part.startswith('[[') and part.endswith(']]'):
            if tokens and tokens[-1][0] == "normal":
                # Merge preceding normal
                pass
            tokens.append(("accent", part[2:-2]))
        elif part.startswith('__') and part.endswith('__'):
            if tokens and tokens[-1][0] == "normal":
                pass
            tokens.append(("underline", part[2:-2]))
        elif part.startswith('**') and part.endswith('**'):
            if tokens and tokens[-1][0] == "normal":
                pass
            tokens.append(("bold", part[2:-2]))
        else:
            if tokens and tokens[-1][0] == "normal":
                tokens[-1] = ("normal", tokens[-1][1] + part)
            else:
                tokens.append(("normal", part))
    
    return tokens if tokens else [("normal", text)]

def _measure_token_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    """Measure width of a text token."""
    return font.getlength(text)

def _wrap_rich(tokens: List[Tuple[str, str]], font: ImageFont.FreeTypeFont, max_w: int) -> List[List[Tuple[str, str]]]:
    """Wrap rich text tokens into lines that fit max_w."""
    if not tokens:
        return []
    
    lines = []
    current_line = []
    current_width = 0.0
    
    for token_type, token_text in tokens:
        words = token_text.split() if " " in token_text else [token_text]
        for word in words:
            word_width = _measure_token_width(word, font)
            space_width = _measure_token_width(" ", font) if current_line else 0
            
            if current_width + space_width + word_width > max_w and current_line:
                lines.append(current_line)
                current_line = [(token_type, word)]
                current_width = word_width
            else:
                if current_line and current_line[-1][0] == token_type:
                    # Merge with same type
                    separator = " " if current_width > 0 else ""
                    current_line[-1] = (token_type, current_line[-1][1] + separator + word)
                    current_width += space_width + word_width
                else:
                    current_line.append((token_type, word))
                    current_width += word_width + space_width
    
    if current_line:
        lines.append(current_line)
    
    return lines

def _fit_text(font_base: ImageFont.FreeTypeFont, text: str, max_width: int, min_size: int, max_size: int) -> Tuple[ImageFont.FreeTypeFont, str]:
    """Auto-scale font to fit text in max_width, keeping within min_size..max_size. Returns (font, wrapped_text)."""
    # Simple approach: try to wrap first, then scale down if > 2 lines
    draw_temp = ImageDraw.Draw(Image.new("RGB", (W, H)))
    current_size = max_size
    
    for attempt in range(10):
        test_font = _load_font(current_size)
        wrapped = _wrap(draw_temp, text, test_font, max_width)
        lines = wrapped.count("\n") + 1
        if lines <= 2:
            return test_font, wrapped
        current_size = max(min_size, int(current_size * 0.85))
    
    return _load_font(min_size), _wrap(draw_temp, text, _load_font(min_size), max_width)

def _get_accent_color(palette: List[Tuple[int, int, int]]) -> Tuple[int, int, int]:
    """Pick the most saturated or contrasting color from palette for accent."""
    if not palette:
        return (255, 200, 0)  # Default accent
    
    # Find most saturated color
    best_sat = -1
    best_color = palette[0]
    
    for r, g, b in palette:
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        if max_val == 0:
            continue
        saturation = (max_val - min_val) / max_val if max_val > 0 else 0
        if saturation > best_sat:
            best_sat = saturation
            best_color = (r, g, b)
    
    # Boost saturation if too low
    r, g, b = best_color
    if best_sat < 0.3:
        # Make it more vibrant
        r = min(255, max(0, int(r * 1.3)))
        g = min(255, max(0, int(g * 1.3)))
        b = min(255, max(0, int(b * 1.3)))
        return (r, g, b)
    
    return best_color

def _draw_accent_pill(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, text: str, font: ImageFont.FreeTypeFont,
                     accent_color: Tuple[int, int, int], palette: List[Tuple[int, int, int]] | None = None,
                     pad: Tuple[int, int] = (12, 6), radius: int = 10) -> Tuple[int, Image.Image, ImageDraw.ImageDraw]:
    """Draw text in a rounded rectangle pill background with accent color. Returns (x after pill, updated img, updated draw)."""
    bbox = draw.textbbox((x, y), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    pill_w = text_w + pad[0] * 2
    pill_h = text_h + pad[1] * 2
    pill_x0 = x
    pill_y0 = y + bbox[1] - pad[1]
    pill_x1 = pill_x0 + pill_w
    pill_y1 = pill_y0 + pill_h
    
    # Determine pill background color: use accent color but darken if contrast is poor
    # Use most saturated color from palette if available
    if palette:
        pill_bg_color = _get_accent_color(palette)
    else:
        pill_bg_color = accent_color
    
    # Darken color by 10-20% if too bright for contrast
    r, g, b = pill_bg_color
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum > 180:
        # Too bright, darken by 15%
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
    elif lum > 140:
        # Moderate brightness, darken by 10%
        r = max(0, int(r * 0.9))
        g = max(0, int(g * 0.9))
        b = max(0, int(b * 0.9))
    
    # Use RGBA with alpha ~160-180 for semi-transparency
    pill_bg_rgba = (r, g, b, 170)
    
    # Create overlay for semi-transparent background
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle([(pill_x0, pill_y0), (pill_x1, pill_y1)], 
                                  fill=pill_bg_rgba, radius=radius)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    
    # Recreate draw object after converting back to RGB
    draw = ImageDraw.Draw(img)
    
    # Draw text on top (white for contrast)
    text_x = pill_x0 + pad[0]
    text_y = y
    draw.text((text_x, text_y), text, font=font, fill=WHITE)
    
    return pill_x1, img, draw

def _draw_rich_line(img: Image.Image, draw: ImageDraw.ImageDraw, line_tokens: List[Tuple[str, str]], start_x: int, y: int, 
                    line_height: int, base_font: ImageFont.FreeTypeFont, accent_color: Tuple[int, int, int],
                    bold_font: ImageFont.FreeTypeFont | None = None, 
                    palette: List[Tuple[int, int, int]] | None = None) -> Tuple[int, Image.Image, ImageDraw.ImageDraw]:
    """Draw a line of rich text tokens. Returns (x position after line, updated img, updated draw)."""
    x = start_x
    current_img = img
    current_draw = draw
    
    for token_type, token_text in line_tokens:
        if token_type == "accent":
            # Draw accent pill with palette-aware coloring
            x, current_img, current_draw = _draw_accent_pill(current_img, current_draw, x, y, token_text, base_font, 
                                                             accent_color=accent_color, palette=palette)
        elif token_type == "bold":
            font_to_use = bold_font if bold_font else base_font
            fill_color = WHITE
            
            if token_text.strip():
                if not bold_font:
                    # Draw with outline for bold effect
                    current_draw.text((x, y), token_text, font=font_to_use, fill=fill_color, 
                             stroke_width=2, stroke_fill=(0, 0, 0))
                else:
                    current_draw.text((x, y), token_text, font=font_to_use, fill=fill_color)
                x += _measure_token_width(token_text, font_to_use)
        elif token_type == "underline":
            font_to_use = base_font
            fill_color = WHITE
            
            if token_text.strip():
                current_draw.text((x, y), token_text, font=font_to_use, fill=fill_color)
                bbox = current_draw.textbbox((x, y), token_text, font=font_to_use)
                underline_y = bbox[3] + 2
                current_draw.line([(bbox[0], underline_y), (bbox[2], underline_y)], fill=WHITE, width=2)
                x += _measure_token_width(token_text, font_to_use)
        else:  # normal
            font_to_use = base_font
            fill_color = WHITE
            
            if token_text.strip():
                current_draw.text((x, y), token_text, font=font_to_use, fill=fill_color)
                x += _measure_token_width(token_text, font_to_use)
    
    return x, current_img, current_draw

def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    if not text:
        return ""
    words = text.split()
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if draw.textlength(" ".join(cur), font=font) > max_w:
            cur.pop(); lines.append(" ".join(cur)); cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)

def clean_slide_title(raw: str) -> str:
    if not raw:
        return raw
    cleaned = re.sub(r"^\s*Слайд\s*\d+\s*\(обложка\)\s*:\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*Слайд\s*\d+\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*Слайд\s*\d+\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def _header(draw: ImageDraw.ImageDraw, username: str, page: str, f_sm):
    draw.text((SAFE, SAFE), username, font=f_sm, fill=WHITE)
    tw = draw.textlength(page, font=f_sm)
    draw.text((W - SAFE - tw, SAFE), page, font=f_sm, fill=WHITE)


def _draw_block(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, x: int, y: int, *, spacing: int = 8) -> int:
    """
    Draw multiline text and return the bottom Y coordinate of the drawn block.
    """
    if not text:
        return y
    draw.multiline_text((x, y), text, font=font, fill=WHITE, spacing=spacing)
    _, _, _, bottom = draw.multiline_textbbox((x, y), text, font=font, spacing=spacing)
    return bottom

def render_carousel(job: dict, out_dir: Path, seed: int | None = None, username_override: str | None = None) -> Path:
    """
    Renders slides to PNG files with cover template, clean backgrounds, and markup support.

    job format:
    {
        "username": "...",
        "slides": [
            {
                "type": "cover" | "list" | "text",
                "title": str,
                "items": [str, ...],
                "body": str,
                "bg": {"mode": "photo"/"clean"/"solid", "path": str, ...},
            },
            ...
        ]
    }

    Returns Path to the output directory.
    """

    slides = job.get("slides", [])
    username = username_override or job.get("username") or "@username"

    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = Path(out_dir) / ts
    out.mkdir(parents=True, exist_ok=True)

    f_lg_base = _font_big()
    f_t = _font_body()
    f_sm = _font_small()
    f_bold = _font_semibold(44)

    total = len(slides)
    
    # Extract palette from cover if it's a photo
    palette_cache = None
    cover_img = None
    
    # Get cover slide background path
    if slides and slides[0].get("bg", {}).get("mode") == "photo":
        cover_bg_path = slides[0].get("bg", {}).get("path")
        if cover_bg_path and Path(cover_bg_path).exists():
            try:
                cover_img = _bg_photo(cover_bg_path, apply_darkening=False)
                if cover_img:
                    # Use img_analysis for better palette extraction
                    from app.services.img_analysis import dominant_palette
                    palette_cache = dominant_palette(cover_bg_path, k=5)
            except Exception as e:
                print(f"WARN: Failed to load cover image {cover_bg_path}: {e}")
                # Fallback to old method
                if cover_img:
                    palette_cache = _extract_palette(cover_img, k=5)

    for idx, slide in enumerate(slides, 1):
        slide_type = slide.get("type", "list")
        title = (slide.get("title") or "").strip()
        body = (slide.get("body") or "").strip()
        items = [str(it).strip() for it in (slide.get("items") or []) if str(it).strip()]

        # STEP 1: Load background
        is_cover = slide.get("is_cover", False) and idx == 1
        bg_cfg = slide.get("bg", {})
        bg_mode = bg_cfg.get("mode", "clean")
        
        if is_cover and cover_img:
            # Cover slide: use pre-loaded cover image
            img = cover_img.copy()
        elif bg_mode == "photo" and bg_cfg.get("path"):
            # Any slide with photo mode: load the specified photo
            photo_path = bg_cfg.get("path")
            if photo_path and Path(photo_path).exists():
                try:
                    # Для внутренних слайдов применяем затемнение для читаемости текста
                    # Для обложки затемнение не применяется (apply_darkening=False)
                    is_inner_slide = not is_cover
                    img = _bg_photo(photo_path, apply_darkening=is_inner_slide)
                    print(f"Loaded photo background for slide {idx}: {photo_path} (darkening={is_inner_slide})")
                except Exception as e:
                    print(f"WARN: Failed to load photo {photo_path} for slide {idx}: {e}")
                    # Fallback to clean background
                    palette_for_slide = bg_cfg.get("palette") or palette_cache
                    img = _bg_from_cfg({"mode": "clean", "palette": palette_for_slide}, palette_cache=palette_cache)
            else:
                print(f"WARN: Photo path missing or invalid for slide {idx}: {photo_path}")
                # Fallback to clean background
                palette_for_slide = bg_cfg.get("palette") or palette_cache
                img = _bg_from_cfg({"mode": "clean", "palette": palette_for_slide}, palette_cache=palette_cache)
        elif bg_mode == "clean":
            # Clean background mode: use palette
            palette_for_slide = bg_cfg.get("palette") or palette_cache
            print(f"DEBUG slide {idx}: bg_cfg={bg_cfg}, palette_from_cfg={bg_cfg.get('palette')}, palette_cache={palette_cache}")
            if not palette_for_slide:
                # Если палитры нет вообще, используем дефолтную тёмную палитру
                palette_for_slide = [(30, 30, 40), (50, 50, 60), (20, 20, 30)]
                print(f"WARN: No palette found for slide {idx}, using default dark palette")
            print(f"Using clean background with palette for slide {idx}: {palette_for_slide[:3] if palette_for_slide else 'None'}")
            # Убедимся, что передаем палитру правильно
            img = _bg_from_cfg({"mode": "clean", "palette": palette_for_slide}, palette_cache=palette_cache)
        else:
            # Other modes (solid, etc.) or default
            img = _bg_from_cfg(bg_cfg, palette_cache=palette_cache)

        # STEP 2: Apply all overlays BEFORE text rendering
        # Важно: сохраняем bg_mode для проверки ниже
        print(f"DEBUG slide {idx}: bg_mode={bg_mode}, is_cover={is_cover}")
        
        if is_cover:
            # Cover: strong gradient + vignette
            img = _apply_bottom_gradient(img, strength=0.65, bottom_ratio=0.5)
            img = _apply_vignette(img, strength=0.18)
        else:
            # Inner slides: для clean backgrounds используем очень слабый градиент или вообще без него
            if bg_mode == "clean":
                # Для clean backgrounds - очень слабый градиент или вообще без затемнения
                # Сначала проверяем контраст БЕЗ затемнения
                text_area = (SAFE, CONTENT_Y, W - SAFE, H - SAFE * 2)
                overlay_strength = _ensure_readability(img, text_area)
                # Применяем минимальное затемнение только если нужно
                if overlay_strength > 0.6:
                    # Только если действительно нужно, применяем очень слабое затемнение
                    img = _apply_bottom_gradient(img, strength=0.25, bottom_ratio=0.25)
                    print(f"Applied minimal gradient for clean background on slide {idx} (strength=0.25)")
                else:
                    print(f"No gradient needed for clean background on slide {idx}, brightness is sufficient")
            else:
                # Для фото - стандартный градиент
                img = _apply_bottom_gradient(img, strength=0.5, bottom_ratio=0.4)
                text_area = (SAFE, CONTENT_Y, W - SAFE, H - SAFE * 2)
                overlay_strength = _ensure_readability(img, text_area)
                if overlay_strength > 0.5:
                    # Reapply stronger gradient if needed (только для фото)
                    max_overlay = 0.8
                    final_strength = min(overlay_strength, max_overlay)
                    img = _apply_bottom_gradient(img, strength=final_strength, bottom_ratio=0.45)

        # STEP 3: Draw header
        d = ImageDraw.Draw(img)
        _header(d, username, f"{idx}/{total}", f_sm)

        # Get accent color and palette for text rendering
        accent_color = _get_accent_color(palette_cache) if palette_cache else (255, 200, 0)
        palette_for_text = palette_cache  # Pass to _draw_rich_line for accent pills

        if idx == 1 and slide_type == "cover":
            # Cover slide: title only, positioned at CONTENT_Y_COVER
            content_y = CONTENT_Y_COVER
            if title:
                # Auto-fit title font, parse markup
                title_font, _ = _fit_text(f_lg_base, title, W - 2 * SAFE, min_size=56, max_size=78)
                title_tokens = _parse_markup(title)
                title_lines = _wrap_rich(title_tokens, title_font, W - 2 * SAFE)
                
                y = content_y
                line_height = int(title_font.getbbox("A")[3] - title_font.getbbox("A")[1] + 10)
                for line_tokens in title_lines[:2]:  # Max 2 lines
                    _, img, d = _draw_rich_line(img, d, line_tokens, SAFE, y, line_height, title_font, accent_color, f_bold, palette=palette_for_text)
                    y += line_height

            # STEP 4: Draw CTA last with pill background
            if total > 1:
                cta_text = "Листай дальше →"
                cta_x = SAFE
                cta_y = H - int(SAFE * 1.2)
                
                # Measure text for pill
                cta_bbox = d.textbbox((cta_x, cta_y), cta_text, font=f_sm)
                cta_w = cta_bbox[2] - cta_bbox[0]
                cta_h = cta_bbox[3] - cta_bbox[1]
                pill_pad = (10, 4)
                pill_x0 = cta_x - pill_pad[0]
                pill_y0 = cta_y + cta_bbox[1] - pill_pad[1]
                pill_x1 = pill_x0 + cta_w + pill_pad[0] * 2
                pill_y1 = pill_y0 + cta_h + pill_pad[1] * 2
                
                # Draw pill background (semi-transparent dark)
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                overlay_draw.rounded_rectangle([(pill_x0, pill_y0), (pill_x1, pill_y1)], 
                                              fill=(0, 0, 0, 110), radius=8)
                img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
                d = ImageDraw.Draw(img)
                _header(d, username, f"{idx}/{total}", f_sm)
                
                # Draw text with slight shadow for extra contrast
                d.text((cta_x + 1, cta_y + 1), cta_text, font=f_sm, fill=(0, 0, 0))
                d.text((cta_x, cta_y), cta_text, font=f_sm, fill=(235, 235, 235))

        elif slide_type == "list":
            # List slide: title + bullets with markup support
            y = CONTENT_Y
            if title:
                # Auto-fit title
                title_font, _ = _fit_text(f_lg_base, title, W - 2 * SAFE, min_size=56, max_size=78)
                title_tokens = _parse_markup(title)
                title_lines = _wrap_rich(title_tokens, title_font, W - 2 * SAFE)
                
                line_height = int(title_font.getbbox("A")[3] - title_font.getbbox("A")[1] + 10)
                for line_tokens in title_lines[:2]:  # Max 2 lines
                    _, img, d = _draw_rich_line(img, d, line_tokens, SAFE, y, line_height, title_font, accent_color, f_bold, palette=palette_for_text)
                    y += line_height
                
                y += 26  # Gap after title (increased from 24)

            if items:
                line_height = int(f_t.getbbox("A")[3] - f_t.getbbox("A")[1] + 12)
                for item_idx, it in enumerate(items):
                    bullet_text = f"- {it}"
                    bullet_tokens = _parse_markup(bullet_text)
                    bullet_lines = _wrap_rich(bullet_tokens, f_t, W - 2 * SAFE)
                    
                    # Limit to 3 lines per bullet, add ellipsis if overflow
                    lines_to_draw = bullet_lines[:3]
                    if len(bullet_lines) > 3:
                        # Add ellipsis to last line if truncated
                        if lines_to_draw and lines_to_draw[-1]:
                            last_line = lines_to_draw[-1]
                            if last_line:
                                last_token_type, last_token_text = last_line[-1] if last_line else ("normal", "")
                                if last_token_text:
                                    last_line[-1] = (last_token_type, last_token_text + "...")
                    
                    for line_tokens in lines_to_draw:
                        if y + line_height > H - SAFE * 2:
                            break
                        _, img, d = _draw_rich_line(img, d, line_tokens, SAFE, y, line_height, f_t, accent_color, f_bold, palette=palette_for_text)
                        y += line_height
                    
                    y += 8  # Spacing between bullets

        else:
            # Text slide: title + body
            y = CONTENT_Y
            if title:
                title_font, _ = _fit_text(f_lg_base, title, W - 2 * SAFE, min_size=56, max_size=78)
                title_tokens = _parse_markup(title)
                title_lines = _wrap_rich(title_tokens, title_font, W - 2 * SAFE)
                
                line_height = int(title_font.getbbox("A")[3] - title_font.getbbox("A")[1] + 10)
                for line_tokens in title_lines[:2]:
                    _, img, d = _draw_rich_line(img, d, line_tokens, SAFE, y, line_height, title_font, accent_color, f_bold, palette=palette_for_text)
                    y += line_height
                
                y += 24
            
            if body:
                body_tokens = _parse_markup(body)
                body_lines = _wrap_rich(body_tokens, f_t, W - 2 * SAFE)
                line_height = int(f_t.getbbox("A")[3] - f_t.getbbox("A")[1] + 12)
                for line_tokens in body_lines:
                    _, img, d = _draw_rich_line(img, d, line_tokens, SAFE, y, line_height, f_t, accent_color, f_bold, palette=palette_for_text)
                    y += line_height

        img.save(out / f"slide_{idx:02}.png", optimize=True)

    return out
