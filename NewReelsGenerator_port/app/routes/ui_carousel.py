from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
import os
import uuid
from typing import Optional
from uuid import uuid4

from app.templates_manager.models import TemplateMetadata
from app.templates_manager.service import TemplateService
from app.auto_generator import auto_generator
from app.services.text_gen import generate_carousel_text
import json


router = APIRouter(tags=["UI"], include_in_schema=False)
templates = Jinja2Templates(directory="templates")


@router.post("/api/carousel/upload-style-image")
async def upload_style_image(file: UploadFile = File(...)):
    """Принимает изображение-референс для карусели и сохраняет его."""
    folder = os.path.join("uploads", "style_refs")
    os.makedirs(folder, exist_ok=True)
    filename = f"temp_{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(folder, filename)
    
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    print(f"[UPLOAD] style image saved -> {filepath}")
    return {"status": "ok", "path": filepath}


@router.post("/api/carousel/generate-texts")
async def generate_texts(request: Request):
    """Генерация текстов слайдов по идее пользователя."""
    data = await request.json()
    idea = data.get("idea", "").strip()
    if not idea:
        return {"error": "missing idea"}

    try:
        text = generate_carousel_text(idea)
        print(f"[TEXT_GEN] Generated carousel text for idea: {idea}")
        return {"slides_text": text}
    except Exception as e:
        print(f"[TEXT_GEN] Error: {e}")
        return {"error": "text generation failed"}


@router.post("/api/carousel/generate")
async def api_generate_carousel(request: Request):
    """
    Финальная генерация карусели (режим style_from_photo и др.).
    Принимает JSON с полями:
      - mode: str (например, "style_from_photo")
      - idea: str
      - slides_count: int
      - style_image_path: str (путь, полученный ранее от upload-style-image)
    """
    data = await request.json()
    mode = data.get("mode", "style_from_photo")
    idea = data.get("idea", "").strip()
    slides_count = int(data.get("slides_count", 3))
    style_image_path = data.get("style_image_path")

    if not style_image_path or not os.path.exists(style_image_path):
        return {"error": "missing or invalid style_image_path"}

    print(f"[CAROUSEL] mode={mode}, idea='{idea}', slides={slides_count}, style='{style_image_path}'")

    try:
        # Генерируем слайды
        from app.services.carousel_service import build_carousel_slides
        temp_slides = build_carousel_slides(style_image_path, slides_count)
        print(f"[CAROUSEL] Generated {len(temp_slides)} slides successfully")
        
        # Создаём generation_id и папку для сохранения
        generation_id = uuid.uuid4().hex
        output_folder = os.path.join("output", generation_id)
        os.makedirs(output_folder, exist_ok=True)
        
        # Копируем слайды в постоянную папку
        final_slides = []
        for i, temp_slide_path in enumerate(temp_slides, 1):
            if os.path.exists(temp_slide_path):
                slide_filename = f"slide_{i:02d}.png"
                final_slide_path = os.path.join(output_folder, slide_filename)
                
                # Копируем файл (не перемещаем, чтобы не повредить кэш)
                shutil.copy2(temp_slide_path, final_slide_path)
                final_slides.append(final_slide_path)
            else:
                print(f"[CAROUSEL] Warning: slide {i} not found at {temp_slide_path}")
        
        print(f"[CAROUSEL] Saved generation -> {output_folder}/")
        
        response = {
            "status": "ok", 
            "generation_id": generation_id,
            "slides": final_slides
        }
        print(f"[CAROUSEL] RESPONSE: {json.dumps(response, ensure_ascii=False, indent=2)}")
        return response
        
    except Exception as e:
        print(f"[CAROUSEL] Error: {e}")
        return {"error": str(e)}


@router.get("/api/carousel/generations/{gen_id}")
async def get_generation(gen_id: str):
    """Получение сохранённой генерации по ID."""
    if not gen_id or gen_id in {"undefined", "null"}:
        raise HTTPException(status_code=422, detail="invalid generation_id")
    
    folder = os.path.join("output", gen_id)
    if not os.path.exists(folder):
        raise HTTPException(status_code=404, detail="generation not found")
    
    try:
        files = sorted(os.listdir(folder))
        slides = [os.path.join(folder, f) for f in files if f.endswith(('.png', '.jpg', '.jpeg'))]
        return {"slides": slides}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _render_index(
    request: Request,
    *,
    result: Optional[dict] = None,
    message: Optional[str] = None,
    selected_template: Optional[TemplateMetadata] = None,
    img_warning: bool = False,
):
    stored_templates = TemplateService.list_templates()
    context = {
        "request": request,
        "result": result,
        "message": message,
        "img_warning": img_warning,
        "stored_templates": stored_templates,
        "selected_template": selected_template,
    }
    return templates.TemplateResponse("carousel_index.html", context)


