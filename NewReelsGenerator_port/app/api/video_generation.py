"""
API для генерации видео (Reels)
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.generation import Generation, VideoGeneration, GenerationType, GenerationStatus
from app.models.template import Template
from app.services.video_service import VideoGenerationService

router = APIRouter()

# Pydantic модели
class VideoGenerationRequest(BaseModel):
    template_id: Optional[int] = None
    video_files: List[str]  # Пути к видео файлам
    music_file: Optional[str] = None
    music_mode: str = "random"  # "random", "smart", "none"
    keep_original_audio: bool = False
    titles: List[str]
    descriptions: List[str]
    count: int = 1
    auto_generation: bool = False
    daily_limit: Optional[int] = None

class VideoGenerationResponse(BaseModel):
    id: int
    status: str
    output_files: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: str

class VideoTemplateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    mask_x: int
    mask_y: int
    mask_width: int
    mask_height: int
    caption_mask_x: int
    caption_mask_y: int
    caption_mask_width: int
    caption_mask_height: int
    title_font: str
    title_size: int = 48
    caption_size: int = 36
    text_color: str = "#FFFFFF"
    box_color: str = "#000000"
    box_alpha: int = 50
    full_vertical: bool = False
    gradient_height: Optional[int] = None
    gradient_strength: Optional[int] = None

@router.post("/generate", response_model=VideoGenerationResponse)
async def generate_videos(
    request: VideoGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Запуск генерации видео"""
    
    # Проверяем лимиты пользователя
    if request.auto_generation and request.daily_limit:
        if request.daily_limit > current_user.daily_video_limit:
            raise HTTPException(
                status_code=400,
                detail=f"Превышен дневной лимит генерации. Максимум: {current_user.daily_video_limit}"
            )
    
    # Создаем запись о генерации
    generation = Generation(
        user_id=current_user.id,
        type=GenerationType.VIDEO,
        status=GenerationStatus.PENDING,
        config=request.dict()
    )
    
    db.add(generation)
    db.commit()
    db.refresh(generation)
    
    # Создаем детали генерации видео
    video_gen = VideoGeneration(
        generation_id=generation.id,
        video_files=request.video_files,
        music_file=request.music_file,
        titles=request.titles,
        descriptions=request.descriptions,
        template_id=request.template_id,
        music_mode=request.music_mode,
        keep_original_audio=request.keep_original_audio
    )
    
    db.add(video_gen)
    db.commit()
    
    # Запускаем генерацию в фоне
    background_tasks.add_task(
        VideoGenerationService.process_video_generation,
        generation.id,
        db
    )
    
    return VideoGenerationResponse(
        id=generation.id,
        status=generation.status.value,
        created_at=generation.created_at.isoformat()
    )

@router.get("/generations", response_model=List[VideoGenerationResponse])
async def get_user_generations(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка генераций пользователя"""
    generations = db.query(Generation).filter(
        Generation.user_id == current_user.id,
        Generation.type == GenerationType.VIDEO
    ).offset(skip).limit(limit).all()
    
    return [
        VideoGenerationResponse(
            id=gen.id,
            status=gen.status.value,
            output_files=gen.output_files,
            error_message=gen.error_message,
            created_at=gen.created_at.isoformat()
        )
        for gen in generations
    ]

@router.get("/generations/{generation_id}", response_model=VideoGenerationResponse)
async def get_generation(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение информации о конкретной генерации"""
    generation = db.query(Generation).filter(
        Generation.id == generation_id,
        Generation.user_id == current_user.id,
        Generation.type == GenerationType.VIDEO
    ).first()
    
    if not generation:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    
    return VideoGenerationResponse(
        id=generation.id,
        status=generation.status.value,
        output_files=generation.output_files,
        error_message=generation.error_message,
        created_at=generation.created_at.isoformat()
    )

@router.post("/templates", response_model=Dict[str, Any])
async def create_template(
    template_data: VideoTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание шаблона для видео"""
    template = Template(
        name=template_data.name,
        description=template_data.description,
        type="video",
        mask_x=template_data.mask_x,
        mask_y=template_data.mask_y,
        mask_width=template_data.mask_width,
        mask_height=template_data.mask_height,
        caption_mask_x=template_data.caption_mask_x,
        caption_mask_y=template_data.caption_mask_y,
        caption_mask_width=template_data.caption_mask_width,
        caption_mask_height=template_data.caption_mask_height,
        title_font=template_data.title_font,
        title_size=template_data.title_size,
        caption_size=template_data.caption_size,
        text_color=template_data.text_color,
        box_color=template_data.box_color,
        box_alpha=template_data.box_alpha,
        full_vertical=template_data.full_vertical,
        gradient_height=template_data.gradient_height,
        gradient_strength=template_data.gradient_strength,
        created_by=current_user.id
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return {
        "id": template.id,
        "name": template.name,
        "message": "Шаблон успешно создан"
    }

@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение шаблонов пользователя"""
    templates = db.query(Template).filter(
        (Template.created_by == current_user.id) | (Template.is_public == True),
        Template.type == "video"
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

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Загрузка видео файла"""
    # Проверяем расширение файла
    allowed_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}"
        )
    
    # Создаем директорию для пользователя
    user_upload_dir = Path("uploads") / str(current_user.id)
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

@router.post("/auto-generation/setup")
async def setup_auto_generation(
    daily_count: int,
    start_time: str,  # HH:MM format
    platforms: List[str],  # ["instagram", "tiktok"]
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Настройка автогенерации"""
    if daily_count > current_user.daily_video_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен дневной лимит. Максимум: {current_user.daily_video_limit}"
        )
    
    # Здесь можно добавить логику настройки автогенерации
    # Например, создание cron-задач или записей в БД
    
    return {
        "message": "Автогенерация настроена",
        "daily_count": daily_count,
        "start_time": start_time,
        "platforms": platforms
    }































