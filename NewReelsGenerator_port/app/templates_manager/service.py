from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional
from uuid import uuid4

from fastapi import UploadFile

from app.services.text_gen import generate_carousel_text
from app.services.image_gen import generate_image
from app.carousel.core import render_carousel
from .models import TemplateMetadata

USE_AITUNNEL_BG = False


def _detect_mode(idea: str) -> str:
    """Detect mode from idea text: 'advice' if contains advice markers, otherwise 'mistakes'."""
    idea_low = idea.lower()
    advice_markers = (
        "лайфхак",
        "лайфхаки",
        "совет",
        "советы",
        "как сделать",
        "работающий способ",
        "что делать",
        "план",
        "алгоритм",
        "пошагово",
    )
    for marker in advice_markers:
        if marker in idea_low:
            return "advice"
    return "mistakes"


def _clean_text(s: str) -> str:
    """Clean text from unwanted characters and symbols."""
    if not s:
        return ""
    s = s.replace("\t", " ")
    s = s.replace("\u00a0", " ")
    s = s.replace("•", "-")
    s = s.replace("‣", "-")
    # Remove non-printable characters
    s = "".join(ch for ch in s if ch.isprintable() or ch == "\n")
    return s.strip()


class TemplateService:
    """Filesystem-based storage for carousel templates and generation utilities."""

    TEMPLATES_ROOT = Path("templates_storage")
    STYLE_ROOT = TEMPLATES_ROOT / "style_refs"

    @classmethod
    def ensure_dirs(cls) -> None:
        cls.TEMPLATES_ROOT.mkdir(parents=True, exist_ok=True)
        cls.STYLE_ROOT.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Template CRUD
    # ------------------------------------------------------------------ #
    @classmethod
    def list_templates(cls) -> List[TemplateMetadata]:
        cls.ensure_dirs()
        templates: List[TemplateMetadata] = []
        for path in cls.TEMPLATES_ROOT.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                templates.append(TemplateMetadata.from_dict(data))
            except Exception:
                continue
        templates.sort(key=lambda tpl: tpl.created_at, reverse=True)
        return templates

    @classmethod
    def get_template(cls, name: str) -> Optional[TemplateMetadata]:
        cls.ensure_dirs()
        path = cls._template_path(name)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return TemplateMetadata.from_dict(data)

    @classmethod
    def save_template(
        cls,
        *,
        base_prompt: str,
        slides_count: int,
        username: str,
        style_image: Optional[UploadFile],
        template_name: Optional[str] = None,
        auto_generate_daily: bool = False,
    ) -> TemplateMetadata:
        cls.ensure_dirs()

        base_prompt = base_prompt.strip()
        if not base_prompt:
            raise ValueError("Template prompt cannot be empty.")

        try:
            slides_count_val = int(slides_count)
        except (TypeError, ValueError):
            slides_count_val = 1
        slides_count_val = max(1, slides_count_val)

        metadata = cls.get_template(template_name) if template_name else None
        name = metadata.name if metadata else cls._create_template_name(base_prompt)

        style_ref = metadata.style_ref if metadata else ""
        if style_image and style_image.filename:
            style_ref = cls._store_style_reference(style_image, name)
        elif not style_ref:
            raise ValueError("Style reference image is required for template creation.")

        payload = TemplateMetadata(
            name=name,
            base_prompt=base_prompt,
            slides_count=slides_count_val,
            style_ref=style_ref,
            username=username.strip() or "@username",
            auto_generate_daily=auto_generate_daily or (metadata.auto_generate_daily if metadata else False),
            created_at=metadata.created_at if metadata else datetime.utcnow().isoformat(),
            last_generated_at=metadata.last_generated_at if metadata else None,
            font=metadata.font if metadata else None,
            text_area=metadata.text_area if metadata else None,
        )
        cls._write_template(payload)
        return payload

    @classmethod
    def set_auto_daily(cls, name: str, enabled: bool) -> Optional[TemplateMetadata]:
        template = cls.get_template(name)
        if not template:
            return None
        template.auto_generate_daily = enabled
        cls._write_template(template)
        return template

    @classmethod
    def mark_generated(cls, name: str) -> None:
        template = cls.get_template(name)
        if not template:
            return
        template.mark_generated()
        cls._write_template(template)

    # ------------------------------------------------------------------ #
    # Generation helpers (text-only mode)
    # ------------------------------------------------------------------ #
    @classmethod
    def generate_carousel(
        cls,
        *,
        idea: str,
        slides_count: int,
        username: str,
        style_ref: Optional[str],
        output_root: Path = Path("output"),
    ) -> dict:
        try:
            slides_count_val = int(slides_count)
        except (TypeError, ValueError):
            slides_count_val = 1
        slides_count_val = max(1, slides_count_val)

        slides_struct = cls._generate_slide_texts(idea, slides_count_val)
        # Use first slide title or idea for background generation
        cover_line = slides_struct[0].get("title", "") if slides_struct else idea.strip()

        # Build job payload first
        job_payload = cls._build_job(slides_struct, idea.strip(), username.strip() or "@username", style_ref)
        
        # Background handling:
        # - If style_ref exists: generate cover via AITunnel with style_ref as reference
        # - If no style_ref: generate background without reference
        bg_cover = None
        palette_from_cover = None
        
        if style_ref and Path(style_ref).exists():
            photo_path = str(style_ref)
            bg_cover = {"mode": "photo", "path": photo_path}
            palette_from_cover = None  # не нужен, используем ту же фотографию на всех слайдах
        else:
            if USE_AITUNNEL_BG:
                from app.services.nlp_utils import strip_markup
                clean_topic = strip_markup(cover_line or idea.strip())
                background_path = cls._generate_background_image(
                    idea=clean_topic,
                    cover_line=clean_topic,
                    style_ref=None,
                )
                if background_path and Path(background_path).exists():
                    bg_cover = {"mode": "photo", "path": str(background_path)}
                    from app.carousel.core import _bg_photo, _extract_palette
                    cover_img = _bg_photo(str(background_path), apply_darkening=False)
                    if cover_img:
                        palette_from_cover = _extract_palette(cover_img, k=5)
                else:
                    bg_cover = {"mode": "solid", "color": "#0f0f12"}
            else:
                bg_cover = {"mode": "solid", "color": "#0f0f12"}
        
        if palette_from_cover is None:
            palette_from_cover = [(30, 30, 40), (50, 50, 60), (20, 20, 30)]
        
        if len(job_payload["slides"]) > 0:
            job_payload["slides"][0]["bg"] = bg_cover
            job_payload["slides"][0]["is_cover"] = True
        
        # Для внутренних слайдов: генерируем фоны в стиле загруженного фото
        for idx in range(1, len(job_payload["slides"])):
            if style_ref and Path(style_ref).exists():
                # Генерируем новый фон через AI с использованием style_ref как reference
                from uuid import uuid4
                slide_bg_path = Path("output") / f"slide_bg_{uuid4().hex[:8]}.png"
                
                # Строим промпт для внутреннего слайда
                slide_title = job_payload["slides"][idx].get("title", "")
                inner_prompt = cls._build_inner_slide_prompt(idea, slide_title, style_ref)
                
                # Генерация фона: по умолчанию через AI (AITunnel), локальная только если явно включена
                import os
                from app.core.config import settings
                # По умолчанию False (AI генерация), только если явно указано True - используем локальную
                use_local_bg = getattr(settings, 'USE_LOCAL_BG_GENERATION', False) or os.getenv("USE_LOCAL_BG_GENERATION", "false").lower() in {"1", "true", "yes", "on"}
                
                if use_local_bg:
                    # БЕСПЛАТНЫЙ вариант: используем clean background в стилистике фото
                    # Фон должен быть в той же стилистике (темно-синий, черный, белый), но не само фото
                    print(f"💰 Using LOCAL (free) background: creating style-based background for slide {idx+1}")
                    try:
                        from app.services.img_analysis import safe_palette_from
                        # Извлекаем палитру из фото для создания фона в стилистике
                        style_palette = safe_palette_from(str(style_ref), k=5)
                        print(f"DEBUG: Extracted palette from {style_ref}: {style_palette}")
                        if not style_palette or len(style_palette) == 0:
                            print(f"WARN: Empty palette extracted from {style_ref}, using fallback")
                            style_palette = [(30, 30, 50), (50, 50, 70), (70, 70, 90)]  # Темно-синие оттенки
                        # Используем clean background с палитрой из фото - фон будет в стилистике фото
                        job_payload["slides"][idx]["bg"] = {"mode": "clean", "palette": style_palette}
                        print(f"✓ Created style-based background for slide {idx+1} with palette: {style_palette[:3]}")
                    except Exception as exc:
                        print(f"✗ Error creating style-based background for slide {idx+1}: {exc}")
                        # Fallback: используем темно-синие оттенки
                        job_payload["slides"][idx]["bg"] = {"mode": "clean", "palette": [(30, 30, 50), (50, 50, 70), (70, 70, 90)]}
                else:
                    # ПЛАТНЫЙ вариант: генерируем через AI (если включен)
                    try:
                        from app.services.image_gen import generate_image
                        print(f"[DEPRECATED] AI generation for slide {idx+1} - should use single background approach")
                        print(f"🎨 Prompt for slide {idx+1}: {inner_prompt[:200]}...")
                        # Используем полный размер для качества (можно уменьшить до "512x640" для экономии)
                        generated_bg = generate_image(
                            prompt=inner_prompt,
                            style_image_path=str(style_ref),
                            out_path=slide_bg_path,
                            size="1080x1350",  # Полный размер для качества (или "512x640" для экономии)
                        )
                        if generated_bg and Path(generated_bg).exists():
                            job_payload["slides"][idx]["bg"] = {"mode": "photo", "path": str(generated_bg)}
                            print(f"✓ Generated AI background for slide {idx+1}: {generated_bg}")
                        else:
                            # Fallback: используем clean background с палитрой из стиля
                            print(f"⚠ AI generation failed for slide {idx+1}, using clean background with style palette")
                            from app.services.img_analysis import safe_palette_from
                            style_palette = safe_palette_from(str(style_ref), k=5)
                            job_payload["slides"][idx]["bg"] = {"mode": "clean", "palette": style_palette}
                    except Exception as exc:
                        print(f"✗ Error generating AI background for slide {idx+1}: {exc}")
                        import traceback
                        traceback.print_exc()
                        # Fallback: используем clean background с палитрой из стиля
                        try:
                            from app.services.img_analysis import safe_palette_from
                            style_palette = safe_palette_from(str(style_ref), k=5)
                            job_payload["slides"][idx]["bg"] = {"mode": "clean", "palette": style_palette}
                        except:
                            job_payload["slides"][idx]["bg"] = {"mode": "clean", "palette": [(30, 30, 40), (50, 50, 60)]}
            else:
                job_payload["slides"][idx]["bg"] = {"mode": "clean", "palette": palette_from_cover}

        # Actually render the carousel
        output_dir = render_carousel(job_payload, output_root)

        # Collect preview paths
        previews = []
        if output_dir.exists():
            preview_files = sorted(output_dir.glob("slide_*.png"))
            previews = [f"/output/{output_dir.name}/{p.name}" for p in preview_files]

        return {
            "slides": slides_struct,
            "slides_struct": slides_struct,
            "debug_mode": None,
            "job": job_payload,
            "output_dir": str(output_dir),
            "previews": previews,
        }

    @classmethod
    def generate_batch_from_template(
        cls,
        template: TemplateMetadata,
        *,
        count: int = 5,
        output_root: Path = Path("output"),
    ) -> List[Path]:
        cls.ensure_dirs()
        results: List[Path] = []
        for _ in range(max(1, count)):
            variant_topic = f"{template.base_prompt.strip()} — вариант {uuid4().hex[:4]}"
            cls.generate_carousel(
                idea=variant_topic,
                slides_count=template.slides_count,
                username=template.username,
                style_ref=template.style_ref,
                output_root=output_root,
            )
        cls.mark_generated(template.name)
        return results

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @classmethod
    def _template_path(cls, name: str) -> Path:
        return cls.TEMPLATES_ROOT / f"{name}.json"

    @classmethod
    def _write_template(cls, metadata: TemplateMetadata) -> None:
        cls.ensure_dirs()
        path = cls._template_path(metadata.name)
        path.write_text(json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def _create_template_name(cls, base_prompt: str) -> str:
        slug = cls._slugify(base_prompt)[:40].strip("-") or uuid4().hex[:8]
        candidate = slug
        suffix = 1
        while cls._template_path(candidate).exists():
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate

    @classmethod
    def _slugify(cls, value: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
        slug = re.sub(r"\s+", "-", slug, flags=re.UNICODE)
        return slug.lower()

    @classmethod
    def _store_style_reference(cls, upload: UploadFile, template_name: str) -> str:
        cls.ensure_dirs()
        suffix = Path(upload.filename or "style.png").suffix or ".png"
        dest = cls.STYLE_ROOT / f"{template_name}_{uuid4().hex}{suffix}"
        upload.file.seek(0)
        dest.write_bytes(upload.file.read())
        return str(dest)

    @classmethod
    def _fallback_block(cls, mode: str, num: int) -> dict:
        """Generate a fallback slide block with the given number."""
        if mode == "mistakes":
            title = f"Ошибка №{num}: ты делаешь это неправильно"
            items = [
                "ты тратишь бюджет не туда",
                "ты винишь алгоритм вместо цифр",
                "ты называешь это «сложно», но просто не сделал систему",
            ]
        else:
            title = f"Шаг №{num}: сделай это сразу"
            items = [
                "раздели аудиторию по намерению, не по возрасту",
                "не жги бюджет вслепую — тестируй маленькими сегментами",
            ]
        
        return {
            "type": "list",
            "title": title,
            "items": items,
            "body": "",
        }

    @classmethod
    def _parse_block_to_slide(cls, block: str, mode: str, num: int) -> dict:
        """Parse a single text block into a slide dict. Returns fallback if title is empty."""
        lines = [line.strip() for line in block.split("\n") if line.strip()]

        # If no lines at all, return fallback
        if not lines:
            return cls._fallback_block(mode, num)

        # First non-empty line is preliminary title
        title_raw = lines[0]
        title = _clean_text(title_raw)

        # If title is empty after cleaning, return fallback
        if not title:
            return cls._fallback_block(mode, num)

        # Lines starting with "- " or "-" are bullets
        bullets: List[str] = []
        for line in lines[1:]:
            cleaned_line = _clean_text(line)
            if cleaned_line.startswith("- "):
                bullet_text = _clean_text(cleaned_line[2:])
                if bullet_text:  # Only add non-empty bullets
                    bullets.append(bullet_text)
            elif cleaned_line.startswith("-"):
                bullet_text = _clean_text(cleaned_line[1:])
                if bullet_text:  # Only add non-empty bullets
                    bullets.append(bullet_text)
            # Other lines are ignored (no body for now)

        return {
            "type": "list",
            "title": title,
            "items": bullets,
            "body": "",
        }

    @classmethod
    def _generate_slide_texts(cls, idea: str, slides_count: int) -> List[dict]:
        """Generate slide texts using new JSON structure with local markup application."""
        idea_clean = (idea or "").strip()

        def _cover_title_from_idea(text: str) -> str:
            stripped = text.strip().rstrip('.!?')
            if not stripped:
                return "Несколько советов по теме"
            lowered = stripped.lower()
            if lowered.startswith("как "):
                rest = stripped[4:]
                return f"Несколько советов: как {rest}"
            if lowered.startswith("что "):
                rest = stripped[4:]
                return f"Что важно: {rest}"
            if lowered.startswith("почему "):
                rest = stripped[7:]
                return f"Почему важна тема: {rest}"
            return f"Несколько советов: {stripped}"

        # Call generate_carousel_text with slides_count, with error handling
        try:
            raw_text = generate_carousel_text(idea_clean, slides_count=slides_count)
        except Exception as e:
            print(f"text_gen error => {type(e).__name__}: {e}")
            # Use local fallback text generation
            from app.services.text_gen import _local_fallback_text
            raw_text = _local_fallback_text(idea_clean, slides_count)
        
        from app.services.nlp_utils import normalize_spaces, normalize_words, top_keywords, strip_markup

        try:
            data = json.loads(raw_text)
            if not isinstance(data, dict) or "slides" not in data:
                raise ValueError("Invalid JSON structure")
            raw_slides = data["slides"]
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"JSON parse error: {e}, using fallback")
            from app.services.text_gen import _local_fallback_text
            fallback_struct = json.loads(_local_fallback_text(idea_clean, slides_count))
            raw_slides = fallback_struct.get("slides", [])

        # Validate that generated content matches topic; otherwise fallback
        idea_tokens = set(normalize_words(idea_clean))
        if idea_tokens and raw_slides:
            produced_tokens = []
            for raw_slide in raw_slides[:slides_count]:
                text_blob = " ".join(
                    [
                        str(raw_slide.get("title", "")),
                        *[str(x) for x in raw_slide.get("bullets", [])],
                        *[str(x) for x in raw_slide.get("keywords", [])],
                    ]
                )
                produced_tokens.extend(normalize_words(text_blob))
            if produced_tokens and not any(token in idea_tokens for token in produced_tokens):
                print("Topic mismatch detected, using fallback struct")
                from app.services.text_gen import _local_fallback_text
                fallback_struct = json.loads(_local_fallback_text(idea_clean, slides_count))
                raw_slides = fallback_struct.get("slides", [])

        slides: List[dict] = []
        prepared_plain = []
        
        def _sanitize_keywords_list(raw: list[str]) -> list[str]:
            seen = set()
            cleaned: list[str] = []
            for kw in raw or []:
                kw_clean = normalize_spaces(strip_markup(str(kw)))
                if not kw_clean:
                    continue
                word_count = len(kw_clean.split())
                if word_count == 0 or word_count > 3:
                    continue
                if len(kw_clean) > 40:
                    continue
                key = kw_clean.lower()
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append(kw_clean)
                if len(cleaned) >= 5:
                    break
            return cleaned

        def _clean_bullet(text: str) -> str:
            cleaned = strip_markup(text)
            cleaned = cleaned.lstrip("-–—•·•").strip()
            return normalize_spaces(cleaned)

        def _clean_title(text: str) -> str:
            return normalize_spaces(strip_markup(text))

        def _build_cover_title(raw_idea: str) -> str:
            base = normalize_spaces(strip_markup(raw_idea))
            if not base:
                return "Твоя тема"
            lowered = base.strip().rstrip(".!?")
            idea_lower = lowered.lower()
            if idea_lower.startswith("как "):
                suffix = lowered[0].lower() + lowered[1:]
                return f"Как {suffix[4:]}"
            if idea_lower.startswith("что "):
                suffix = lowered[0].lower() + lowered[1:]
                return f"Что делать: {suffix[4:]}"
            if idea_lower.startswith("почему "):
                suffix = lowered[0].lower() + lowered[1:]
                return f"Почему это важно: {suffix[7:]}"
            if idea_lower.startswith("где "):
                suffix = lowered[0].lower() + lowered[1:]
                return f"Где найти ответ: {suffix[4:]}"
            return lowered

        # Process each slide from JSON
        for idx, raw_slide in enumerate(raw_slides[:slides_count], 1):
            title = _clean_title(str(raw_slide.get("title", "")))
            bullets_raw = [str(b) for b in raw_slide.get("bullets", []) if str(b).strip()]
            bullets_clean = []
            for b in bullets_raw:
                cleaned = _clean_bullet(b)
                if cleaned:
                    bullets_clean.append(cleaned)
            keywords_raw = [str(k) for k in raw_slide.get("keywords", []) if str(k).strip()]
            keywords = _sanitize_keywords_list(keywords_raw)

            # Ensure we have a valid slide
            if not title:
                title = f"{idea_clean}: ключевая мысль {idx}"

            if not bullets_clean:
                bullets_clean = ["добавь практический пункт"]
            plain_entry = {
                "title": normalize_spaces(title),
                "bullets": [normalize_spaces(b) for b in bullets_clean],
                "keywords": keywords,
            }
            prepared_plain.append(plain_entry)

        # Auto-fill keywords if missing using top_keywords
        cover_keywords = []
        if prepared_plain:
            need_keywords = any(not entry["keywords"] for entry in prepared_plain)
            if need_keywords:
                auto_kw = top_keywords(
                    [{"title": entry["title"], "bullets": entry["bullets"]} for entry in prepared_plain],
                    k=4,
                )
                for entry, kw in zip(prepared_plain, auto_kw):
                    if not entry["keywords"]:
                        entry["keywords"] = kw
            cover_keywords = prepared_plain[0].get("keywords", [])
        else:
            # No valid slides parsed, use fallback once
            from app.services.text_gen import _local_fallback_text
            fallback_struct = json.loads(_local_fallback_text(idea_clean, slides_count))
            for raw_slide in fallback_struct.get("slides", [])[:slides_count]:
                prepared_plain.append({
                    "title": normalize_spaces(raw_slide.get("title", "")),
                    "bullets": [normalize_spaces(b) for b in raw_slide.get("bullets", [])],
                    "keywords": raw_slide.get("keywords", []),
                })
            cover_keywords = prepared_plain[0].get("keywords", []) if prepared_plain else []

        # Apply markup and build slides
        for idx, entry in enumerate(prepared_plain, 1):
            normalized_title = entry["title"]
            normalized_bullets = [b if b.startswith("- ") else "- " + b for b in entry["bullets"]]

            slides.append({
                "type": "list",
                "title": normalized_title,
                "items": normalized_bullets,
                "body": "",
            })

        # Pad to slides_count if needed
        while len(slides) < slides_count:
            num = len(slides) + 1  # Human-readable number starting from 1
            fallback_slide = {
                "type": "list",
                "title": f"{idea_clean}",
                "items": ["добавь практический пункт"],
                        "body": "",
                    }
            slides.append(fallback_slide)

        # Truncate if more than needed
        slides = slides[:slides_count]
        
        if slides:
            cover_plain = _build_cover_title(idea_clean)

            slides[0]["type"] = "cover"
            slides[0]["title"] = cover_plain
            slides[0]["items"] = []
            slides[0]["body"] = ""
        
        # Final validation: ensure all slides have non-empty title
        for i, slide in enumerate(slides):
            if not slide.get("title"):
                # Replace any slide with empty title with fallback
                num = i + 1
                slides[i] = {
                    "type": "list",
                    "title": normalize_spaces(f"{idea_clean}: ключевая мысль {num}"),
                    "items": ["- добавь практический пункт"],
                    "body": "",
                }
            # Ensure required structure
            slide.setdefault("type", "list")
            slide.setdefault("items", [])
            slide.setdefault("body", "")

        return slides

    @classmethod
    def _build_background_prompt(cls, idea: str, cover_line: str, style_ref: Optional[str]) -> str:
        """Builds a prompt for AI background image generation with strict no-text requirements."""
        topic_hint = cover_line or idea.strip()
        has_style_ref = bool(style_ref)
        
        prompt = f"""Сгенерируй фоновое изображение для Instagram-карусели.

Тема: "{topic_hint}".

Требования:
- Это фон под текст, не постер.
- Никаких слов, букв, цифр, логотипов, стрелок, иконок UI.
- Не добавляй текст на самой картинке.
- Фон должен быть читаемым: гладкие градиенты/мягкие формы, без текста, логотипов, стрелок, UI-иконок.
- Держи фон спокойным и читаемым, с чётким ощущением глубины и настроения темы.
- Формат вертикальный 1080x1350.

Стиль:
"""
        
        if has_style_ref:
            prompt += """- Используй цветовую палитру и настроение референса, но не копируй сюжет, лица, буквы.
- Сохрани палитру и настроение этого референса, но не копируй картинку дословно.
- Это должна быть новая вариация в том же стиле."""
        else:
            prompt += "- Подбери палитру и свет, которые передают тему."
        
        print("BG_PROMPT DEBUG:", prompt[:400])
        return prompt

    @classmethod
    def _build_inner_slide_prompt(cls, idea: str, slide_title: str, style_ref: Optional[str]) -> str:
        """Строит промпт для генерации фона внутреннего слайда в стиле загруженного фото."""
        has_style_ref = bool(style_ref and Path(style_ref).exists())
        
        # Улучшенный промпт для нейросети - явно просим проанализировать стиль и создать похожий фон
        prompt = f"""Проанализируй загруженное изображение-референс и создай фоновое изображение в ТОЧНО ТАКОЙ ЖЕ СТИЛИСТИКЕ для внутреннего слайда Instagram-карусели.

Тема слайда: "{slide_title}".

КРИТИЧЕСКИ ВАЖНО - Проанализируй загруженное изображение и извлеки из него:
- Цветовую палитру (темно-синие, черные, белые оттенки - какие именно присутствуют)
- Стиль освещения (темное/светлое, контрастное/мягкое)
- Общую атмосферу и настроение
- Текстуру и тип градиента (плавный, резкий, размытый)

Создай фоновое изображение которое:
1. ИСПОЛЬЗУЕТ ТУ ЖЕ ЦВЕТОВУЮ ПАЛИТРУ из референса (темно-синий, черный, белый - те же оттенки)
2. ИМЕЕТ ТО ЖЕ НАСТРОЕНИЕ (темное, драматичное, футуристичное - как в референсе)
3. СОЗДАЕТ ТУ ЖЕ АТМОСФЕРУ что и референс
4. НО БЕЗ конкретных объектов из референса (без робота, без конкретных деталей)

Требования к результату:
- Абстрактный фон под текст (градиенты, размытия, плавные переходы)
- Никаких слов, букв, цифр, логотипов, стрелок, иконок, лиц
- ТОЧНО ТА ЖЕ цветовая палитра что и в референсе
- ТО ЖЕ настроение и атмосфера
- Читаемый под белый текст
- Вертикальный формат 1080x1350

ВАЖНО: Результат должен выглядеть как фон из референса - та же стилистика, те же цвета, то же настроение."""
        
        if not has_style_ref:
            prompt = """Создай абстрактный фоновое изображение для Instagram-карусели.
- Темная палитра (темно-синий, черный, белый)
- Абстрактные градиенты
- Читаемый под белый текст
- Вертикальный формат 1080x1350"""
        
        print("INNER_SLIDE_PROMPT DEBUG:", prompt[:500])
        return prompt

    @classmethod
    def _generate_background_image(
        cls,
        idea: str,
        cover_line: str,
        style_ref: Optional[str],
    ) -> Path:
        """Generates an AI background image using style_ref as visual reference. Always returns a Path (fallback if generation fails)."""
        print("BG_GEN DEBUG: starting background gen, idea=", idea, "cover_line=", cover_line, "style_ref=", style_ref)
        
        prompt = cls._build_background_prompt(idea, cover_line, style_ref)
        output_path = Path("output") / f"background_{uuid4().hex[:8]}.png"
        
        # Pass style_ref as visual reference image path (if provided)
        style_image_path = style_ref if style_ref and Path(style_ref).exists() else None
        
        try:
            bg_path = generate_image(
                prompt=prompt,
                style_image_path=style_image_path,
                out_path=output_path,
                size="1080x1350",
            )
            
            if bg_path and Path(bg_path).exists():
                print("BG_GEN DEBUG: got background at", bg_path)
                return Path(bg_path)
            else:
                print("BG_GEN WARN: generate_image returned None or invalid path, using fallback")
                raise ValueError("Background generation returned None")
                
        except Exception as exc:
            print("BG_GEN ERROR:", exc)
            # Create fallback black background
            from PIL import Image
            fallback_path = Path("output") / "latest_background_fallback.png"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_img = Image.new("RGB", (1080, 1350), color=(0, 0, 0))
            fallback_img.save(fallback_path, "PNG")
            print("BG_GEN DEBUG: created fallback background at", fallback_path)
            return fallback_path

    @classmethod
    def _build_job(cls, slides: Iterable[dict], topic: str, username: str, style_ref: Optional[str]) -> dict:
        """Build job payload from slides. Does not override types - passes through what comes from slides_struct."""
        job = {
            "username": username or "@username",
            "style_ref": style_ref,
            "topic": topic,
            "slides": [],
        }
        for slide in slides:
            entry = {
                "type": slide.get("type", "list"),  # Default to "list" now, not "text"
                "title": (slide.get("title") or "").strip(),
                "items": list(slide.get("items") or []),
                "body": (slide.get("body") or "").strip(),
            }
            # Build fallback text for backward compatibility
            fallback_text_parts = [entry["title"]] if entry["title"] else []
            if entry["body"]:
                fallback_text_parts.append(entry["body"])
            if entry["items"]:
                fallback_text_parts.append("\n".join(f"- {item}" for item in entry["items"]))
            entry["text"] = "\n\n".join(part for part in fallback_text_parts if part)
            job["slides"].append(entry)
        return job

    @classmethod
    def needs_generation_today(cls, template: TemplateMetadata) -> bool:
        if not template.auto_generate_daily:
            return False
        if not template.last_generated_at:
            return True
        try:
            last_date = datetime.fromisoformat(template.last_generated_at).date()
        except ValueError:
            return True
        return last_date < date.today()
