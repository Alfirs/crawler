"""
Templates API routes
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Template

router = APIRouter()


class TemplateCreate(BaseModel):
    name: str
    category: Optional[str] = None
    text: str
    variables: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    text: str
    variables: Optional[List[str]]
    is_active: bool
    usage_count: int
    success_rate: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[TemplateResponse])
def list_templates(
    category: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """List all templates"""
    query = db.query(Template)
    
    if category:
        query = query.filter(Template.category == category)
    if active_only:
        query = query.filter(Template.is_active == True)
    
    templates = query.order_by(Template.usage_count.desc()).all()
    return templates


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    """Create a new template"""
    template = Template(
        name=data.name,
        category=data.category,
        text=data.text,
        variables=data.variables,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return template


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    """Get a specific template"""
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(template_id: int, data: TemplateCreate, db: Session = Depends(get_db)):
    """Update a template"""
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.name = data.name
    template.category = data.category
    template.text = data.text
    template.variables = data.variables
    template.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(template)
    
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    """Delete a template"""
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()


@router.post("/{template_id}/toggle-active")
def toggle_template_active(template_id: int, db: Session = Depends(get_db)):
    """Toggle template active status"""
    template = db.query(Template).filter(Template.id == template_id).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.is_active = not template.is_active
    db.commit()
    
    return {"id": template.id, "is_active": template.is_active}


@router.get("/categories/list")
def list_categories(db: Session = Depends(get_db)):
    """Get list of template categories"""
    from sqlalchemy import distinct
    
    categories = db.query(distinct(Template.category)).filter(
        Template.category != None
    ).all()
    
    return [c[0] for c in categories if c[0]]


# Default templates to seed
DEFAULT_TEMPLATES = [
    {
        "name": "Первый контакт - Бот",
        "category": "Bots_TG_WA_VK",
        "text": "Привет! Увидел, что вам нужен бот. Делаю ботов для Telegram/WhatsApp/VK уже 3 года — от простых автоответчиков до сложных интеграций с CRM. Могу показать примеры похожих проектов. Какие задачи бот должен решать?",
        "variables": ["project_type", "examples"]
    },
    {
        "name": "Первый контакт - Парсер",
        "category": "Parsing_Analytics_Reports",
        "text": "Привет! Заметил запрос на парсинг. Специализируюсь на сборе данных: сайты, маркетплейсы, соцсети. Работаю с обходом защит и большими объемами. Что именно нужно спарсить и в каком формате данные?",
        "variables": ["data_source", "format"]
    },
    {
        "name": "Первый контакт - Интеграция",
        "category": "Integrations_Sheets_CRM_n8n",
        "text": "Привет! Увидел, что нужна интеграция. Делаю связки сервисов: Bitrix24, amoCRM, 1C, Google Sheets, n8n, Make. Обычно первый результат через 2-3 дня. Какие системы нужно связать?",
        "variables": ["systems"]
    },
    {
        "name": "Follow-up мягкий",
        "category": "General",
        "text": "Привет! Писал пару дней назад по поводу {{project_type}}. Понимаю, что много дел — если вопрос еще актуален, рад обсудить детали. Если уже решили — тоже ок, удачи с проектом! 🙌",
        "variables": ["project_type"]
    },
    {
        "name": "Follow-up с ценностью",
        "category": "General",
        "text": "Привет! Подумал над вашей задачей — вижу, что можно {{benefit}}. Набросал примерный план, если интересно — скину. Это бесплатно, просто хочу понять задачу глубже.",
        "variables": ["benefit"]
    },
]


@router.post("/seed-defaults")
def seed_default_templates(db: Session = Depends(get_db)):
    """Seed default templates if none exist"""
    existing = db.query(Template).count()
    
    if existing > 0:
        return {"message": "Templates already exist", "count": existing}
    
    for tpl_data in DEFAULT_TEMPLATES:
        template = Template(**tpl_data)
        db.add(template)
    
    db.commit()
    
    return {"message": f"Created {len(DEFAULT_TEMPLATES)} default templates"}
