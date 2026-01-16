"""
API для админ-панели
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.generation import Generation, GenerationStatus
from app.models.template import Template

router = APIRouter()

# Pydantic модели
class UserStats(BaseModel):
    total_users: int
    active_users: int
    new_users_today: int
    new_users_this_week: int

class GenerationStats(BaseModel):
    total_generations: int
    video_generations: int
    carousel_generations: int
    completed_generations: int
    failed_generations: int
    pending_generations: int

class TemplateStats(BaseModel):
    total_templates: int
    public_templates: int
    video_templates: int
    carousel_templates: int

class AdminStats(BaseModel):
    users: UserStats
    generations: GenerationStats
    templates: TemplateStats

class UserManagement(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    daily_video_limit: int
    daily_carousel_limit: int
    instagram_connected: bool
    tiktok_connected: bool

class LimitUpdate(BaseModel):
    daily_video_limit: Optional[int] = None
    daily_carousel_limit: Optional[int] = None

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение статистики для админ-панели"""
    # Проверяем права администратора
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    # Статистика пользователей
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    
    new_users_today = db.query(User).filter(
        User.created_at >= today
    ).count()
    
    new_users_this_week = db.query(User).filter(
        User.created_at >= week_ago
    ).count()
    
    user_stats = UserStats(
        total_users=total_users,
        active_users=active_users,
        new_users_today=new_users_today,
        new_users_this_week=new_users_this_week
    )
    
    # Статистика генераций
    total_generations = db.query(Generation).count()
    video_generations = db.query(Generation).filter(Generation.type == "video").count()
    carousel_generations = db.query(Generation).filter(Generation.type == "carousel").count()
    completed_generations = db.query(Generation).filter(Generation.status == GenerationStatus.COMPLETED).count()
    failed_generations = db.query(Generation).filter(Generation.status == GenerationStatus.FAILED).count()
    pending_generations = db.query(Generation).filter(Generation.status == GenerationStatus.PENDING).count()
    
    generation_stats = GenerationStats(
        total_generations=total_generations,
        video_generations=video_generations,
        carousel_generations=carousel_generations,
        completed_generations=completed_generations,
        failed_generations=failed_generations,
        pending_generations=pending_generations
    )
    
    # Статистика шаблонов
    total_templates = db.query(Template).count()
    public_templates = db.query(Template).filter(Template.is_public == True).count()
    video_templates = db.query(Template).filter(Template.type == "video").count()
    carousel_templates = db.query(Template).filter(Template.type == "carousel").count()
    
    template_stats = TemplateStats(
        total_templates=total_templates,
        public_templates=public_templates,
        video_templates=video_templates,
        carousel_templates=carousel_templates
    )
    
    return AdminStats(
        users=user_stats,
        generations=generation_stats,
        templates=template_stats
    )

@router.get("/users", response_model=List[UserManagement])
async def get_users(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение списка пользователей"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    users = db.query(User).offset(skip).limit(limit).all()
    
    return [
        UserManagement(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            daily_video_limit=user.daily_video_limit,
            daily_carousel_limit=user.daily_carousel_limit,
            instagram_connected=user.instagram_connected,
            tiktok_connected=user.tiktok_connected
        )
        for user in users
    ]

@router.put("/users/{user_id}/limits")
async def update_user_limits(
    user_id: int,
    limits: LimitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление лимитов пользователя"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if limits.daily_video_limit is not None:
        user.daily_video_limit = limits.daily_video_limit
    if limits.daily_carousel_limit is not None:
        user.daily_carousel_limit = limits.daily_carousel_limit
    
    db.commit()
    
    return {"message": "Лимиты пользователя обновлены"}

@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Переключение активности пользователя"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.is_active = not user.is_active
    db.commit()
    
    return {
        "message": f"Пользователь {'активирован' if user.is_active else 'деактивирован'}",
        "is_active": user.is_active
    }

@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_all_templates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение всех шаблонов"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    templates = db.query(Template).all()
    
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "type": t.type,
            "is_public": t.is_public,
            "created_by": t.created_by,
            "created_at": t.created_at.isoformat()
        }
        for t in templates
    ]

@router.put("/templates/{template_id}/toggle-public")
async def toggle_template_public(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Переключение публичности шаблона"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    template.is_public = not template.is_public
    db.commit()
    
    return {
        "message": f"Шаблон {'опубликован' if template.is_public else 'скрыт'}",
        "is_public": template.is_public
    }

@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление шаблона"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    db.delete(template)
    db.commit()
    
    return {"message": "Шаблон удален"}

@router.get("/generations", response_model=List[Dict[str, Any]])
async def get_all_generations(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение всех генераций"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    generations = db.query(Generation).offset(skip).limit(limit).all()
    
    return [
        {
            "id": g.id,
            "user_id": g.user_id,
            "type": g.type.value,
            "status": g.status.value,
            "created_at": g.created_at.isoformat(),
            "started_at": g.started_at.isoformat() if g.started_at else None,
            "completed_at": g.completed_at.isoformat() if g.completed_at else None,
            "error_message": g.error_message
        }
        for g in generations
    ]

@router.delete("/generations/{generation_id}")
async def delete_generation(
    generation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление генерации"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    generation = db.query(Generation).filter(Generation.id == generation_id).first()
    if not generation:
        raise HTTPException(status_code=404, detail="Генерация не найдена")
    
    # Удаляем связанные файлы
    if generation.output_files:
        for file_path in generation.output_files:
            try:
                os.remove(file_path)
            except:
                pass
    
    db.delete(generation)
    db.commit()
    
    return {"message": "Генерация удалена"}































