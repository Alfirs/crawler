"""
Менеджер шаблонов - загрузка, сохранение, валидация
"""
from __future__ import annotations
import os
import json
import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..schemas.template_schema import CarouselTemplate, SlideTemplate


class TemplateManager:
    """Управление шаблонами слайдов"""
    
    def __init__(self, templates_dir: str = "app/static/templates"):
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем подпапки
        (self.templates_dir / "presets").mkdir(exist_ok=True)
        (self.templates_dir / "custom").mkdir(exist_ok=True)
    
    def save_template(self, template: CarouselTemplate, category: str = "custom") -> str:
        """
        Сохранить шаблон в JSON файл
        
        Args:
            template: Шаблон карусели
            category: Категория ("presets" или "custom")
            
        Returns:
            Путь к сохраненному файлу
        """
        # Обновляем timestamp
        now = datetime.datetime.now().isoformat()
        if not template.created_at:
            template.created_at = now
        template.updated_at = now
        
        # Определяем путь к файлу
        filename = f"{template.id}.json"
        filepath = self.templates_dir / category / filename
        
        # Сохраняем
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template.dict(), f, ensure_ascii=False, indent=2)
        
        print(f"[template_manager] Сохранен: {filepath}")
        return str(filepath)
    
    def load_template(self, template_id: str) -> Optional[CarouselTemplate]:
        """
        Загрузить шаблон по ID
        
        Args:
            template_id: ID шаблона
            
        Returns:
            Шаблон или None если не найден
        """
        # Ищем в presets и custom
        for category in ["presets", "custom"]:
            filepath = self.templates_dir / category / f"{template_id}.json"
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    template = CarouselTemplate(**data)
                    print(f"[template_manager] Загружен: {filepath}")
                    return template
                    
                except Exception as e:
                    print(f"[template_manager] Ошибка загрузки {filepath}: {e}")
                    continue
        
        print(f"[template_manager] Шаблон {template_id} не найден")
        return None
    
    def list_templates(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Список всех шаблонов
        
        Args:
            category: Фильтр по категории ("presets", "custom" или None для всех)
            
        Returns:
            Список метаданных шаблонов
        """
        templates = []
        categories = [category] if category else ["presets", "custom"]
        
        for cat in categories:
            cat_dir = self.templates_dir / cat
            if not cat_dir.exists():
                continue
                
            for filepath in cat_dir.glob("*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Извлекаем только метаданные
                    metadata = {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "description": data.get("description"),
                        "tags": data.get("tags", []),
                        "slides_count": len(data.get("slides", [])),
                        "category": cat,
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at")
                    }
                    templates.append(metadata)
                    
                except Exception as e:
                    print(f"[template_manager] Ошибка чтения {filepath}: {e}")
                    continue
        
        # Сортируем по дате обновления
        templates.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return templates
    
    def delete_template(self, template_id: str, category: str = "custom") -> bool:
        """
        Удалить шаблон
        
        Args:
            template_id: ID шаблона
            category: Категория шаблона
            
        Returns:
            True если удален успешно
        """
        filepath = self.templates_dir / category / f"{template_id}.json"
        
        if filepath.exists():
            try:
                filepath.unlink()
                print(f"[template_manager] Удален: {filepath}")
                return True
            except Exception as e:
                print(f"[template_manager] Ошибка удаления {filepath}: {e}")
                return False
        
        print(f"[template_manager] Шаблон {template_id} не найден для удаления")
        return False
    
    def validate_template(self, data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Валидация данных шаблона
        
        Args:
            data: Данные шаблона (dict)
            
        Returns:
            (is_valid, error_message)
        """
        try:
            CarouselTemplate(**data)
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def duplicate_template(self, template_id: str, new_name: str, new_id: Optional[str] = None) -> Optional[CarouselTemplate]:
        """
        Дублировать существующий шаблон
        
        Args:
            template_id: ID исходного шаблона
            new_name: Название копии
            new_id: ID копии (если None, создается автоматически)
            
        Returns:
            Новый шаблон или None при ошибке
        """
        # Загружаем исходный шаблон
        original = self.load_template(template_id)
        if not original:
            return None
        
        # Создаем копию
        new_template_id = new_id or f"{template_id}_copy_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Обновляем метаданные
        template_data = original.dict()
        template_data["id"] = new_template_id
        template_data["name"] = new_name
        template_data["created_at"] = None  # Будет установлено при сохранении
        template_data["updated_at"] = None
        
        # Создаем новый объект
        new_template = CarouselTemplate(**template_data)
        
        # Сохраняем в custom
        self.save_template(new_template, "custom")
        
        print(f"[template_manager] Дублирован {template_id} -> {new_template_id}")
        return new_template


# Глобальный экземпляр
template_manager = TemplateManager()


def create_instagram_preset() -> CarouselTemplate:
    """Создать базовый пресет Instagram карусели"""
    
    # Обложка
    cover_slide = SlideTemplate(
        id="cover",
        name="Обложка",
        canvas_width=1080,
        canvas_height=1350,
        background={"type": "solid", "color": "#000000"},
        zones=[
            {
                "id": "cover_bg", 
                "type": "image",
                "x": 0, "y": 0, "width": 1080, "height": 1350,
                "source": "uploaded",
                "fit_mode": "cover",
                "z_index": 1
            },
            {
                "id": "cover_title",
                "type": "text",
                "x": 80, "y": 930, "width": 920, "height": 320,
                "content": "{{title}}",
                "font_family": "Inter-Bold", 
                "font_size": 72,
                "font_color": "#FFFFFF",
                "align": "left",
                "z_index": 2,
                "formatting": []
            },
            {
                "id": "swipe_hint",
                "type": "text", 
                "x": 80, "y": 1270, "width": 200, "height": 50,
                "content": "Листай дальше",
                "font_family": "Inter-Regular",
                "font_size": 40,
                "font_color": "#D0D0D0", 
                "align": "left",
                "z_index": 2,
                "formatting": []
            }
        ]
    )
    
    # Контент-слайд  
    content_slide = SlideTemplate(
        id="content",
        name="Контент",
        canvas_width=1080, 
        canvas_height=1350,
        background={"type": "solid", "color": "#FFFFFF"},
        zones=[
            {
                "id": "content_bg",
                "type": "image", 
                "x": 0, "y": 0, "width": 1080, "height": 1350,
                "source": "ai_generated",
                "ai_prompt": "{{slide_text}}, comic illustration style, vibrant colors, no text",
                "fit_mode": "cover",
                "z_index": 1
            },
            {
                "id": "nickname",
                "type": "text",
                "x": 80, "y": 60, "width": 300, "height": 50, 
                "content": "@antonsharafutdin",
                "font_family": "Inter-Regular",
                "font_size": 40,
                "font_color": "#9E9E9E",
                "align": "left", 
                "z_index": 3,
                "formatting": []
            },
            {
                "id": "page_number",
                "type": "text",
                "x": 930, "y": 60, "width": 70, "height": 50,
                "content": "{{page_num}}",
                "font_family": "Inter-Regular", 
                "font_size": 40,
                "font_color": "#9E9E9E",
                "align": "right",
                "z_index": 3,
                "formatting": []
            },
            {
                "id": "content_title", 
                "type": "text",
                "x": 80, "y": 200, "width": 920, "height": 400,
                "content": "{{headline}}",
                "font_family": "Inter-Bold",
                "font_size": 80,
                "font_color": "#111111", 
                "align": "left",
                "z_index": 3,
                "auto_fit": True,
                "formatting": []
            },
            {
                "id": "content_body",
                "type": "text",
                "x": 80, "y": 640, "width": 920, "height": 550,
                "content": "{{body_text}}", 
                "font_family": "Inter-Regular",
                "font_size": 45,
                "font_color": "#111111",
                "align": "left",
                "z_index": 3,
                "line_height": 1.3,
                "formatting": []
            },
            {
                "id": "swipe_hint_content", 
                "type": "text",
                "x": 80, "y": 1270, "width": 200, "height": 50,
                "content": "Листай дальше",
                "font_family": "Inter-Regular",
                "font_size": 36,
                "font_color": "#D0D0D0",
                "align": "left",
                "z_index": 3,
                "formatting": []
            }
        ]
    )
    
    return CarouselTemplate(
        id="instagram_carousel",
        name="Instagram карусель",
        description="Классический шаблон Instagram карусели с обложкой и контент-слайдами",
        slides=[cover_slide, content_slide],
        tags=["instagram", "социальные сети", "карусель", "комикс"]
    )


