"""
API для управления шаблонами
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.template import Template

router = APIRouter()

# Pydantic модели
class TemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    type: str
    is_public: bool
    created_by: int
    created_at: str
    # Настройки для видео
    mask_x: Optional[int] = None
    mask_y: Optional[int] = None
    mask_width: Optional[int] = None
    mask_height: Optional[int] = None
    caption_mask_x: Optional[int] = None
    caption_mask_y: Optional[int] = None
    caption_mask_width: Optional[int] = None
    caption_mask_height: Optional[int] = None
    title_font: Optional[str] = None
    title_size: Optional[int] = None
    caption_size: Optional[int] = None
    text_color: Optional[str] = None
    box_color: Optional[str] = None
    box_alpha: Optional[int] = None
    full_vertical: Optional[bool] = None
    gradient_height: Optional[int] = None
    gradient_strength: Optional[int] = None

class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    type: str  # "video" или "carousel"
    is_public: bool = False
    # Настройки для видео
    mask_x: Optional[int] = None
    mask_y: Optional[int] = None
    mask_width: Optional[int] = None
    mask_height: Optional[int] = None
    caption_mask_x: Optional[int] = None
    caption_mask_y: Optional[int] = None
    caption_mask_width: Optional[int] = None
    caption_mask_height: Optional[int] = None
    title_font: Optional[str] = None
    title_size: Optional[int] = None
    caption_size: Optional[int] = None
    text_color: Optional[str] = None
    box_color: Optional[str] = None
    box_alpha: Optional[int] = None
    full_vertical: Optional[bool] = None
    gradient_height: Optional[int] = None
    gradient_strength: Optional[int] = None

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    # Настройки для видео
    mask_x: Optional[int] = None
    mask_y: Optional[int] = None
    mask_width: Optional[int] = None
    mask_height: Optional[int] = None
    caption_mask_x: Optional[int] = None
    caption_mask_y: Optional[int] = None
    caption_mask_width: Optional[int] = None
    caption_mask_height: Optional[int] = None
    title_font: Optional[str] = None
    title_size: Optional[int] = None
    caption_size: Optional[int] = None
    text_color: Optional[str] = None
    box_color: Optional[str] = None
    box_alpha: Optional[int] = None
    full_vertical: Optional[bool] = None
    gradient_height: Optional[int] = None
    gradient_strength: Optional[int] = None

@router.get("/", response_model=List[TemplateResponse])
async def get_templates(
    template_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение шаблонов пользователя и публичных"""
    query = db.query(Template).filter(
        (Template.created_by == current_user.id) | (Template.is_public == True)
    )
    
    if template_type:
        query = query.filter(Template.type == template_type)
    
    templates = query.all()
    
    return [
        TemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            type=t.type,
            is_public=t.is_public,
            created_by=t.created_by,
            created_at=t.created_at.isoformat(),
            mask_x=t.mask_x,
            mask_y=t.mask_y,
            mask_width=t.mask_width,
            mask_height=t.mask_height,
            caption_mask_x=t.caption_mask_x,
            caption_mask_y=t.caption_mask_y,
            caption_mask_width=t.caption_mask_width,
            caption_mask_height=t.caption_mask_height,
            title_font=t.title_font,
            title_size=t.title_size,
            caption_size=t.caption_size,
            text_color=t.text_color,
            box_color=t.box_color,
            box_alpha=t.box_alpha,
            full_vertical=t.full_vertical,
            gradient_height=t.gradient_height,
            gradient_strength=t.gradient_strength
        )
        for t in templates
    ]

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение конкретного шаблона"""
    template = db.query(Template).filter(
        Template.id == template_id,
        (Template.created_by == current_user.id) | (Template.is_public == True)
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        type=template.type,
        is_public=template.is_public,
        created_by=template.created_by,
        created_at=template.created_at.isoformat(),
        mask_x=template.mask_x,
        mask_y=template.mask_y,
        mask_width=template.mask_width,
        mask_height=template.mask_height,
        caption_mask_x=template.caption_mask_x,
        caption_mask_y=template.caption_mask_y,
        caption_mask_width=template.caption_mask_width,
        caption_mask_height=template.caption_mask_height,
        title_font=template.title_font,
        title_size=template.title_size,
        caption_size=template.caption_size,
        text_color=template.text_color,
        box_color=template.box_color,
        box_alpha=template.box_alpha,
        full_vertical=template.full_vertical,
        gradient_height=template.gradient_height,
        gradient_strength=template.gradient_strength
    )

@router.post("/", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Создание нового шаблона"""
    # Проверяем, что шаблон с таким именем не существует у пользователя
    existing = db.query(Template).filter(
        Template.name == template_data.name,
        Template.created_by == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Шаблон с таким именем уже существует")
    
    template = Template(
        name=template_data.name,
        description=template_data.description,
        type=template_data.type,
        is_public=template_data.is_public,
        created_by=current_user.id,
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
        gradient_strength=template_data.gradient_strength
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        type=template.type,
        is_public=template.is_public,
        created_by=template.created_by,
        created_at=template.created_at.isoformat(),
        mask_x=template.mask_x,
        mask_y=template.mask_y,
        mask_width=template.mask_width,
        mask_height=template.mask_height,
        caption_mask_x=template.caption_mask_x,
        caption_mask_y=template.caption_mask_y,
        caption_mask_width=template.caption_mask_width,
        caption_mask_height=template.caption_mask_height,
        title_font=template.title_font,
        title_size=template.title_size,
        caption_size=template.caption_size,
        text_color=template.text_color,
        box_color=template.box_color,
        box_alpha=template.box_alpha,
        full_vertical=template.full_vertical,
        gradient_height=template.gradient_height,
        gradient_strength=template.gradient_strength
    )

@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Обновление шаблона"""
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    # Обновляем только переданные поля
    update_data = template_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    db.commit()
    db.refresh(template)
    
    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        type=template.type,
        is_public=template.is_public,
        created_by=template.created_by,
        created_at=template.created_at.isoformat(),
        mask_x=template.mask_x,
        mask_y=template.mask_y,
        mask_width=template.mask_width,
        mask_height=template.mask_height,
        caption_mask_x=template.caption_mask_x,
        caption_mask_y=template.caption_mask_y,
        caption_mask_width=template.caption_mask_width,
        caption_mask_height=template.caption_mask_height,
        title_font=template.title_font,
        title_size=template.title_size,
        caption_size=template.caption_size,
        text_color=template.text_color,
        box_color=template.box_color,
        box_alpha=template.box_alpha,
        full_vertical=template.full_vertical,
        gradient_height=template.gradient_height,
        gradient_strength=template.gradient_strength
    )

@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Удаление шаблона"""
    template = db.query(Template).filter(
        Template.id == template_id,
        Template.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    db.delete(template)
    db.commit()
    
    return {"message": "Шаблон удален"}

@router.post("/{template_id}/duplicate", response_model=TemplateResponse)
async def duplicate_template(
    template_id: int,
    new_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Дублирование шаблона"""
    original_template = db.query(Template).filter(
        Template.id == template_id,
        (Template.created_by == current_user.id) | (Template.is_public == True)
    ).first()
    
    if not original_template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    
    # Проверяем, что шаблон с новым именем не существует
    existing = db.query(Template).filter(
        Template.name == new_name,
        Template.created_by == current_user.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Шаблон с таким именем уже существует")
    
    # Создаем копию шаблона
    new_template = Template(
        name=new_name,
        description=original_template.description,
        type=original_template.type,
        is_public=False,  # Копия всегда приватная
        created_by=current_user.id,
        mask_x=original_template.mask_x,
        mask_y=original_template.mask_y,
        mask_width=original_template.mask_width,
        mask_height=original_template.mask_height,
        caption_mask_x=original_template.caption_mask_x,
        caption_mask_y=original_template.caption_mask_y,
        caption_mask_width=original_template.caption_mask_width,
        caption_mask_height=original_template.caption_mask_height,
        title_font=original_template.title_font,
        title_size=original_template.title_size,
        caption_size=original_template.caption_size,
        text_color=original_template.text_color,
        box_color=original_template.box_color,
        box_alpha=original_template.box_alpha,
        full_vertical=original_template.full_vertical,
        gradient_height=original_template.gradient_height,
        gradient_strength=original_template.gradient_strength
    )
    
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    
    return TemplateResponse(
        id=new_template.id,
        name=new_template.name,
        description=new_template.description,
        type=new_template.type,
        is_public=new_template.is_public,
        created_by=new_template.created_by,
        created_at=new_template.created_at.isoformat(),
        mask_x=new_template.mask_x,
        mask_y=new_template.mask_y,
        mask_width=new_template.mask_width,
        mask_height=new_template.mask_height,
        caption_mask_x=new_template.caption_mask_x,
        caption_mask_y=new_template.caption_mask_y,
        caption_mask_width=new_template.caption_mask_width,
        caption_mask_height=new_template.caption_mask_height,
        title_font=new_template.title_font,
        title_size=new_template.title_size,
        caption_size=new_template.caption_size,
        text_color=new_template.text_color,
        box_color=new_template.box_color,
        box_alpha=new_template.box_alpha,
        full_vertical=new_template.full_vertical,
        gradient_height=new_template.gradient_height,
        gradient_strength=new_template.gradient_strength
    )































