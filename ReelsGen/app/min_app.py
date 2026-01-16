"""
Instagram Carousel Generator - основное FastAPI приложение
"""
import os
import io
import zipfile
import json
import traceback
import glob
import random
from typing import Optional, List, Tuple
from urllib.parse import quote, unquote

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageDraw

from .services.neuroapi import chat_complete, image_generate
from .services.render import (
    render_cover,
    render_content,
    image_to_bytes,
    CANVAS_SIZE,
    is_light_image,
    render_slide_with_bg,
    build_bg_from_template,
)
from .services.comic_bg import generate_all_slide_backgrounds
from .services.template_manager import template_manager
from .services.template_renderer import template_renderer
from .schemas.template_schema import CarouselTemplate, RenderContent

# Создаём FastAPI приложение
app = FastAPI(
    title="Instagram Carousel Generator",
    description="Минимальный MVP для генерации каруселей Instagram с NeuroAPI",
    version="1.0.0"
)

# Настраиваем директории
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_ROOT = os.path.join(BASE_DIR, "static", "outputs")
COMIC_BACKGROUNDS_DIR = os.path.join(BASE_DIR, "static", "comic_backgrounds")
ANALYZE_CACHE = os.path.join(BASE_DIR, "static", "analyze_cache")
os.makedirs(OUTPUT_ROOT, exist_ok=True)
os.makedirs(COMIC_BACKGROUNDS_DIR, exist_ok=True)
os.makedirs(ANALYZE_CACHE, exist_ok=True)

from .services.utils_io import make_run_dir, save_manifest, CANVAS_SIZE, cover_fit, slugify
from .services.image_provider import generate_image_bytes

# Настраиваем шаблоны и статические файлы
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUT_ROOT), name="outputs")

# Системный промпт для генерации плана карусели
SYSTEM_PROMPT = (
    "Ты — редактор Instagram-каруселей. Пиши кратко, по делу, без воды. "
    "Никаких эмодзи, максимум 40–60 слов на слайд. "
    "Формат вывода — валидный JSON без комментариев, строго по схеме из задания."
)


def get_random_comic_background() -> Optional[Image.Image]:
    """
    Выбирает случайный фон из каталога comic_backgrounds
    
    Returns:
        PIL Image объект или None если каталог пуст
    """
    try:
        # Ищем только .jpg, .jpeg, .png файлы
        bg_paths = []
        bg_paths.extend(glob.glob(os.path.join(COMIC_BACKGROUNDS_DIR, "*.jpg")))
        bg_paths.extend(glob.glob(os.path.join(COMIC_BACKGROUNDS_DIR, "*.jpeg")))
        bg_paths.extend(glob.glob(os.path.join(COMIC_BACKGROUNDS_DIR, "*.png")))
        
        if not bg_paths:
            return None
        
        # Выбираем случайный фон
        bg_path = random.choice(bg_paths)
        bg_img = Image.open(bg_path).convert("RGBA")
        bg_img = cover_fit(bg_img, CANVAS_SIZE)  # Используем cover_fit вместо resize
        
        return bg_img
    except Exception as e:
        print(f"Ошибка загрузки фона из каталога: {e}")
        return None


def create_fallback_background(color: str = "#2F6F48") -> Image.Image:
    """
    Создаёт fallback фон (заливка цветом)
    
    Args:
        color: Hex цвет (по умолчанию #2F6F48)
    
    Returns:
        PIL Image с залитым фоном
    """
    # Парсим hex цвет
    c = color.lstrip("#")
    if len(c) == 3:
        r, g, b = [int(v * 2, 16) for v in c]
    else:
        r = int(c[0:2], 16)
        g = int(c[2:4], 16)
        b = int(c[4:6], 16)
    
    bg_img = Image.new('RGB', CANVAS_SIZE, (r, g, b))
    return bg_img

# Стиль для генерации изображений
IMAGE_STYLE_PROMPT = (
    "Minimalist editorial illustration for an Instagram carousel slide. "
    "Monochrome or 2-tone palette, clean background, high negative space for text. "
    "Style: vintage engraving + modern flat, soft shadows, high contrast, no clutter. "
    "Aspect: square 1:1, safe composition for top/left text overlay."
)


@app.get("/", response_class=HTMLResponse)
async def ui(request: Request):
    """Главная страница с простым интерфейсом выбора шаблона"""
    return templates.TemplateResponse("simple_ui.html", {"request": request})


@app.get("/advanced", response_class=HTMLResponse)
async def advanced_ui(request: Request):
    """Расширенная форма для генерации карусели (старый интерфейс)"""
    return templates.TemplateResponse("ui.html", {"request": request})



