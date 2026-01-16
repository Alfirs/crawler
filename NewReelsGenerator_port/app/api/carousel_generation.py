"""
API для генерации каруселей
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import shutil
import os
import zipfile

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.generation import Generation, CarouselGeneration, GenerationType, GenerationStatus
from app.models.template import Template
from app.services.carousel_service import CarouselGenerationService

router = APIRouter()

# Pydantic модели
class CarouselGenerationRequest(BaseModel):
    mode: str  # "backgrounds", "user_images", "ai_generated", "style_from_photo"
    template_id: Optional[int] = None
    background_images: Optional[List[str]] = None  # Для режима backgrounds
    user_images: Optional[List[str]] = None  # Для режима user_images
    ai_prompts: Optional[List[str]] = None  # Для режима ai_generated
    
    # Для режима style_from_photo
    style_image_path: Optional[str] = None  # Путь к загруженному референсному изображению
    slides_count: int = 5  # Общее количество слайдов (1 оригинал + N-1 сгенерированных)
    prompt_hint: Optional[str] = None  # Подсказка для содержания
    style_strength: float = 0.75  # Сила переноса стиля (0.0-1.0), по умолчанию 0.75 для более сильного стиля
    seed: Optional[int] = None  # Seed для воспроизводимости
    with_text_overlay: bool = True  # Применять ли оверлей с текстом
    
    text_content: List[Dict[str, Any]]  # Тексты для наложения
    count: int = 1

class CarouselGenerationResponse(BaseModel):
    id: int
    status: str
    output_files: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: str

class CarouselTemplateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    mask_x: int
    mask_y: int
    mask_width: int
    mask_height: int
    title_font: str
    title_size: int = 48
    text_color: str = "#FFFFFF"
    box_color: str = "#000000"
    box_alpha: int = 50

@router.post("/generate", response_model=CarouselGenerationResponse)
async def generate_carousel(
    request: CarouselGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Запуск генерации карусели"""
    
    # Проверяем лимиты пользователя
    if request.count > current_user.daily_carousel_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен дневной лимит генерации каруселей. Максимум: {current_user.daily_carousel_limit}"
        )
    
    # Валидация в зависимости от режима
    if request.mode == "backgrounds" and not request.background_images:
        raise HTTPException(status_code=400, detail="Для режима 'backgrounds' необходимо указать фоновые изображения")
    
    if request.mode == "user_images" and not request.user_images:
        raise HTTPException(status_code=400, detail="Для режима 'user_images' необходимо загрузить изображения")
    
    if request.mode == "ai_generated" and not request.ai_prompts:
        raise HTTPException(status_code=400, detail="Для режима 'ai_generated' необходимо указать промпты")
    
    if request.mode == "style_from_photo" and not request.style_image_path:
        raise HTTPException(status_code=400, detail="Для режима 'style_from_photo' необходимо загрузить референсное изображение")
    
    # Создаем запись о генерации
    generation = Generation(
        user_id=current_user.id,
        type=GenerationType.CAROUSEL,
        status=GenerationStatus.PENDING,
        config=request.dict()
    )
    
    db.add(generation)
    db.commit()
    db.refresh(generation)
    
    # Создаем детали генерации карусели
    carousel_gen = CarouselGeneration(
        generation_id=generation.id,
        mode=request.mode,
        background_images=request.background_images,
        user_images=request.user_images,
        ai_prompts=request.ai_prompts,
        template_id=request.template_id,
        text_content=request.text_content,
        # Для режима style_from_photo
        style_image_path=request.style_image_path,
        slides_count=request.slides_count,
        prompt_hint=request.prompt_hint,
        style_strength=str(request.style_strength),
        seed=request.seed
    )
    
    db.add(carousel_gen)
    db.commit()
    
    # Запускаем генерацию в фоне
    background_tasks.add_task(
        CarouselGenerationService.process_carousel_generation,
        generation.id,
        db
    )
    
    return CarouselGenerationResponse(
        id=generation.id,
        status=generation.status.value,
        created_at=generation.created_at.isoformat()
    )

@router.get("/generations", response_model=List[CarouselGenerationResponse])
async def get_user_carousel_generations(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка генераций каруселей пользователя"""
    generations = db.query(Generation).filter(
        Generation.user_id == current_user.id,
        Generation.type == GenerationType.CAROUSEL
    ).offset(skip).limit(limit).all()
    
    return [
        CarouselGenerationResponse(
            id=gen.id,
            status=gen.status.value,
            output_files=gen.output_files,
            error_message=gen.error_message,
            created_at=gen.created_at.isoformat()
        )
        for gen in generations
    ]

@router.get("/generations/{generation_id}", response_model=CarouselGenerationResponse)
async def get_carousel_generation(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение информации о конкретной генерации карусели"""
    generation = db.query(Generation).filter(
        Generation.id == generation_id,
        Generation.user_id == current_user.id,
        Generation.type == GenerationType.CAROUSEL
    ).first()
    
    if not generation:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    
    return CarouselGenerationResponse(
        id=generation.id,
        status=generation.status.value,
        output_files=generation.output_files,
        error_message=generation.error_message,
        created_at=generation.created_at.isoformat()
    )

@router.post("/templates", response_model=Dict[str, Any])
async def create_carousel_template(
    template_data: CarouselTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание шаблона для карусели"""
    template = Template(
        name=template_data.name,
        description=template_data.description,
        type="carousel",
        mask_x=template_data.mask_x,
        mask_y=template_data.mask_y,
        mask_width=template_data.mask_width,
        mask_height=template_data.mask_height,
        title_font=template_data.title_font,
        title_size=template_data.title_size,
        text_color=template_data.text_color,
        box_color=template_data.box_color,
        box_alpha=template_data.box_alpha,
        created_by=current_user.id
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return {
        "id": template.id,
        "name": template.name,
        "message": "Шаблон карусели успешно создан"
    }

@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_carousel_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение шаблонов каруселей пользователя"""
    templates = db.query(Template).filter(
        (Template.created_by == current_user.id) | (Template.is_public == True),
        Template.type == "carousel"
    ).all()
    
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "is_public": t.is_public,
            "created_at": t.created_at.isoformat()
        }
        for t in templates
    ]

