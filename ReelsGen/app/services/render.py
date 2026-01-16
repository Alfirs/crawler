import math
import os
import random
import re
import tempfile
from io import BytesIO
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageChops

from . import text_overlay

# Basic helpers

APP_DIR = os.path.dirname(os.path.dirname(__file__))
FONTS_DIR = os.path.join(APP_DIR, "assets", "fonts")

ACCENT_COLOR = (92, 204, 146, 255)
DEFAULT_TEXT_COLOR = (255, 255, 255, 255)
AUTO_HIGHLIGHT_PHRASES = [
    "что делать",
    "как исправить",
    "решение",
    "совет",
]
HEADING_KEYWORDS = [
    "ошибка",
    "проблема",
    "совет",
    "решение",
    "причина",
]
BODY_HIGHLIGHT_KEYWORDS = [
    "kpi",
    "utm",
    "ctr",
    "roi",
    "cpa",
    "cpl",
    "анализ",
    "аналитика",
    "оптимизац",
]

def is_light_image(img: Image.Image) -> bool:
    """Rough brightness check (mean luma > 0.7 = light)."""
    gray = img.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    mean = sum(i * v for i, v in enumerate(hist)) / total
    return mean / 255.0 > 0.7


def _cover_fit(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """Scale and crop image to fill target size without distortion."""
    w, h = img.size
    tw, th = target_size
    ratio = max(tw / w, th / h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _avg_luma(img: Image.Image) -> float:
    """Average brightness 0..1."""
    gray = img.convert("L")
    hist = gray.histogram()
    total = sum(hist)
    mean = sum(i * v for i, v in enumerate(hist)) / total
    return mean / 255.0


# Core renderer


TEMPLATES = {
    "user_photo": {"use_upload": True},
    "green_plain": {"bg_fill": (46, 125, 50)},
    "green_pattern": {"bg_fill": (46, 125, 50), "pattern": "squiggle"},
}


def _draw_squiggle_pattern(img: Image.Image) -> Image.Image:
    """Overlay soft squiggle lines on top of the base color."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = img.size
    amplitude = max(10, int(height * 0.05))
    alpha = int(255 * 0.08)
    color = (255, 255, 255, alpha)
    step = max(12, width // 48)

    for idx in range(3):
        baseline = height * (0.2 + idx * 0.25)
        phase = random.random() * math.pi * 2
        freq = random.uniform(1.5, 2.5)
        points = []
        for x in range(0, width + step, step):
            radians = (x / max(1, width)) * math.pi * freq + phase
            y = baseline + math.sin(radians) * amplitude
            points.append((x, y))
        draw.line(points, fill=color, width=6, joint="curve")

    return Image.alpha_composite(img, overlay)


def build_bg_from_template(
    name: str,
    upload_path: Optional[str] = None,
    size: Tuple[int, int] = (1080, 1350),
) -> Tuple[Optional[str], Optional[Tuple[int, int, int]]]:
    """
    Resolve template into either a background image path or a flat fill color.

    Returns:
        Tuple[bg_image_path, bg_fill]
    """
    template = TEMPLATES.get(name)
    if not template:
        raise ValueError(f"Unknown background template '{name}'")

    if template.get("use_upload"):
        if not upload_path or not os.path.exists(upload_path):
            raise ValueError("Template requires uploaded image")
        return upload_path, None

    bg_fill = template.get("bg_fill", (255, 255, 255))
    pattern = template.get("pattern")

    if pattern == "squiggle":
        img = Image.new("RGBA", size, bg_fill + (255,))
        img = _draw_squiggle_pattern(img)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        try:
            img.convert("RGB").save(tmp.name, "PNG")
            temp_path = tmp.name
        finally:
            tmp.close()
        return temp_path, None

    return None, bg_fill


def render_slide_with_bg(
    text: str,
    bg_image_path: Optional[str],
    bg_fill: Optional[Tuple[int, int, int]] = None,
    size: Tuple[int, int] = (1080, 1350),
    darken: bool = True,
    safe_pad: int = 64,
    watermark: Optional[str] = None,
    mode: str = "content",
    handle: Optional[str] = None,
    page_index: Optional[int] = None,
    page_total: Optional[int] = None,
    force_fallback: bool = False,
) -> Image.Image:
    """Render one slide with optional background image or color fill + text (cover/content layouts)."""
    img: Image.Image
    if bg_image_path and os.path.exists(bg_image_path):
        with Image.open(bg_image_path) as src:
            img = _cover_fit(src.convert("RGB"), size)
    else:
        bg_color = bg_fill or (255, 255, 255)
        img = Image.new("RGB", size, bg_color)

    if darken and is_light_image(img):
        overlay = Image.new("RGBA", size, (0, 0, 0, int(255 * 0.3)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    t = str(text or "").strip()
    handle_text = (handle or "").strip() or None
    reserved_top = _estimate_handle_offset(size, safe_pad) if handle_text else 0
    cta_reserve = _estimate_cta_height(size, safe_pad)
    heading_candidate, body_candidate = _split_heading_body(t)
    heading_candidate, body_candidate = _auto_style_sections(heading_candidate, body_candidate)
    content_candidates = [
        {"text": t},
        {"title": t},
        {"content": t},
        {"blocks": [{"type": "text", "text": t}]},
        {"blocks": [{"type": "title", "text": t}]},
    ]
    if body_candidate:
        content_candidates.insert(
            0,
            {
                "title": heading_candidate or t,
                "body": body_candidate,
            },
        )

    slide = None
    base_rgb = img.convert("RGB")
    if not force_fallback:
        for candidate in content_candidates:
            for variant in range(3):
                try:
                    if variant == 0:
                        slide_try = text_overlay.render_slide(img, None, candidate, mode=mode)
                    elif variant == 1:
                        slide_try = text_overlay.render_slide(img, candidate, mode=mode)
                    else:
                        slide_try = text_overlay.render_slide(candidate, img, mode=mode)
                except TypeError:
                    continue
                except ValueError:
                    continue

                if not isinstance(slide_try, Image.Image):
                    continue

                diff = ImageChops.difference(
                    slide_try.convert("RGB"), base_rgb
                ).getbbox()
                if diff is not None:
                    slide = slide_try
                    break
            if slide is not None:
                break

    if slide is None:
        top_offset = reserved_top if handle_text else 0
        slide = _fallback_draw_text(
            base_rgb.copy(),
            t,
            safe_pad,
            mode=mode,
            top_offset=top_offset,
            bottom_reserve=cta_reserve,
        )

    if handle_text:
        slide = _draw_handle(slide, handle_text, pad=safe_pad)

    if mode in {"cover", "content"}:
        slide = _draw_cta(slide, pad=safe_pad)
        slide = _draw_arrow(slide, pad=safe_pad)

    if page_index is not None and page_total is not None:
        slide = _draw_page_counter(slide, page_index, page_total, pad=safe_pad)

    if watermark:
        slide = _apply_watermark(slide, watermark)
    return slide


# Backward-compatibility helpers

CANVAS_SIZE = (1080, 1350)


def image_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = BytesIO()
    img.save(buffer, fmt)
    return buffer.getvalue()


def _make_base_bg(
    background: Optional[object],
    size: Tuple[int, int] = CANVAS_SIZE,
) -> Image.Image:
    if isinstance(background, Image.Image):
        img = background.copy()
    elif isinstance(background, str) and os.path.exists(background):
        img = Image.open(background).convert("RGB")
    elif isinstance(background, tuple) and len(background) == 3:
        img = Image.new("RGB", size, background)
    else:
        img = Image.new("RGB", size, (255, 255, 255))
    return _cover_fit(img, size) if img.size != size else img.convert("RGB")


def render_cover(
    title: str,
    background: Optional[object] = None,
    size: Tuple[int, int] = CANVAS_SIZE,
    darken: bool = True,
    safe_pad: int = 64,
    watermark: Optional[str] = None,
) -> Image.Image:
    img = _make_base_bg(background, size)
    if darken and is_light_image(img):
        overlay = Image.new("RGBA", size, (0, 0, 0, int(255 * 0.35)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    return text_overlay.render_slide(
        text=title,
        bg=img,
        safe_pad=safe_pad,
        watermark=watermark,
    )


def render_content(
    texts: List[str],
    background: Optional[object] = None,
    size: Tuple[int, int] = CANVAS_SIZE,
    darken: bool = True,
    safe_pad: int = 64,
    watermark: Optional[str] = None,
) -> List[Image.Image]:
    slides = []
    for text in texts:
        img = _make_base_bg(background, size)
        if darken and is_light_image(img):
            overlay = Image.new("RGBA", size, (0, 0, 0, int(255 * 0.25)))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        slide = text_overlay.render_slide(
            text=text,
            bg=img,
            safe_pad=safe_pad,
            watermark=watermark,
        )
        slides.append(slide)
    return slides


# Export API

__all__ = [
    "render_slide_with_bg",
    "build_bg_from_template",
    "_cover_fit",
    "_avg_luma",
    "is_light_image",
    "TEMPLATES",
    "render_cover",
    "render_content",
    "image_to_bytes",
    "CANVAS_SIZE",
    "_fallback_draw_text",
    "_draw_handle",
    "_draw_page_counter",
    "_draw_cta",
    "_draw_arrow",
]


def _apply_watermark(img: Image.Image, text: str) -> Image.Image:
    """Draw a simple watermark in the lower-right corner."""
    text = (text or "").strip()
    if not text:
        return img

    base = img.convert("RGB")
    draw = ImageDraw.Draw(base)

    font_size = max(12, int(base.height * 0.02))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = right - left, bottom - top
    else:
        text_w, text_h = font.getsize(text)

    margin = max(8, font_size)
    x = max(margin, base.width - text_w - margin)
    y = max(margin, base.height - text_h - margin)

    # shadow
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0))
    # main text
    draw.text((x, y), text, font=font, fill=(255, 255, 255))
    return base


def _font_candidates(weight: str = "regular") -> List[str]:
    font_names = []
    if weight == "bold":
        font_names.extend(
            [
                "Inter-Bold.ttf",
                "Manrope-Bold.ttf",
                "DejaVuSans-Bold.ttf",
                "arialbd.ttf",
            ]
        )
    else:
        font_names.extend(
            [
                "Inter-Regular.ttf",
                "Manrope-Regular.ttf",
                "DejaVuSans.ttf",
                "arial.ttf",
            ]
        )
    resolved = []
    for name in font_names:
        resolved.append(os.path.join(FONTS_DIR, name))
        resolved.append(name)
    return resolved


def _load_overlay_font(size: int, weight: str = "regular") -> ImageFont.ImageFont:
    font_loader = getattr(text_overlay, "load_font", None)
    candidates = _font_candidates(weight)
    if callable(font_loader):
        try:
            return font_loader(candidates, size)
        except Exception:
            pass
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _line_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ag") if hasattr(font, "getbbox") else None
    if bbox:
        return max(1, bbox[3] - bbox[1])
    return max(1, font.getsize("Ag")[1])


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    if hasattr(draw, "textbbox"):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    return font.getsize(text)


def _parse_styled_text(raw_text: str) -> Tuple[str, List[dict]]:
    """Return plain text and style flags per character."""
    plain_chars: List[str] = []
    style_flags: List[dict] = []
    accent = False
    underline = False
    escape = False

    for ch in raw_text or "":
        if escape:
            plain_chars.append(ch)
            style_flags.append({"accent": accent, "underline": underline})
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == "*":
            accent = not accent
            continue
        if ch == "_":
            underline = not underline
            continue
        plain_chars.append(ch)
        style_flags.append({"accent": accent, "underline": underline})

    return "".join(plain_chars), style_flags


def _build_segments_for_lines(
    lines: List[str],
    plain_text: str,
    style_flags: List[dict],
) -> List[List[dict]]:
    segments_per_line: List[List[dict]] = []
    search_pos = 0
    for line in lines:
        if not line:
            segments_per_line.append([])
            continue
        idx = plain_text.find(line, search_pos)
        if idx == -1:
            idx = search_pos
        end = min(len(plain_text), idx + len(line))
        if end <= idx:
            segments_per_line.append([{"text": line, "accent": False, "underline": False}])
            search_pos = end
            continue
        segments: List[dict] = []
        for char_idx in range(idx, end):
            ch = plain_text[char_idx]
            style = style_flags[char_idx] if char_idx < len(style_flags) else {"accent": False, "underline": False}
            if segments and segments[-1]["accent"] == style["accent"] and segments[-1]["underline"] == style["underline"]:
                segments[-1]["text"] += ch
            else:
                segments.append({"text": ch, "accent": style["accent"], "underline": style["underline"]})
        segments_per_line.append(segments)
        search_pos = end
    return segments_per_line


def _calc_total_height(lines: List[str], font: ImageFont.ImageFont, spacing: float) -> int:
    if not lines:
        return 0
    line_height = _line_height(font)
    total = 0
    for idx, _ in enumerate(lines):
        total += line_height
        if idx < len(lines) - 1:
            total += int(line_height * (spacing - 1))
    return total


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
) -> Tuple[int, int, int, int]:
    textbbox = getattr(draw, "textbbox", None)
    if callable(textbbox):
        return textbbox(xy, text, font=font)
    width, height = font.getsize(text)
    x, y = xy
    return (x, y, x + width, y + height)


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    words = text.split()
    if not words:
        return []

    def _measure(value: str) -> int:
        bbox = _text_bbox(draw, (0, 0), value, font)
        return bbox[2] - bbox[0]

    lines: List[str] = []
    current: List[str] = []
    for word in words:
        trial = " ".join(current + [word]).strip()
        if not trial:
            continue
        if _measure(trial) <= max_width or not current:
            current.append(word)
            continue
        lines.append(" ".join(current))
        current = [word]
        if _measure(word) > max_width:
            chunked: List[str] = []
            remaining = word
            while remaining:
                for idx in range(len(remaining), 0, -1):
                    segment = remaining[:idx]
                    if _measure(segment) <= max_width or idx == 1:
                        chunked.append(segment)
                        remaining = remaining[idx:]
                        break
            if chunked:
                lines.extend(chunked[:-1])
                current = [chunked[-1]]
            else:
                current = []
    if current:
        lines.append(" ".join(current))
    return [ln.strip() for ln in lines if ln.strip()]


def _split_body_lines(text: str) -> List[str]:
    normalized = (text or "").replace("\r\n", "\n")
    parts: List[str] = []
    for raw_line in normalized.split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        sentence_chunks = re.split(r"(?<=[.!?])\s+(?=[A-ZА-Я0-9])", raw_line)
        working = []
        for chunk in sentence_chunks:
            chunk = chunk.strip(" ;")
            if not chunk:
                continue
            if ";" in chunk:
                working.extend([seg.strip() for seg in chunk.split(";") if seg.strip()])
            else:
                working.append(chunk.strip())
        parts.extend(working or [raw_line])
    return parts


def _split_heading_body(text: str) -> Tuple[str, str]:
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return "", ""

    def _cleanup(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    heading = ""
    body = ""

    if "\n\n" in normalized:
        heading, body = normalized.split("\n\n", 1)
    elif "\n" in normalized:
        heading, body = normalized.split("\n", 1)
    else:
        keyword_match = re.search(
            r"(Решение|Вывод|Совет|Важно|Итог|Ответ)\s*(?:[:—-]|$)",
            normalized,
            flags=re.IGNORECASE,
        )
        if keyword_match and keyword_match.start() > 0:
            heading = normalized[: keyword_match.start()]
            body = normalized[keyword_match.start() :].strip()
        else:
            sentences = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)
            if len(sentences) == 2:
                first, rest = sentences
                if len(first) <= 160 or len(first) < len(normalized) * 0.6:
                    heading, body = first, rest
            if not body and ":" in normalized:
                idx = normalized.find(":")
                if idx > 0:
                    heading = normalized[: idx + 1]
                    body = normalized[idx + 1 :]

    if not heading:
        heading = normalized
        body = ""

    heading_clean = _cleanup(heading)
    body_clean = _cleanup(body)
    return heading_clean, body_clean


def _wrap_section(text: str, start: int, end: int, marker: str) -> str:
    if start < 0 or end <= start:
        return text
    return text[:start] + marker + text[start:end] + marker + text[end:]


def _auto_style_sections(heading: str, body: str) -> Tuple[str, str]:
    heading = heading or ""
    body = body or ""
    heading_lower = heading.lower()
    stripped = heading.lstrip()
    offset = len(heading) - len(stripped)
    keyword_match = None
    for keyword in HEADING_KEYWORDS:
        if stripped.lower().startswith(keyword):
            keyword_match = (offset, offset + len(keyword))
            break
    if keyword_match:
        heading = _wrap_section(heading, keyword_match[0], keyword_match[1], "*")
    else:
        for separator in (":", "—", "-"):
            if separator in heading:
                idx = heading.index(separator)
                start = heading.rfind(" ", 0, idx)
                start = offset if start == -1 else start + 1
                if start < idx:
                    heading = _wrap_section(heading, start, idx, "*")
                break

    body_lower = body.lower()
    for phrase in AUTO_HIGHLIGHT_PHRASES:
        pos = body_lower.find(phrase)
        if pos >= 0:
            end = pos + len(phrase)
            body = _wrap_section(body, pos, end, "_")
            break
    return heading, body


_NUMERIC_BULLET_RE = re.compile(r"^\s*(?:\d+[\).\:-]|[\(\[]\d+[\)\]]|№\s*\d+)\s*")


def _extract_bullets(body: str) -> List[dict]:
    markers = ("-", "—", "–", "→", "•", "*")
    bullets: List[dict] = []
    for segment in _split_body_lines(body):
        candidate = segment.lstrip()
        cleaned = candidate
        use_symbol = True
        for marker in markers:
            if candidate.startswith(marker):
                cleaned = candidate[len(marker) :].strip()
                break
        else:
            match = _NUMERIC_BULLET_RE.match(candidate)
            if match:
                cleaned = candidate.strip()
                use_symbol = False
            else:
                use_symbol = False

        cleaned = cleaned.strip()
        if cleaned:
            bullets.append({"text": cleaned, "use_symbol": use_symbol})
    return bullets


def _maybe_draw_plate(
    base: Image.Image,
    draw: ImageDraw.ImageDraw,
    instructions: List[dict],
    threshold: float,
    alpha: float,
    pad: int,
) -> None:
    if not instructions:
        return
    width, height = base.size
    bounds = [width, height, 0, 0]
    for inst in instructions:
        bbox = _text_bbox(draw, inst["xy"], inst["text"], inst["font"])
        bounds[0] = min(bounds[0], bbox[0])
        bounds[1] = min(bounds[1], bbox[1])
        bounds[2] = max(bounds[2], bbox[2])
        bounds[3] = max(bounds[3], bbox[3])
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return
    expanded = [
        max(0, bounds[0] - pad),
        max(0, bounds[1] - pad),
        min(width, bounds[2] + pad),
        min(height, bounds[3] + pad),
    ]
    region = base.crop(tuple(expanded))
    if _avg_luma(region) <= threshold:
        return
    draw.rounded_rectangle(
        expanded,
        radius=int(min(width, height) * 0.04),
        fill=(0, 0, 0, int(255 * alpha)),
    )


def _build_cover_instructions(
    draw: ImageDraw.ImageDraw,
    heading_text: str,
    sub_text: str,
    safe_pad: int,
    width: int,
    height: int,
    bottom_reserve: int = 0,
) -> List[dict]:
    heading_text = (heading_text or "").strip()
    sub_text = (sub_text or "").strip()
    if not heading_text:
        heading_text = sub_text
        sub_text = ""

    min_dim = min(width, height)
    max_width = max(10, width - safe_pad * 2)
    area_top = max(safe_pad, int(height * 0.52))
    area_bottom = max(area_top + 40, height - safe_pad - bottom_reserve)
    area_height = max(40, area_bottom - area_top)

    font_size = max(32, int(min_dim * 0.1))
    line_spacing = 1.16
    heading_plain, heading_styles = _parse_styled_text(heading_text)

    while font_size >= 22:
        heading_font = _load_overlay_font(font_size, weight="bold")
        heading_lines = _wrap_text(draw, heading_plain, heading_font, max_width)
        if not heading_lines:
            heading_lines = [heading_plain]
        total = _calc_total_height(heading_lines, heading_font, line_spacing)
        if total <= area_height or font_size <= 24:
            break
        font_size -= 2

    max_heading_lines = 3
    if len(heading_lines) > max_heading_lines:
        overflow = " ".join(heading_lines[max_heading_lines - 1 :]).strip()
        heading_lines = heading_lines[: max_heading_lines - 1]
        sub_text = f"{overflow} {sub_text}".strip()

    heading_font = _load_overlay_font(font_size, weight="bold")
    heading_segments = _build_segments_for_lines(heading_lines, heading_plain, heading_styles)
    line_height = _line_height(heading_font)
    total = _calc_total_height(heading_lines, heading_font, line_spacing)
    y_start = max(area_top, area_bottom - total)
    instructions: List[dict] = []
    y = y_start
    for idx, line in enumerate(heading_lines):
        instructions.append(
            {
                "text": line,
                "font": heading_font,
                "xy": (safe_pad, y),
                "segments": heading_segments[idx] if idx < len(heading_segments) else None,
                "line_height": line_height,
            }
        )
        y += int(line_height * line_spacing)

    if sub_text:
        body_font_size = max(20, int(min_dim * 0.05))
        body_font = _load_overlay_font(body_font_size)
        body_line_spacing = 1.18
        body_plain, body_styles = _parse_styled_text(sub_text)
        body_lines = _wrap_text(draw, body_plain, body_font, max_width)
        body_segments = _build_segments_for_lines(body_lines, body_plain, body_styles)
        body_line_height = _line_height(body_font)
        y = max(y, area_bottom - _calc_total_height(body_lines, body_font, body_line_spacing))
        for idx, line in enumerate(body_lines):
            instructions.append(
                {
                    "text": line,
                    "font": body_font,
                    "xy": (safe_pad, y),
                    "segments": body_segments[idx] if idx < len(body_segments) else None,
                    "line_height": body_line_height,
                }
            )
            y += int(body_line_height * body_line_spacing)

    return instructions


def _build_content_instructions(
    draw: ImageDraw.ImageDraw,
    text: str,
    safe_pad: int,
    width: int,
    height: int,
    top_offset: int = 0,
    bottom_reserve: int = 0,
) -> List[dict]:
    max_width = max(10, width - safe_pad * 2)
    min_dim = min(width, height)
    heading_text, body_text = _split_heading_body(text)
    heading_text, body_text = _auto_style_sections(heading_text, body_text)
    if not heading_text and body_text:
        lines_guess = _split_body_lines(body_text)
        if lines_guess:
            heading_text = lines_guess[0]
            body_text = " ".join(lines_guess[1:]).strip()
    instructions: List[dict] = []

    offset = max(0, top_offset)
    top_pad = safe_pad + offset

    reserve = max(0, bottom_reserve)
    content_space = max(200, height - top_pad - safe_pad - reserve)
    heading_top = top_pad + int(min_dim * 0.03)
    heading_space = max(int(content_space * 0.36), int(min_dim * 0.26))
    heading_area_bottom = min(height - safe_pad - reserve - int(min_dim * 0.06), heading_top + heading_space)
    heading_font_size = max(26, int(min_dim * 0.078))
    line_spacing = 1.08
    heading_plain, heading_styles = _parse_styled_text(heading_text or "")
    heading_lines: List[str] = []

    while heading_font_size >= 18:
        heading_font = _load_overlay_font(heading_font_size, weight="bold")
        heading_lines = _wrap_text(draw, heading_plain, heading_font, max_width)
        if not heading_lines and heading_plain:
            heading_lines = [heading_plain]
        total = _calc_total_height(heading_lines, heading_font, line_spacing)
        available = max(40, heading_area_bottom - heading_top)
        if total <= available or heading_font_size <= 20:
            break
        heading_font_size -= 1

    heading_font = _load_overlay_font(heading_font_size, weight="bold")
    heading_line_height = _line_height(heading_font)
    heading_area_height = max(heading_area_bottom - heading_top, heading_line_height)
    total = _calc_total_height(heading_lines, heading_font, line_spacing)
    if heading_lines:
        y = heading_top + max(0, (heading_area_height - total) // 2)
        heading_segments = _build_segments_for_lines(heading_lines, heading_plain, heading_styles)
        for line in heading_lines:
            instructions.append(
                {
                    "text": line,
                    "font": heading_font,
                    "xy": (safe_pad, y),
                    "segments": heading_segments.pop(0) if heading_segments else None,
                    "line_height": heading_line_height,
                }
            )
            y += int(heading_line_height * line_spacing)
    else:
        y = heading_top

    body_area_top = max(y + int(min_dim * 0.035), heading_area_bottom)
    body_area_bottom = min(
        height - safe_pad - reserve,
        body_area_top + max(int(content_space * 0.46), int(min_dim * 0.35)),
    )
    if body_area_bottom <= body_area_top:
        body_area_bottom = min(height - safe_pad, body_area_top + heading_area_height)
    body_available = max(30, body_area_bottom - body_area_top)
    body_font_size = max(17, int(min_dim * 0.042))
    body_line_spacing = 1.28
    body_font = _load_overlay_font(body_font_size)

    bullets = _extract_bullets(body_text)
    wrapped_blocks: List[dict] = []
    bullet_indent = max(22, int(min_dim * 0.04))

    if bullets:
        while body_font_size >= 16:
            body_font = _load_overlay_font(body_font_size)
            line_height = _line_height(body_font)
            wrapped_blocks = []
            total = 0
            for bullet in bullets:
                indent = bullet_indent if bullet["use_symbol"] else 0
                plain, styles = _parse_styled_text(bullet["text"])
                lines = _wrap_text(draw, plain, body_font, max(10, max_width - indent))
                if not lines:
                    lines = [plain]
                segments = _build_segments_for_lines(lines, plain, styles)
                wrapped_blocks.append({"lines": lines, "use_symbol": bullet["use_symbol"], "segments": segments})
                total += int(len(lines) * line_height * body_line_spacing)
                total += int(line_height * 0.35)
            if total <= body_available or body_font_size <= 16:
                break
            body_font_size -= 1
        y = body_area_top
        line_height = _line_height(body_font)
        for idx, block in enumerate(wrapped_blocks):
            lines = block["lines"]
            use_symbol = block["use_symbol"]
            indent = bullet_indent if use_symbol else 0
            segments = block.get("segments") or [[] for _ in lines]
            for line_idx, line in enumerate(lines):
                if line_idx == 0 and use_symbol:
                    instructions.append(
                        {
                            "text": "→",
                            "font": body_font,
                            "xy": (safe_pad, y),
                        }
                    )
                instructions.append(
                    {
                        "text": line,
                        "font": body_font,
                        "xy": (safe_pad + indent, y),
                        "segments": segments[line_idx] if line_idx < len(segments) else None,
                        "line_height": line_height,
                    }
                )
                y += int(line_height * body_line_spacing)
            if idx < len(wrapped_blocks) - 1:
                y += int(line_height * 0.35)
    else:
        paragraphs = [
            p.strip()
            for p in (body_text or "").replace("\r\n", "\n").split("\n\n")
            if p.strip()
        ]
        if not paragraphs:
            paragraphs = _split_body_lines(body_text)
        while body_font_size >= 16 and paragraphs:
            body_font = _load_overlay_font(body_font_size)
            line_height = _line_height(body_font)
            wrapped_blocks = []
            total = 0
            for para in paragraphs:
                plain, styles = _parse_styled_text(para)
                lines = _wrap_text(draw, plain, body_font, max_width)
                if not lines:
                    continue
                segments = _build_segments_for_lines(lines, plain, styles)
                wrapped_blocks.append({"lines": lines, "segments": segments})
                total += int(len(lines) * line_height * body_line_spacing)
                total += int(line_height * 0.42)
            if total <= body_available or body_font_size <= 18:
                break
            body_font_size -= 1
        y = body_area_top
        if paragraphs:
            line_height = _line_height(body_font)
            for idx, block in enumerate(wrapped_blocks):
                lines = block["lines"]
                segments = block.get("segments") or [[] for _ in lines]
                for line_idx, line in enumerate(lines):
                    instructions.append(
                        {
                            "text": line,
                            "font": body_font,
                            "xy": (safe_pad, y),
                            "segments": segments[line_idx] if line_idx < len(segments) else None,
                            "line_height": line_height,
                        }
                    )
                    y += int(line_height * body_line_spacing)
                if idx < len(wrapped_blocks) - 1:
                    y += int(line_height * 0.42)

    return instructions


def _fallback_draw_text(
    img: Image.Image,
    text: str,
    safe_pad: int = 64,
    mode: str = "content",
    top_offset: int = 0,
    bottom_reserve: int = 0,
) -> Image.Image:
    """Draw text manually if text_overlay rendering failed."""
    text = (text or "").strip()
    if not text:
        return img

    base = img.convert("RGBA").copy()
    draw = ImageDraw.Draw(base, "RGBA")
    width, height = base.size

    if mode == "cover":
        cover_heading, cover_body = _split_heading_body(text)
        instructions = _build_cover_instructions(
            draw,
            cover_heading or text,
            cover_body,
            safe_pad,
            width,
            height,
            bottom_reserve=bottom_reserve,
        )
        threshold = 0.6
        alpha = 0.38
    else:
        instructions = _build_content_instructions(
            draw,
            text,
            safe_pad,
            width,
            height,
            top_offset=top_offset,
            bottom_reserve=bottom_reserve,
        )
        threshold = 0.7
        alpha = 0.3

    if not instructions:
        return base.convert("RGB")

    plate_pad = max(16, safe_pad // 2)
    _maybe_draw_plate(base, draw, instructions, threshold, alpha, plate_pad)

    base_is_light = is_light_image(base)
    text_fill = (34, 42, 48, 255) if (mode == "content" and base_is_light) else DEFAULT_TEXT_COLOR
    for inst in instructions:
        segments = inst.get("segments")
        line_height = inst.get("line_height") or _line_height(inst["font"])
        default_fill = inst.get("fill", text_fill)
        if segments:
            cursor_x, cursor_y = inst["xy"]
            for segment in segments:
                seg_text = segment.get("text")
                if not seg_text:
                    continue
                seg_fill = ACCENT_COLOR if segment.get("accent") else default_fill
                draw.text(
                    (cursor_x, cursor_y),
                    seg_text,
                    font=inst["font"],
                    fill=seg_fill,
                )
                seg_width, _ = _measure_text(draw, seg_text, inst["font"])
                if segment.get("underline"):
                    underline_y = cursor_y + line_height - max(2, line_height // 12)
                    draw.line(
                        (cursor_x, underline_y, cursor_x + seg_width, underline_y),
                        fill=seg_fill,
                        width=max(2, line_height // 14),
                    )
                cursor_x += seg_width
        else:
            draw.text(
                inst["xy"],
                inst["text"],
                font=inst["font"],
                fill=default_fill,
            )

    print("[overlay] fallback used")
    return base.convert("RGB")


def _estimate_handle_offset(size: Tuple[int, int], pad: int) -> int:
    min_dim = min(size)
    font_size = max(16, int(min_dim * 0.035))
    font = _load_overlay_font(font_size)
    line_height = _line_height(font)
    extra_gap = max(14, font_size // 2)
    return line_height + extra_gap


def _estimate_cta_height(size: Tuple[int, int], pad: int, text: str = "Листай дальше") -> int:
    min_dim = min(size)
    font_size = max(18, int(min_dim * 0.04))
    font = _load_overlay_font(font_size)
    line_height = _line_height(font)
    inner_pad = max(10, font_size // 3)
    # include extra breathing room above CTA so body doesn't collide
    return line_height + inner_pad * 2 + pad + int(min_dim * 0.015)


def _contrast_text_color(
    base: Image.Image,
    box: Tuple[int, int, int, int],
    light: Tuple[int, int, int, int],
    dark: Tuple[int, int, int, int],
) -> Tuple[int, int, int, int]:
    width, height = base.size
    x0, y0, x1, y1 = box
    x0 = max(0, min(width, x0))
    y0 = max(0, min(height, y0))
    x1 = max(0, min(width, x1))
    y1 = max(0, min(height, y1))
    if x1 <= x0 or y1 <= y0:
        return light
    region = base.crop((x0, y0, x1, y1))
    return dark if _avg_luma(region) > 0.6 else light


def _draw_handle(img: Image.Image, text: Optional[str], pad: int = 24) -> Image.Image:
    text = (text or "").strip()
    if not text:
        return img
    base = img.convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")
    min_dim = min(base.size)
    font_size = max(16, int(min_dim * 0.032))
    font = _load_overlay_font(font_size)
    bbox = _text_bbox(draw, (pad, pad), text, font)
    color = _contrast_text_color(
        base,
        (pad, pad, min(base.width, bbox[2] + pad), min(base.height, bbox[3] + pad)),
        (234, 234, 234, 255),
        (32, 32, 32, 255),
    )
    draw.text((pad, pad), text, font=font, fill=color)
    return base.convert("RGB")


def _draw_page_counter(
    img: Image.Image,
    index: int,
    total: int,
    pad: int = 24,
) -> Image.Image:
    try:
        index_val = int(index)
        total_val = int(total)
    except (TypeError, ValueError):
        return img
    if total_val <= 0:
        return img
    index = max(1, index_val)
    total = max(index, total_val)
    label = f"{index}/{total}"
    base = img.convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")
    min_dim = min(base.size)
    font_size = max(16, int(min_dim * 0.035))
    font = _load_overlay_font(font_size)
    bbox = _text_bbox(draw, (0, 0), label, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = max(pad, base.width - pad - text_w)
    y = pad
    color = _contrast_text_color(
        base,
        (x, y, min(base.width, x + text_w), min(base.height, y + text_h)),
        (234, 234, 234, 255),
        (32, 32, 32, 255),
    )
    draw.text((x, y), label, font=font, fill=color)
    return base.convert("RGB")


def _draw_cta(img: Image.Image, text: str = "Листай дальше", pad: int = 24) -> Image.Image:
    text = (text or "").strip()
    if not text:
        return img
    base = img.convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")
    min_dim = min(base.size)
    font_size = max(18, int(min_dim * 0.04))
    font = _load_overlay_font(font_size)
    bbox = _text_bbox(draw, (0, 0), text, font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    y = max(pad, base.height - pad - text_h)
    color = _contrast_text_color(
        base,
        (pad, y, min(base.width, pad + text_w), min(base.height, y + text_h)),
        (234, 234, 234, 255),
        (80, 80, 80, 255),
    )
    draw.text((pad, y), text, font=font, fill=color)
    return base.convert("RGB")


def _draw_arrow(img: Image.Image, pad: int = 24) -> Image.Image:
    base = img.convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")
    min_dim = min(base.size)
    font_size = max(32, int(min_dim * 0.07))
    length = max(60, int(min_dim * 0.09))
    stroke = max(3, font_size // 8)
    x_end = base.width - pad
    x_start = x_end - length
    cta_font = _load_overlay_font(max(18, int(min_dim * 0.04)))
    cta_height = _line_height(cta_font)
    cta_top = max(pad, base.height - pad - cta_height)
    baseline = cta_top + cta_height - max(2, stroke // 2)
    y = baseline
    color = _contrast_text_color(
        base,
        (x_start, y - stroke * 4, x_end, y + stroke * 4),
        (234, 234, 234, 255),
        (60, 60, 60, 255),
    )
    draw.line((x_start, y, x_end, y), fill=color, width=stroke)
    draw.line((x_end - stroke * 2, y - stroke * 2, x_end, y), fill=color, width=stroke)
    draw.line((x_end - stroke * 2, y + stroke * 2, x_end, y), fill=color, width=stroke)
    return base.convert("RGB")