@app.get("/test-photo-overlay", response_class=HTMLResponse)
async def test_photo_overlay_ui():
    """Return a small HTML form that posts to /test-photo-overlay."""
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <title>Photo Overlay (local test)</title>
        </head>
        <body style="font-family: sans-serif; max-width: 720px; margin: 40px auto;">
            <h1>Photo Overlay (local test)</h1>
            <form action="/test-photo-overlay" method="post" enctype="multipart/form-data" style="display:flex;flex-direction:column;gap:16px;">
                <label>
                    Background image:
                    <input type="file" name="image" accept="image/*" required>
                </label>
                <label>
                    Slides text (JSON array):
                    <textarea name="slides_text" rows="4">["Slide headline 1","Slide headline 2","Slide headline 3"]</textarea>
                </label>
                <label>
                    Templates (JSON array):
                    <textarea name="templates" rows="3">["user_photo","green_plain","green_pattern"]</textarea>
                </label>
                <label>
                    Size:
                    <input type="text" name="size" value="1080x1350">
                </label>
                <label>
                    <input type="checkbox" name="darken" checked> Darken backgrounds if needed
                </label>
                <label>
                    Template ID (optional):
                    <input type="text" name="template_id" placeholder="e.g. instagram_carousel">
                    <small style="display:block;font-size:12px;color:#666;">
                        Укажите сохранённый шаблон, чтобы использовать собственные фон, шрифты и расположение текста.
                    </small>
                </label>
                <button type="submit">Generate ZIP (no AI)</button>
            </form>
        </body>
        </html>
        """,
        media_type="text/html",
    )
@app.get("/constructor", response_class=HTMLResponse)
async def constructor_ui(request: Request):
    """Конструктор шаблонов слайдов"""
    return templates.TemplateResponse("constructor.html", {"request": request})


@app.post("/generate-legacy")
async def generate_carousel_legacy(
    request: Request,
    cover_image: UploadFile = File(..., description="Изображение для обложки"),
    title: str = Form(..., description="Заголовок карусели"),
    slides_count: int = Form(..., ge=2, le=10, description="Количество слайдов (2-10)"),
    prompt: Optional[str] = Form(None, description="Промпт для генерации текста (опционально, используется для уточнения темы)"),
    use_ai_backgrounds: Optional[str] = Form(None, description="Использовать AI-фоны (по умолчанию true, приоритет над ENV)"),
    watermark_text: Optional[str] = Form(None, description="Текстовый водяной знак"),
    watermark_png: Optional[UploadFile] = File(None, description="PNG водяной знак")
):
    """
    УСТАРЕВШИЙ: Генерирует карусель через старую систему рендеринга (оставлен для совместимости)
    """
    """
    Генерирует карусель Instagram и возвращает ZIP архив со слайдами
    """
    try:
        # Валидация входных данных
        if slides_count < 2 or slides_count > 10:
            raise HTTPException(status_code=400, detail="Количество слайдов должно быть от 2 до 10")
        
        if not title or not title.strip():
            raise HTTPException(status_code=400, detail="Заголовок не может быть пустым")
        
        # Проверяем файл обложки
        if not cover_image.content_type or not cover_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Файл обложки должен быть изображением")
        
        # 1. Генерируем план карусели через NeuroAPI
        user_prompt = (
            f'Тема: "{title}"\n'
            f"Количество слайдов (включая обложку): {slides_count}\n\n"
            "Сделай план карусели. Слайд 1 — обложка (только крупный заголовок). "
            "Слайды 2..N — по 1 короткому тезису + 2–5 пунктов для раскрытия. "
            "Тон: практичный, ясный. Язык: русский. "
            "Верни только JSON по схеме без дополнительных пояснений."
        )
        
        raw_plan = await chat_complete(SYSTEM_PROMPT, user_prompt, temperature=0.3)
        
        # Парсим JSON план
        try:
            plan = json.loads(raw_plan)
        except (json.JSONDecodeError, TypeError) as e:
            # Попытка исправить JSON
            repair_prompt = (
                "Верни валидный JSON. Исправь формат без пояснений. "
                "Схема: {\"slides\":[{\"idx\":1,\"role\":\"cover\",\"headline\":\"...\"}, "
                "{\"idx\":2,\"role\":\"content\",\"headline\":\"...\",\"bullets\":[\"...\",\"...\"]}], "
                "\"style\":{\"tone\":\"...\",\"target\":\"IG\",\"cta\":\"...\"}}"
            )
            try:
                repair_result = await chat_complete(repair_prompt, f"Исходный текст: {raw_plan}")
                plan = json.loads(repair_result)
            except Exception:
                # Если и это не сработало - используем заглушку
                plan = {
                    "slides": [
                        {"idx": 1, "role": "cover", "headline": title},
                        {"idx": 2, "role": "content", "headline": "Основные моменты", 
                         "bullets": ["Важный пункт 1", "Важный пункт 2", "Важный пункт 3"]}
                    ],
                    "style": {"tone": "практичный", "target": "IG", "cta": "Листай дальше"}
                }
        
        slides = plan.get("slides", [])
        if not slides:
            raise HTTPException(status_code=500, detail="Не удалось сгенерировать план карусели")
        
        # 2. Подготавливаем водяной знак
        watermark_png_bytes = None
        if watermark_png and watermark_png.filename:
            watermark_png_bytes = await watermark_png.read()
        
        # Нормализуем текстовый watermark (может быть из username или watermark_text)
        watermark_text_final = watermark_text or username
        from .services.watermark import normalize_username
        if watermark_text_final:
            watermark_text_final = normalize_username(watermark_text_final)
            if not watermark_text_final:
                watermark_text_final = None
        else:
            watermark_text_final = None
        
        # 3. Генерируем фоны для всех контент-слайдов параллельно (на основе текста каждого слайда)
        print(f"[generate] Generating backgrounds for {len(slides)} slides...")
        
        # Проверяем флаг USE_AI_BACKGROUNDS (по умолчанию true)
        use_ai_bg_env = os.getenv("USE_AI_BACKGROUNDS", "true").lower() in ("1", "true", "yes")
        use_ai_bg = (use_ai_backgrounds or "").lower() in ("1", "true", "yes") if use_ai_backgrounds is not None else use_ai_bg_env
        
        # Генерируем фоны параллельно для всех контент-слайдов
        slide_backgrounds: List[Optional[Image.Image]] = []
        if use_ai_bg:
            try:
                slide_backgrounds = await generate_all_slide_backgrounds(
                    slides=slides,
                    cache_dir=ANALYZE_CACHE,
                    title=title,
                    use_cache=True
                )
                print(f"[generate] ✅ Generated {len([bg for bg in slide_backgrounds if bg is not None])} backgrounds")
            except Exception as e:
                print(f"[generate] ❌ Background generation failed: {type(e).__name__}: {e}")
                traceback.print_exc()
                slide_backgrounds = []
        
        # Создаем индекс для маппинга контент-слайдов к фонам
        content_slide_index = 0
        
        # 4. Создаём директорию для запуска
        run_dir = make_run_dir(OUTPUT_ROOT, title)
        created_files = []
        
        # 5. Генерируем слайды
        zip_buffer = io.BytesIO()
        cover_bytes = await cover_image.read()  # Читаем обложку один раз
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Проходим по всем слайдам
            for i, s in enumerate(slides, start=1):
                try:
                    slide_type = s.get("type", "content")
            
                    if slide_type == "cover" or i == 1:
                        # Обложка - ВСЕГДА используем загруженное фото пользователя
                        # AI-генерация не применяется для обложки
                        img = await render_cover(
                            cover_bytes, 
                            title, 
                            watermark_text_final, 
                            watermark_png_bytes,
                            bg_prompt=None,  # Не передаем для обложки
                            use_ai_bg=False  # Всегда False для обложки
                        )
                    else:
                        # Контент-слайд - используем сгенерированный фон на основе текста слайда
                        bg_img = None
                        
                        # Берем фон из массива сгенерированных фонов (по индексу контент-слайда)
                        if use_ai_bg and slide_backgrounds and content_slide_index < len(slide_backgrounds):
                            bg_img = slide_backgrounds[content_slide_index]
                            content_slide_index += 1
                        
                        # Fallback: если фон не сгенерировался - используем локальный комикс или цветной фон
                        if bg_img is None:
                            bg_img = get_random_comic_background() or create_fallback_background()
                        
                        # Применяем cover_fit
                        if bg_img.size != CANVAS_SIZE:
                            bg_img = cover_fit(bg_img, CANVAS_SIZE)
                        bg_img = bg_img.convert("RGBA")
                        
                        # Собираем текст слайда
                        title_text = s.get("headline") or s.get("title") or s.get("heading") or s.get("thesis") or ""
                        points = s.get("bullets") or s.get("points") or []
                        thesis = s.get("thesis") or ""
                        
                        body = thesis.strip()
                        if points:
                            body = (body + ("\n\n" if body else "")) + "\n".join([f"→ {p}" for p in points])
                        
                        # Определяем тип текста по яркости фона
                        is_white = is_light_image(bg_img)
                
                # Рендерим слайд
                        img = await render_content(
                            bg_img=bg_img,
                            title=title_text,
                            bullets=[],
                            body_text=body if body else None,
                            slide_num=i,
                            total_slides=len(slides),
                            is_white_bg=is_white,
                            nickname=None,
                            watermark_text=watermark_text_final,
                            watermark_png=watermark_png_bytes,
                            bg_prompt=None,  # Не используется - фон уже сгенерирован
                            use_ai_bg=False  # Фон уже готов, не генерируем повторно
                        )
                    
                    # Сохраняем на диск и в ZIP
                    out_name = f"slide_{i:02d}.png"
                    out_path = os.path.join(run_dir, out_name)
                    img.convert("RGB").save(out_path, "PNG")
                    created_files.append({"index": i, "file": out_name})
                    
                    bio = io.BytesIO()
                    img.convert("RGB").save(bio, "PNG")
                    zf.writestr(out_name, bio.getvalue())
                    
                    print(f"[generate] slide {i}/{len(slides)} -> {out_path}  size={img.width}x{img.height}")
                
                except Exception as e:
                    print(f"[generate] Ошибка генерации слайда {i}: {e}")
                    traceback.print_exc()
                    # Создаём заглушку
                    stub_img = Image.new("RGB", CANVAS_SIZE, (40, 40, 40))
                    draw = ImageDraw.Draw(stub_img)
                    draw.text((50, 500), f"Ошибка генерации слайда", fill=(255, 255, 255))
                    
                    out_name = f"slide_{i:02d}.png"
                    out_path = os.path.join(run_dir, out_name)
                    stub_img.save(out_path, "PNG")
                    created_files.append({"index": i, "file": out_name})
                    
                    bio = io.BytesIO()
                    stub_img.save(bio, "PNG")
                    zf.writestr(out_name, bio.getvalue())
        
        # Проверяем что сгенерированы слайды
        if zip_buffer.tell() == 0:
            raise HTTPException(status_code=500, detail="Не удалось сгенерировать ни одного слайда")
        
        # Сохраняем манифест
        save_manifest(run_dir, {
            "title": title,
            "slides_total": len(slides),
            "files": created_files
        })
        
        zip_buffer.seek(0)
        
        print(f"[generate] done. slides={len(slides)} zip_size={zip_buffer.getbuffer().nbytes}")
        print(f"[generate] saved to {run_dir}")
        
        # Формируем имя файла на основе заголовка
        # Создаём имя файла с оригинальным заголовком (может содержать русские символы)
        filename = f"carousel_{title[:30]}.zip" if title else "carousel.zip"
        
        # Очищаем имя файла от недопустимых символов для файловой системы, но сохраняем кириллицу
        filename_cleaned = "".join(c for c in filename if c not in ('<', '>', ':', '"', '/', '\\', '|', '?', '*'))
        
        # Создаём ASCII fallback для совместимости со старыми браузерами
        # Используем очищенное имя файла для создания безопасного ASCII варианта
        # Извлекаем только ASCII символы (латиница, цифры, пробелы, дефисы, подчёркивания)
        safe_filename = "".join(c for c in filename_cleaned if c.isascii() and (c.isalnum() or c in (' ', '-', '_', '.'))).rstrip()
        safe_filename = safe_filename.replace(' ', '_')[:30] if safe_filename and len(safe_filename) > 0 else "carousel"
        # Убеждаемся, что расширение .zip присутствует
        if not safe_filename.endswith('.zip'):
            safe_filename = f"{safe_filename}.zip"
        
        # Используем RFC 5987 для кодирования имени файла с поддержкой всех символов
        encoded_filename = quote(filename_cleaned, safe='')
        
        # Формируем заголовок Content-Disposition с использованием как ASCII fallback, так и UTF-8 кодирования
        content_disposition = f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        # Возвращаем ZIP файл
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": content_disposition}
        )
        
    except HTTPException:
        raise  # Пробрасываем HTTP ошибки как есть
    except Exception as e:
        # Логируем полную ошибку для отладки
        print(f"Ошибка генерации карусели: {e}")
        print(traceback.format_exc())
        
        # Возвращаем пользователю понятную ошибку
        raise HTTPException(
            status_code=500, 
            detail=f"Произошла ошибка при генерации карусели: {str(e)}"
        )


@app.post("/generate")
async def generate_carousel_new(
    request: Request,
    cover_image: UploadFile = File(..., description="Изображение для обложки"),
    title: str = Form(..., description="Заголовок карусели"),
    slides_count: int = Form(..., ge=2, le=10, description="Количество слайдов (2-10)"),
    prompt: Optional[str] = Form(None, description="Промпт для генерации текста"),
    template_id: str = Form("instagram_carousel", description="ID шаблона для использования"),
    gradient_color: Optional[str] = Form(None, description="Цвет градиента для фона (hex)")
):
    """
    Новая версия генерации карусели через систему шаблонов
    """
    try:
        # Валидация
        if slides_count < 2 or slides_count > 10:
            raise HTTPException(status_code=400, detail="Количество слайдов должно быть от 2 до 10")
        
        if not title or not title.strip():
            raise HTTPException(status_code=400, detail="Заголовок не может быть пустым")
        
        if not cover_image.content_type or not cover_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Файл обложки должен быть изображением")
        
        # 1. Генерируем план карусели через NeuroAPI (как в старой версии)
        user_prompt = (
            f'Тема: "{title}"\n'
            f"Количество слайдов (включая обложку): {slides_count}\n\n"
            "Сделай план карусели. Слайд 1 — обложка (только крупный заголовок). "
            "Слайды 2..N — по 1 короткому тезису + 2–5 пунктов для раскрытия. "
            "Тон: практичный, ясный. Язык: русский. "
            "Верни только JSON по схеме без дополнительных пояснений."
        )
        
        if prompt:
            user_prompt += f"\n\nДополнительные указания: {prompt}"
        
        raw_plan = await chat_complete(SYSTEM_PROMPT, user_prompt, temperature=0.3)
        
        # Парсим JSON план
        try:
            plan = json.loads(raw_plan)
        except (json.JSONDecodeError, TypeError) as e:
            # Попытка исправить JSON
            repair_prompt = (
                "Верни валидный JSON. Исправь формат без пояснений. "
                "Схема: {\"slides\":[{\"idx\":1,\"role\":\"cover\",\"headline\":\"...\"}, "
                "{\"idx\":2,\"role\":\"content\",\"headline\":\"...\",\"bullets\":[\"...\",\"...\"]}], "
                "\"style\":{\"tone\":\"...\",\"target\":\"IG\",\"cta\":\"...\"}}"
            )
            try:
                repair_result = await chat_complete(repair_prompt, f"Исходный текст: {raw_plan}")
                plan = json.loads(repair_result)
            except Exception:
                # Fallback
                plan = {
                    "slides": [
                        {"idx": 1, "role": "cover", "headline": title},
                        {"idx": 2, "role": "content", "headline": "Основные моменты", 
                         "bullets": ["Важный пункт 1", "Важный пункт 2", "Важный пункт 3"]}
                    ],
                    "style": {"tone": "практичный", "target": "IG", "cta": "Листай дальше"}
                }
        
        slides = plan.get("slides", [])
        if not slides:
            raise HTTPException(status_code=500, detail="Не удалось сгенерировать план карусели")
        
        # 2. Сохраняем обложку во временный файл
        cover_bytes = await cover_image.read()
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_cover:
            temp_cover.write(cover_bytes)
            temp_cover_path = temp_cover.name
        
        # 3. Преобразуем данные в формат RenderContent
        slides_content = []
        
        for i, slide in enumerate(slides):
            if slide.get("role") == "cover" or i == 0:
                # Обложка
                content = RenderContent(
                    title=title,
                    custom_fields={"cover_image_path": temp_cover_path}
                )
            else:
                # Контент-слайд
                headline = slide.get("headline") or slide.get("heading") or slide.get("thesis") or ""
                bullets = slide.get("bullets") or slide.get("points") or []
                
                # Формируем body_text из bullets
                body_text = ""
                if bullets:
                    body_text = "\n".join([f"→ {bullet}" for bullet in bullets])
                
                # Добавляем цвет градиента в custom_fields, если указан
                custom_fields = {}
                if gradient_color:
                    custom_fields["gradient_color"] = gradient_color
                
                content = RenderContent(
                    title=headline,
                    body_text=body_text,
                    bullet_points=bullets,
                    custom_fields=custom_fields
                )
            
            slides_content.append(content)
        
        # 4. Рендерим через новую систему шаблонов
        images = await template_renderer.render_carousel(template_id, slides_content)
        
        # 5. Сохраняем результат в папку проекта
        run_dir = make_run_dir(OUTPUT_ROOT, title)
        created_files = []
        file_urls = []
        
        # Сохраняем каждый слайд как отдельный файл
        for i, img in enumerate(images):
            out_name = f"slide_{i+1:02d}.png"
            out_path = os.path.join(run_dir, out_name)
            
            # Сохраняем на диск
            img.convert("RGB").save(out_path, "PNG")
            
            # Формируем относительный путь для URL
            rel_path = os.path.relpath(out_path, OUTPUT_ROOT).replace("\\", "/")
            # URL-кодируем путь для корректной работы с кириллицей
            rel_path_encoded = "/".join(quote(part, safe="") for part in rel_path.split("/"))
            file_url = f"/outputs/{rel_path_encoded}"
            
            created_files.append({
                "index": i+1,
                "file": out_name,
                "path": rel_path,
                "url": file_url
            })
            file_urls.append(file_url)
            
            print(f"[generate] Сохранен слайд {i+1}/{len(images)}: {out_path}")
        
        # Сохраняем манифест
        run_dir_rel = os.path.relpath(run_dir, OUTPUT_ROOT).replace("\\", "/")
        manifest_data = {
            "title": title,
            "template_id": template_id,
            "slides_total": len(images),
            "files": created_files,
            "generation_method": "template_system",
            "run_dir": run_dir_rel
        }
        save_manifest(run_dir, manifest_data)
        
        # Удаляем временный файл обложки
        try:
            os.unlink(temp_cover_path)
        except:
            pass
        
        print(f"[generate] ✅ Карусель сохранена в: {run_dir}")
        print(f"[generate] Всего слайдов: {len(images)}")
        
        # Формируем view_url через endpoint /carousel
        slug, timestamp = run_dir_rel.split("/", 1) if "/" in run_dir_rel else (run_dir_rel, "")
        if timestamp:
            view_url = f"/carousel/{quote(slug, safe='')}/{timestamp}"
        else:
            view_url = f"/slides"
        
        # Возвращаем JSON с информацией о сохраненных файлах
        return JSONResponse({
            "success": True,
            "title": title,
            "template_id": template_id,
            "slides_total": len(images),
            "run_dir": manifest_data["run_dir"],
            "files": created_files,
            "urls": file_urls,
            "view_url": view_url
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[generate-new] ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Произошла ошибка при генерации карусели: {str(e)}"
        )


@app.post("/test-photo-overlay")
async def test_photo_overlay(
    image: UploadFile = File(..., description="Background image for slide 1"),
    slides_text: str = Form(..., description="JSON array of slide texts"),
    templates: str = Form(..., description="JSON array of template names"),
    size: str = Form("1080x1350", description="Canvas size WIDTHxHEIGHT"),
    darken: bool = Form(True, description="Apply global darkening"),
    title: Optional[str] = Form(None, description="Explicit title for the cover slide"),
    handle: Optional[str] = Form("@yourhandle", description="Handle to show on slides"),
    show_counter: Optional[bool] = Form(True, description="Show page counters on content slides"),
    template_id: Optional[str] = Form(None, description="ID шаблона для рендера через конструктор"),
):


    """
    Технический тест рендера фото+текст без AI.
    """
    slides_text_raw = slides_text or ""
    slides_text_stripped = slides_text_raw.strip()

    if not slides_text_stripped.startswith("["):
        plan_prompt = slides_text_stripped
        ai_resp = await chat_complete(
            "Сделай 1 заголовок и 3–5 коротких слайдов по теме. Ответ в JSON-массиве строк.",
            plan_prompt,
            temperature=0.4,
        )
        try:
            texts_raw = json.loads(ai_resp)
        except Exception:
            texts_raw = [plan_prompt]
    else:
        try:
            texts_raw = json.loads(slides_text_raw)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="slides_text/templates должны быть корректным JSON массивом")

    try:
        template_names = json.loads(templates)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="slides_text/templates должны быть корректным JSON массивом")

    if not isinstance(texts_raw, list) or not texts_raw:
        raise HTTPException(status_code=400, detail="slides_text должен быть непустым массивом строк")
    if not isinstance(template_names, list):
        raise HTTPException(status_code=400, detail="templates должен быть массивом той же длины")

    # parse texts → cover title + content body
    prepared_texts = [str(item or "") for item in texts_raw]
    if title is not None and str(title).strip():
        title_text = str(title).strip()
        body_texts = [t.strip() for t in prepared_texts]
    else:
        title_text = prepared_texts[0].strip() if prepared_texts else ""
        body_texts = [t.strip() for t in prepared_texts[1:]]

    try:
        width_str, height_str = size.lower().split("x")
        target_size = (int(width_str), int(height_str))
    except Exception:
        raise HTTPException(status_code=400, detail="size должен быть в формате WIDTHxHEIGHT (например 1080x1350)")

    run_dir = make_run_dir(OUTPUT_ROOT, "photo-overlay")
    os.makedirs(run_dir, exist_ok=True)

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Файл image пустой")
    uploaded_path = os.path.join(run_dir, "user_upload.png")
    with open(uploaded_path, "wb") as f:
        f.write(image_bytes)

    if template_id and template_id.strip():
        try:
            response = await _render_with_template(
                template_id.strip(),
                [title_text] + body_texts if title_text else prepared_texts,
                uploaded_path,
                run_dir,
            )
            return response
        finally:
            try:
                os.remove(uploaded_path)
            except OSError:
                pass

    # normalize templates: force first = user_photo, pad with green_plain
    total_slides = 1 + len(body_texts)
    templates_normalized = list(template_names) if template_names else []
    if templates_normalized:
        templates_normalized[0] = "user_photo"
    else:
        templates_normalized = ["user_photo"]
    while len(templates_normalized) < total_slides:
        templates_normalized.append("green_plain")
    templates_normalized = templates_normalized[:total_slides]
    handle_value = (handle or "").strip() or None
    show_counter_flag = True if show_counter is None else bool(show_counter)

    slide_files = []
    render_modes = []
    render_templates = []

    if not title_text:
        title_text = "Заголовок"

    # build render queue: (text, template, mode, bg_image_path, bg_fill)
    queue = [(title_text.strip(), templates_normalized[0], "cover", uploaded_path, None)]
    for idx, body_text in enumerate(body_texts):
        tpl = templates_normalized[idx + 1] if (idx + 1) < len(templates_normalized) else "green_plain"
        queue.append((body_text.strip(), tpl, "content", None, None))

    for idx, (text_value, template_name, mode, forced_bg, forced_fill) in enumerate(queue):
        if not text_value.strip():
            raise HTTPException(status_code=400, detail=f"Текст слайда #{idx + 1} пустой")

        bg_path = forced_bg
        bg_fill = forced_fill
        if not bg_path and not bg_fill:
            try:
                bg_path, bg_fill = build_bg_from_template(
                    template_name,
                    upload_path=uploaded_path,
                    size=target_size,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

        # inside the render loop, the render call must be exactly:
        page_idx = idx + 1
        if mode == "cover":
            page_index_value = page_idx
            page_total_value = total_slides
        else:
            page_index_value = page_idx if show_counter_flag else None
            page_total_value = total_slides if show_counter_flag else None
        rendered = render_slide_with_bg(
            text=text_value.strip(),
            bg_image_path=bg_path,
            bg_fill=bg_fill,
            size=target_size,
            darken=darken,
            safe_pad=64,
            watermark=None,
            mode=mode,
            handle=handle_value,
            page_index=page_index_value,
            page_total=page_total_value,
            force_fallback=True,
        )

        # cleanup temp pattern files (keep user upload)
        if bg_path and bg_path != uploaded_path:
            try:
                os.remove(bg_path)
            except OSError:
                pass

        filename = f"slide_{idx + 1}.png"
        filepath = os.path.join(run_dir, filename)
        rendered.convert("RGB").save(filepath, "PNG")
        slide_files.append({"index": idx + 1, "file": filename, "path": filepath})
        render_modes.append(mode)
        render_templates.append(template_name)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_meta in slide_files:
            zf.write(file_meta["path"], arcname=file_meta["file"])

    manifest_payload = {
        "mode": render_modes,
        "templates": render_templates,
        "size": size,
        "slides_total": len(slide_files),
        "files": [{"index": f["index"], "file": f["file"]} for f in slide_files],
    }
    save_manifest(run_dir, manifest_payload)

    zip_buffer.seek(0)
    filename = f"photo-overlay-{slugify('photo-overlay')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


def _parse_slide_for_template(text: str) -> Tuple[str, str, List[str]]:
    normalized = (text or "").replace("\r\n", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if not lines:
        return "", "", []
    heading = lines[0]
    rest = lines[1:]
    bullets: List[str] = []
    body_lines: List[str] = []
    for line in rest:
        stripped = line.lstrip()
        if stripped.startswith(("•", "-", "→", "*", "—")):
            bullets.append(stripped.lstrip("•-→*— ").strip())
        else:
            body_lines.append(line)
    body_text = "\n".join(body_lines).strip()
    return heading, body_text, bullets


async def _render_with_template(
    template_id: str,
    slide_texts: List[str],
    cover_image_path: str,
    run_dir: str,
) -> StreamingResponse:
    if not slide_texts:
        raise HTTPException(status_code=400, detail="Нет текста для рендера по шаблону")

    slides_content: List[RenderContent] = []
    first_slide = slide_texts[0]
    slides_content.append(
        RenderContent(
            title=first_slide,
            custom_fields={"cover_image_path": cover_image_path},
        )
    )

    for slide_text in slide_texts[1:]:
        heading, body_text, bullets = _parse_slide_for_template(slide_text)
        slides_content.append(
            RenderContent(
                title=heading or slide_text,
                body_text=body_text or None,
                bullet_points=bullets or [],
            )
        )

    try:
        images = await template_renderer.render_carousel(template_id, slides_content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось применить шаблон: {exc}")
    slide_files = []
    for idx, img in enumerate(images):
        filename = f"slide_{idx + 1:02d}.png"
        filepath = os.path.join(run_dir, filename)
        img.convert("RGB").save(filepath, "PNG")
        slide_files.append({"index": idx + 1, "file": filename, "path": filepath})

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_meta in slide_files:
            zf.write(file_meta["path"], arcname=file_meta["file"])

    manifest_payload = {
        "mode": ["template"] * len(slide_files),
        "templates": [template_id] * len(slide_files),
        "size": "template",
        "slides_total": len(slide_files),
        "files": [{"index": f["index"], "file": f["file"]} for f in slide_files],
        "template_id": template_id,
        "generation_method": "template_system",
    }
    save_manifest(run_dir, manifest_payload)

    zip_buffer.seek(0)
    filename = f"photo-overlay-{slugify(template_id)}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.get("/analyze", response_class=HTMLResponse)
async def analyze_ui(request: Request):
    """Страница для анализа изображений и генерации промптов"""
    return templates.TemplateResponse("image_analyzer.html", {"request": request})


@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(..., description="Изображение для анализа"),
    style: str = Form("", description="Стиль изображения (пустое = жёлто-черно-оранжевый стиль комиксов)"),
    details: Optional[str] = Form(None)
):
    """
    Анализирует изображение, генерирует промпт и автоматически создаёт новое изображение
    
    Args:
        file: Загруженный файл изображения
        style: Стиль для генерации нового изображения (пустое = жёлто-черно-оранжевый стиль комиксов)
        details: Дополнительные детали для промпта
    
    Returns:
        JSON с результатами анализа, промптом и сгенерированным изображением в base64
    """
    try:
        print(f"[FastAPI] Получен запрос на анализ изображения")
        print(f"[FastAPI] Имя файла: {file.filename}")
        print(f"[FastAPI] Content-Type: {file.content_type}")
        print(f"[FastAPI] Параметры: style='{style}' ({'дефолтный жёлто-черно-оранжевый' if not style else 'пользовательский'}), details={details}")
        
        # Проверяем тип файла
        if not file.content_type or not file.content_type.startswith('image/'):
            error_msg = f"Файл должен быть изображением. Получен тип: {file.content_type}"
            print(f"[FastAPI] ОШИБКА: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Читаем изображение
        print(f"[FastAPI] Читаем файл изображения...")
        image_data = await file.read()
        
        if not image_data or len(image_data) == 0:
            error_msg = "Изображение не было загружено или файл пуст"
            print(f"[FastAPI] ОШИБКА: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        print(f"[FastAPI] Изображение загружено успешно: {len(image_data)} байт")
        
        # Проверяем, что это валидное изображение
        try:
            from PIL import Image
            import io
            # Открываем для проверки
            img = Image.open(io.BytesIO(image_data))
            # verify() закрывает файл, поэтому после него нужно переоткрыть
            img.verify()
            # Переоткрываем для использования
            img = Image.open(io.BytesIO(image_data))
            print(f"[FastAPI] Изображение валидно: {img.format}, размер {img.size}")
        except Exception as e:
            error_msg = f"Файл не является валидным изображением: {str(e)}"
            print(f"[FastAPI] ОШИБКА: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Импортируем функции анализа
        from .services.image_analyzer import (
            analyze_image_from_bytes,
            generate_image_from_prompt
        )
        
        print(f"[FastAPI] Запускаем анализ изображения через Vision API...")
        
        # Анализируем изображение напрямую из байтов (без временных файлов)
        result = await analyze_image_from_bytes(image_data, style=style, details=details)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Неизвестная ошибка при анализе")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # АВТОМАТИЧЕСКАЯ ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ после создания промпта
        # Генерируем изображение всегда, если промпт успешно создан
        if result.get("prompt"):
            try:
                print(f"[FastAPI] ⚡ Автоматически генерируем изображение на основе промпта...")
                print(f"[FastAPI] Промпт: {result['prompt'][:150]}...")
                
                generated_image_bytes = await generate_image_from_prompt(
                    result["prompt"],
                    size="1024x1024"
                )
                
                # Преобразуем изображение в base64 для отправки через JSON
                import base64
                image_base64 = base64.b64encode(generated_image_bytes).decode('utf-8')
                
                result["generated_image_base64"] = image_base64
                result["generated_image_size"] = len(generated_image_bytes)
                result["image_generated"] = True
                
                print(f"[FastAPI] ✅ Изображение успешно сгенерировано: {len(generated_image_bytes)} байт")
                print(f"[FastAPI] ✅ Base64 размер: {len(image_base64)} символов")
                
            except Exception as e:
                print(f"[FastAPI] ❌ ОШИБКА: Не удалось сгенерировать изображение: {e}")
                print(traceback.format_exc())
                result["image_generation_error"] = str(e)
                result["image_generated"] = False
                # Не прерываем выполнение - возвращаем результат с ошибкой генерации
        else:
            print(f"[FastAPI] ⚠️ Промпт не создан, пропускаем генерацию изображения")
            result["image_generated"] = False
        
        return JSONResponse({
            "success": True,
            **result
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка анализа изображения: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Произошла ошибка при анализе изображения: {str(e)}"
        )


def latest_run_dir(root: str) -> Optional[str]:
    """
    Находит последнюю директорию запуска
    
    Args:
        root: Корневая директория outputs
        
    Returns:
        Путь к последней директории или None
    """
    # outputs/<slug>/<YYYYMMDD_HHMMSS>; берём последний по времени
    candidates = glob.glob(os.path.join(root, "*", "*"))
    if not candidates:
        return None
    
    # Фильтруем только директории
    candidates = [c for c in candidates if os.path.isdir(c)]
    if not candidates:
        return None
    
    candidates.sort()
    return candidates[-1]


@app.get("/slides", response_class=HTMLResponse)
async def list_slides():
    """
    Отображает HTML-страницу с предпросмотром последнего рендера
    """
    latest = latest_run_dir(OUTPUT_ROOT)
    if not latest:
        return "<h3>Нет слайдов. Сначала вызови POST /generate.</h3>"
    
    files = sorted(glob.glob(os.path.join(latest, "slide_*.png")))
    
    if not files:
        return "<h3>В последнем рендере нет слайдов.</h3>"
    
    # Загружаем манифест если есть
    manifest_path = os.path.join(latest, "manifest.json")
    manifest_info = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_info = json.load(f)
        except:
            pass
    
    title = manifest_info.get("title", "Карусель")
    template_id = manifest_info.get("template_id", "unknown")
    slides_total = manifest_info.get("slides_total", len(files))
    
    # Формируем HTML
    html_parts = [
        f'<html><head><meta charset="utf-8"><title>{title}</title></head><body>',
        f'<h1>{title}</h1>',
        f'<p><strong>Шаблон:</strong> {template_id} | <strong>Слайдов:</strong> {slides_total}</p>',
        f'<p><strong>Папка:</strong> <code>{os.path.relpath(latest, OUTPUT_ROOT).replace("\\", "/")}</code></p>',
        '<div style="display:flex;flex-wrap:wrap;gap:20px;margin:20px 0;">'
    ]
    
    for f in files:
        name = os.path.basename(f)
        rel = os.path.relpath(f, OUTPUT_ROOT).replace("\\", "/")
        html_parts.append(
            f'<div style="margin:12px;display:inline-block;text-align:center;border:1px solid #ddd;padding:10px;border-radius:8px;">'
            f'<img src="/outputs/{rel}" style="max-width:400px;display:block;margin:auto;border-radius:4px;">'
            f'<br><code style="font-size:12px;">{name}</code>'
            f'</div>'
        )
    
    html_parts.append('</div></body></html>')
    
    return "".join(html_parts)


@app.get("/carousel/{slug:path}/{timestamp}", response_class=HTMLResponse)
async def view_carousel(slug: str, timestamp: str):
    """
    Просмотр конкретной карусели по slug и timestamp
    """
    # FastAPI автоматически декодирует параметры пути, но на всякий случай декодируем еще раз
    slug_decoded = unquote(slug)
    # Нормализуем путь (убираем лишние слеши)
    slug_decoded = slug_decoded.strip("/").replace("\\", "/")
    carousel_dir = os.path.join(OUTPUT_ROOT, slug_decoded, timestamp)
    
    if not os.path.exists(carousel_dir):
        raise HTTPException(status_code=404, detail=f"Карусель не найдена: {slug_decoded}/{timestamp}")
    
    files = sorted(glob.glob(os.path.join(carousel_dir, "slide_*.png")))
    
    if not files:
        raise HTTPException(status_code=404, detail="В карусели нет слайдов")
    
    # Загружаем манифест
    manifest_path = os.path.join(carousel_dir, "manifest.json")
    manifest_info = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_info = json.load(f)
        except:
            pass
    
    title = manifest_info.get("title", "Карусель")
    template_id = manifest_info.get("template_id", "unknown")
    slides_total = manifest_info.get("slides_total", len(files))
    
    # Формируем HTML
    html_parts = [
        f'<html><head><meta charset="utf-8"><title>{title}</title></head><body>',
        f'<h1>{title}</h1>',
        f'<p><strong>Шаблон:</strong> {template_id} | <strong>Слайдов:</strong> {slides_total}</p>',
        f'<p><strong>Папка:</strong> <code>{slug_decoded}/{timestamp}</code></p>',
        '<div style="display:flex;flex-wrap:wrap;gap:20px;margin:20px 0;">'
    ]
    
    for f in files:
        name = os.path.basename(f)
        rel = os.path.relpath(f, OUTPUT_ROOT).replace("\\", "/")
        # URL-кодируем путь для изображений
        rel_encoded = "/".join(quote(part, safe="") for part in rel.split("/"))
        html_parts.append(
            f'<div style="margin:12px;display:inline-block;text-align:center;border:1px solid #ddd;padding:10px;border-radius:8px;">'
            f'<img src="/outputs/{rel_encoded}" style="max-width:400px;display:block;margin:auto;border-radius:4px;">'
            f'<br><code style="font-size:12px;">{name}</code>'
            f'</div>'
        )
    
    html_parts.append('</div></body></html>')
    
    return "".join(html_parts)


@app.post("/debug/image-gen")
async def debug_image_gen(prompt: str = "angry couple arguing, interior, dramatic, comic illustration"):
    """
    Health-check эндпоинт для тестирования генерации изображений
    """
    try:
        print(f"[debug] Starting image generation with prompt: '{prompt[:100]}...'")
        
        raw = await generate_image_bytes(prompt, width=1080, height=1350)
        print(f"[debug] got bytes: {len(raw)}")
        
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
        img = cover_fit(img, CANVAS_SIZE)
        
        print(f"[debug] image processed: {img.size} mode={img.mode}")
        
        out_root = OUTPUT_ROOT
        run_dir = make_run_dir(out_root, f"debug-{slugify(prompt)[:30]}")
        out_path = os.path.join(run_dir, "debug.png")
        img.save(out_path, "PNG")
        
        print(f"[debug] saved to: {out_path}")
        
        # Формируем относительный путь для URL
        # out_path находится в OUTPUT_ROOT, нужно получить путь относительно OUTPUT_ROOT
        rel_path = os.path.relpath(out_path, OUTPUT_ROOT)
        rel_path = rel_path.replace("\\", "/")
        
        return JSONResponse({
            "ok": True, 
            "size": list(img.size), 
            "mode": img.mode,
            "bytes_len": len(raw),
            "file": f"/outputs/{rel_path}"
        })
    except Exception as e:
        print(f"[debug] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "ok": False, 
            "error": str(e),
            "error_type": type(e).__name__
        }, status_code=500)


# ========== API для работы с шаблонами ==========

@app.get("/templates")
async def list_templates(category: Optional[str] = None):
    """Получить список всех шаблонов"""
    try:
        templates_list = template_manager.list_templates(category)
        return {"ok": True, "templates": templates_list}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/templates/simple")
async def list_templates_simple():
    """Получить упрощённый список шаблонов для главной страницы"""
    try:
        presets = template_manager.list_templates("presets")
        
        # Добавляем иконки и описания для каждого шаблона
        templates_info = {
            "instagram_carousel": {
                "icon": "📱",
                "name": "Instagram карусель", 
                "description": "Классический стиль с AI-фонами и комикс-иллюстрациями"
            },
            "photo_overlay": {
                "icon": "📸",
                "name": "Фото с оверлеем",
                "description": "Для собственных фотографий с градиентным текстом"
            },
            "ai_comic_split": {
                "icon": "🎨", 
                "name": "AI комикс",
                "description": "Картинка сверху, текст снизу - для AI-генерации"
            },
            "minimal_text": {
                "icon": "📝",
                "name": "Минимальный",
                "description": "Чистый дизайн без изображений, только типографика"
            }
        }
        
        result = []
        for preset in presets:
            template_id = preset["id"]
            if template_id in templates_info:
                info = templates_info[template_id]
                result.append({
                    "id": template_id,
                    "name": info["name"],
                    "description": info["description"], 
                    "icon": info["icon"],
                    "slides_count": preset["slides_count"]
                })
        
        return {"ok": True, "templates": result}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Получить конкретный шаблон"""
    try:
        template = template_manager.load_template(template_id)
        if not template:
            return JSONResponse({"ok": False, "error": "Шаблон не найден"}, status_code=404)
        
        return {"ok": True, "template": template.dict()}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/templates")