@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Загрузка изображения для карусели"""
    # Проверяем расширение файла
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}"
        )
    
    # Создаем директорию для пользователя
    user_upload_dir = Path("uploads") / str(current_user.id) / "images"
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Сохраняем файл
    file_path = user_upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    return {
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content)
    }

@router.post("/ai-generate-images")
async def generate_ai_images(
    prompts: List[str],
    count_per_prompt: int = 1,
    current_user: User = Depends(get_current_user)
):
    """Генерация изображений с помощью AI"""
    if not prompts:
        raise HTTPException(status_code=400, detail="Необходимо указать промпты")
    
    # Здесь будет интеграция с AI сервисом для генерации изображений
    # Пока возвращаем заглушку
    return {
        "message": "AI генерация изображений будет реализована",
        "prompts": prompts,
        "count_per_prompt": count_per_prompt
    }

@router.post("/generate-texts")
async def generate_texts_for_carousel(
    idea: str,
    slides_count: int = 5,
    current_user: User = Depends(get_current_user)
):
    """
    Генерация текстов для карусели на основе идеи.
    Используется для создания text_content для режима style_from_photo.
    """
    if not idea or not idea.strip():
        raise HTTPException(status_code=400, detail="Необходимо указать идею карусели")
    
    if slides_count < 1 or slides_count > 20:
        raise HTTPException(status_code=400, detail="slides_count должен быть от 1 до 20")
    
    try:
        from app.services.text_gen import generate_carousel_text
        from app.services.nlp_utils import normalize_spaces
        
        # Генерируем тексты
        raw_text = generate_carousel_text(idea.strip(), slides_count=slides_count)
        data = json.loads(raw_text)
        
        if not isinstance(data, dict) or "slides" not in data:
            raise ValueError("Invalid response from text generator")
        
        # Формируем text_content для API
        text_content = []
        for slide in data["slides"][:slides_count]:
            entry = {
                "title": slide.get("title", ""),
                "description": "",
                "items": slide.get("bullets", [])
            }
            text_content.append(entry)
        
        return {
            "text_content": text_content,
            "slides_count": len(text_content),
            "idea": idea.strip()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации текстов: {str(e)}"
        )

@router.post("/upload-style-image")
async def upload_style_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Загрузка изображения для режима style_from_photo.
    Валидация: JPEG/PNG, макс 10MB
    """
    # Проверяем расширение файла
    allowed_extensions = ['.jpg', '.jpeg', '.png']
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла. Для style_from_photo разрешены: {', '.join(allowed_extensions)}"
        )
    
    # Читаем файл и проверяем размер
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    max_size_mb = 10
    
    if file_size_mb > max_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой: {file_size_mb:.2f}MB. Максимум: {max_size_mb}MB"
        )
    
    # Сохраняем в специальную директорию для style_from_photo
    style_upload_dir = Path("uploads") / "style_from_photo"
    style_upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем уникальное имя файла
    from uuid import uuid4
    unique_filename = f"{uuid4().hex}_{file.filename}"
    file_path = style_upload_dir / unique_filename
    
    # Сохраняем файл
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    
    return {
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
        "message": f"Style reference image uploaded successfully"
    }

@router.get("/backgrounds", response_model=List[Dict[str, Any]])
async def get_background_templates():
    """Получение готовых фоновых шаблонов"""
    # Здесь можно вернуть список готовых фоновых изображений
    return [
        {
            "id": "bg_1",
            "name": "Градиентный фон",
            "preview_url": "/static/backgrounds/bg_1_preview.jpg",
            "download_url": "/static/backgrounds/bg_1.jpg"
        },
        {
            "id": "bg_2", 
            "name": "Абстрактный фон",
            "preview_url": "/static/backgrounds/bg_2_preview.jpg",
            "download_url": "/static/backgrounds/bg_2.jpg"
        }
    ]


@router.get("/jobs/{job_id}/zip")
async def download_carousel_zip(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Скачивание карусели в формате ZIP архива.
    В архиве все слайды в порядке 01..NN.
    """
    # Получаем генерацию
    generation = db.query(Generation).filter(
        Generation.id == job_id,
        Generation.user_id == current_user.id,
        Generation.type == GenerationType.CAROUSEL
    ).first()
    
    if not generation:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if generation.status != GenerationStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {generation.status.value}, not completed"
        )
    
    if not generation.output_files:
        raise HTTPException(status_code=404, detail="Output files not found")
    
    # Создаем ZIP архив
    output_dir = Path(generation.output_files[0]).parent
    zip_path = output_dir / "result.zip"
    
    # Если архив уже существует, отдаем его
    if zip_path.exists():
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"carousel_{job_id}.zip"
        )
    
    # Создаем архив
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Сортируем файлы по имени
            sorted_files = sorted(generation.output_files)
            for i, file_path in enumerate(sorted_files, 1):
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    # Сохраняем в архиве с правильным порядковым номером
                    arcname = f"slide_{i:02d}.jpg"
                    zipf.write(file_path_obj, arcname)
        
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"carousel_{job_id}.zip"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ZIP archive: {str(e)}"
        )





