def _store_temp_style_image(upload: UploadFile) -> str:
    temp_dir = Path("uploads") / "style_refs"
    temp_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "style_ref.png").suffix or ".png"
    destination = temp_dir / f"temp_{uuid4().hex}{suffix}"
    upload.file.seek(0)
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return str(destination.resolve())


@router.get("/carousel", response_class=HTMLResponse)
async def get_carousel(request: Request):
    template_name = request.query_params.get("template")
    selected_template = TemplateService.get_template(template_name) if template_name else None
    return _render_index(request, selected_template=selected_template)


@router.post("/carousel", response_class=HTMLResponse)
async def post_carousel(
    request: Request,
    idea: str = Form(...),
    slides_count: int = Form(4),
    style_image: UploadFile | None = File(None),
    username: str | None = Form(None),
    template_name: str | None = Form(None),
):
    selected_template = TemplateService.get_template(template_name) if template_name else None

    username_value = (username or (selected_template.username if selected_template else None) or "@username").strip()
    try:
        slides_count_value = int(slides_count)
    except (TypeError, ValueError):
        slides_count_value = selected_template.slides_count if selected_template else 4
    slides_count_value = max(1, slides_count_value)

    style_ref: Optional[str] = None
    if style_image and style_image.filename:
        style_ref = _store_temp_style_image(style_image)
    elif selected_template:
        style_ref = selected_template.style_ref

    result_data = TemplateService.generate_carousel(
        idea=idea,
        slides_count=slides_count_value,
        username=username_value,
        style_ref=style_ref,
    )

    slides_struct = result_data.get("slides_struct") or result_data.get("slides") or []
    slides_debug = [
        {
            "type": slide.get("type"),
            "title": slide.get("title"),
            "items": list(slide.get("items", [])),
            "body": slide.get("body", ""),
        }
        for slide in slides_struct
    ]

    result = {
        "message": "Carousel generated successfully.",
        "slides": result_data.get("slides", []),
        "debug_mode": result_data.get("debug_mode"),
        "previews": result_data.get("previews", []),
        "slides_debug": slides_debug,
    }

    return _render_index(
        request,
        result=result,
        message="Carousel generated successfully.",
        selected_template=selected_template,
        img_warning=False,
    )


@router.post("/save_template", response_class=HTMLResponse)
async def save_template(
    request: Request,
    idea: str = Form(...),
    slides_count: int = Form(4),
    style_image: UploadFile | None = File(None),
    username: str | None = Form(None),
    template_name: str | None = Form(None),
    auto_daily: Optional[str] = Form(None),
):
    try:
        metadata = TemplateService.save_template(
            base_prompt=idea,
            slides_count=slides_count,
            username=(username or "@username"),
            style_image=style_image,
            template_name=template_name,
            auto_generate_daily=bool(auto_daily),
        )
    except ValueError as exc:
        return _render_index(request, message=str(exc))

    if metadata.auto_generate_daily or auto_daily:
        await auto_generator.start()
        metadata = TemplateService.set_auto_daily(metadata.name, True) or metadata

    message = "Template saved."
    if metadata.auto_generate_daily:
        message += " Daily auto-generation enabled."

    return _render_index(request, message=message, selected_template=metadata)


@router.post("/generate_from_template", response_class=HTMLResponse)
async def generate_from_template(
    request: Request,
    template_name: str = Form(...),
    count: int = Form(5),
):
    template = TemplateService.get_template(template_name)
    if not template:
        return _render_index(request, message="Template not found.")

    outputs = TemplateService.generate_batch_from_template(template, count=count)
    previews = []
    if outputs:
        previews = [f"/{p}" for p in sorted(outputs[-1].glob("slide_*.png"))[:3]]

    message = f"Generated {len(outputs)} carousels from template {template.name}."
    result = {"message": message, "previews": previews}
    return _render_index(request, result=result, message=message)


@router.post("/toggle_auto_template", response_class=HTMLResponse)
async def toggle_auto_template(
    request: Request,
    template_name: str = Form(...),
    enable: int = Form(...),
):
    template = TemplateService.set_auto_daily(template_name, bool(enable))
    if not template:
        return _render_index(request, message="Template not found.")

    if template.auto_generate_daily:
        await auto_generator.start()
        message = f"Daily auto-generation enabled for template {template.name}."
    else:
        message = f"Daily auto-generation disabled for template {template.name}."

    return _render_index(request, message=message, selected_template=template)