async def create_template(template_data: dict):
    """Создать новый шаблон"""
    try:
        # Валидируем данные
        is_valid, error_msg = template_manager.validate_template(template_data)
        if not is_valid:
            return JSONResponse({"ok": False, "error": f"Невалидный шаблон: {error_msg}"}, status_code=400)
        
        # Создаем шаблон
        template = CarouselTemplate(**template_data)
        
        # Сохраняем
        filepath = template_manager.save_template(template, "custom")
        
        return {"ok": True, "template_id": template.id, "saved_to": filepath}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.put("/templates/{template_id}")
async def update_template(template_id: str, template_data: dict):
    """Обновить существующий шаблон"""
    try:
        # Проверяем что шаблон существует
        existing = template_manager.load_template(template_id)
        if not existing:
            return JSONResponse({"ok": False, "error": "Шаблон не найден"}, status_code=404)
        
        # Убеждаемся что ID совпадает
        template_data["id"] = template_id
        
        # Валидируем данные
        is_valid, error_msg = template_manager.validate_template(template_data)
        if not is_valid:
            return JSONResponse({"ok": False, "error": f"Невалидный шаблон: {error_msg}"}, status_code=400)
        
        # Создаем и сохраняем обновленный шаблон
        template = CarouselTemplate(**template_data)
        filepath = template_manager.save_template(template, "custom")
        
        return {"ok": True, "template_id": template.id, "updated": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Удалить шаблон"""
    try:
        success = template_manager.delete_template(template_id, "custom")
        if not success:
            return JSONResponse({"ok": False, "error": "Шаблон не найден или не удален"}, status_code=404)
        
        return {"ok": True, "deleted": template_id}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/templates/{template_id}/duplicate")
async def duplicate_template(template_id: str, new_name: str = Form(...), new_id: Optional[str] = Form(None)):
    """Дублировать шаблон"""
    try:
        new_template = template_manager.duplicate_template(template_id, new_name, new_id)
        if not new_template:
            return JSONResponse({"ok": False, "error": "Исходный шаблон не найден"}, status_code=404)
        
        return {"ok": True, "new_template_id": new_template.id, "name": new_template.name}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/templates/{template_id}/preview")
async def preview_template(template_id: str, slide_id: Optional[str] = None):
    """Получить превью шаблона"""
    try:
        preview_img = await template_renderer.render_preview(template_id, slide_id)
        
        # Сохраняем превью во временную директорию
        preview_dir = os.path.join(OUTPUT_ROOT, "previews")
        os.makedirs(preview_dir, exist_ok=True)
        
        preview_filename = f"{template_id}_{slide_id or 'default'}.png"
        preview_path = os.path.join(preview_dir, preview_filename)
        preview_img.convert("RGB").save(preview_path, "PNG")
        
        # Формируем URL
        rel_path = f"previews/{preview_filename}"
        
        return {"ok": True, "preview_url": f"/outputs/{rel_path}"}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/render-template")
async def render_template_endpoint(
    template_id: str = Form(...),
    slides_content: str = Form(...)  # JSON строка с массивом RenderContent
):
    """Рендеринг карусели по шаблону"""
    try:
        # Парсим контент слайдов
        try:
            slides_data = json.loads(slides_content)
            slides_content_list = [RenderContent(**slide) for slide in slides_data]
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"Невалидный JSON контента: {e}"}, status_code=400)
        
        # Рендерим карусель
        images = await template_renderer.render_carousel(template_id, slides_content_list)
        
        # Сохраняем результат
        template = template_manager.load_template(template_id)
        title = template.name if template else template_id
        
        run_dir = make_run_dir(OUTPUT_ROOT, f"template-{title}")
        created_files = []
        
        # Создаем ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, img in enumerate(images):
                out_name = f"slide_{i+1:02d}.png"
                out_path = os.path.join(run_dir, out_name)
                
                # Сохраняем на диск
                img.convert("RGB").save(out_path, "PNG")
                created_files.append({"index": i+1, "file": out_name})
                
                # Добавляем в ZIP
                bio = io.BytesIO()
                img.convert("RGB").save(bio, "PNG")
                zf.writestr(out_name, bio.getvalue())
        
        # Сохраняем манифест
        save_manifest(run_dir, {
            "template_id": template_id,
            "template_name": title,
            "slides_total": len(images),
            "files": created_files
        })
        
        buf.seek(0)
        filename = f"carousel-{slugify(title)}.zip"
        
        return StreamingResponse(
            io.BytesIO(buf.read()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
        )
        
    except Exception as e:
        print(f"[render-template] ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/health")
async def health_check():
    """Простая проверка здоровья приложения"""
    return {"status": "ok", "message": "Instagram Carousel Generator is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8010, reload=True)



