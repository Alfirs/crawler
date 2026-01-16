"""
Схемы данных для системы шаблонов слайдов
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum


class ZoneType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    SHAPE = "shape"


class BackgroundType(str, Enum):
    SOLID = "solid"
    GRADIENT = "gradient" 
    IMAGE = "image"


class ImageSource(str, Enum):
    AI_GENERATED = "ai_generated"
    UPLOADED = "uploaded"
    URL = "url"


class TextAlign(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class FormattingEffect(str, Enum):
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    HIGHLIGHT = "highlight"
    SHADOW = "shadow"
    STROKE = "stroke"


# Базовые компоненты зон
class Zone(BaseModel):
    """Базовая зона на слайде"""
    id: str = Field(..., description="Уникальный ID зоны")
    type: ZoneType
    x: int = Field(ge=0, description="X координата (пиксели)")
    y: int = Field(ge=0, description="Y координата (пиксели)")
    width: int = Field(gt=0, description="Ширина (пиксели)")
    height: int = Field(gt=0, description="Высота (пиксели)")
    z_index: int = Field(default=1, description="Слой (больше = выше)")


class TextFormatting(BaseModel):
    """Форматирование текста"""
    effect: FormattingEffect
    value: Optional[str] = None  # для highlight - цвет, для stroke - толщина и цвет
    
    class Config:
        schema_extra = {
            "examples": [
                {"effect": "bold"},
                {"effect": "highlight", "value": "#FFD700"},
                {"effect": "stroke", "value": "2px #000000"}
            ]
        }


class TextZone(Zone):
    """Зона с текстом"""
    type: Literal[ZoneType.TEXT] = ZoneType.TEXT
    content: str = Field(..., description="Текст содержимое")
    font_family: str = Field(default="Inter-Regular", description="Семейство шрифта")
    font_size: int = Field(default=48, ge=8, le=200, description="Размер шрифта")
    font_color: str = Field(default="#000000", description="Цвет текста (hex)")
    line_height: float = Field(default=1.2, ge=0.8, le=3.0, description="Межстрочный интервал")
    align: TextAlign = Field(default=TextAlign.LEFT, description="Выравнивание")
    formatting: List[TextFormatting] = Field(default_factory=list, description="Эффекты форматирования")
    auto_fit: bool = Field(default=True, description="Автоподбор размера шрифта")
    
    @validator('font_color')
    def validate_color(cls, v):
        if not (v.startswith('#') and len(v) in [4, 7]):
            raise ValueError('Цвет должен быть в формате #RGB или #RRGGBB')
        return v


class ImageZone(Zone):
    """Зона с изображением"""
    type: Literal[ZoneType.IMAGE] = ZoneType.IMAGE
    source: ImageSource = Field(..., description="Источник изображения")
    
    # Для AI-генерации
    ai_prompt: Optional[str] = Field(None, description="Промт для AI генерации")
    ai_style: Optional[str] = Field(None, description="Стиль генерации")
    
    # Для загруженных файлов  
    uploaded_path: Optional[str] = Field(None, description="Путь к загруженному файлу")
    
    # Для URL
    image_url: Optional[str] = Field(None, description="URL изображения")
    
    # Настройки отображения
    fit_mode: Literal["cover", "contain", "stretch"] = Field(default="cover", description="Режим масштабирования")
    blur_radius: float = Field(default=0, ge=0, le=20, description="Радиус размытия")
    opacity: float = Field(default=1.0, ge=0, le=1, description="Прозрачность")


class ShapeZone(Zone):
    """Зона с геометрической фигурой"""
    type: Literal[ZoneType.SHAPE] = ZoneType.SHAPE
    shape_type: Literal["rectangle", "circle", "line"] = Field(..., description="Тип фигуры")
    fill_color: Optional[str] = Field(None, description="Цвет заливки")
    stroke_color: Optional[str] = Field(None, description="Цвет контура")
    stroke_width: int = Field(default=0, ge=0, description="Толщина контура")
    border_radius: int = Field(default=0, ge=0, description="Радиус скругления (для прямоугольника)")


# Фоны слайдов
class SolidBackground(BaseModel):
    """Сплошной цвет фона"""
    type: Literal[BackgroundType.SOLID] = BackgroundType.SOLID
    color: str = Field(..., description="Цвет фона (hex)")


class GradientBackground(BaseModel):
    """Градиентный фон"""
    type: Literal[BackgroundType.GRADIENT] = BackgroundType.GRADIENT
    colors: List[str] = Field(..., min_items=2, description="Цвета градиента")
    direction: Literal["vertical", "horizontal", "diagonal"] = Field(default="vertical")
    angle: Optional[int] = Field(None, ge=0, lt=360, description="Угол градиента (градусы)")


class ImageBackground(BaseModel):
    """Изображение как фон"""
    type: Literal[BackgroundType.IMAGE] = BackgroundType.IMAGE
    source: ImageSource
    ai_prompt: Optional[str] = None
    uploaded_path: Optional[str] = None
    image_url: Optional[str] = None
    fit_mode: Literal["cover", "contain", "stretch"] = Field(default="cover")
    blur_radius: float = Field(default=0, ge=0, le=20)
    opacity: float = Field(default=1.0, ge=0, le=1)


Background = Union[SolidBackground, GradientBackground, ImageBackground]


# Слайд и шаблон
class SlideTemplate(BaseModel):
    """Шаблон одного слайда"""
    id: str = Field(..., description="ID слайда")
    name: str = Field(..., description="Название слайда")
    zones: List[Union[TextZone, ImageZone, ShapeZone]] = Field(..., description="Зоны на слайде")
    background: Background = Field(..., description="Фон слайда")
    canvas_width: int = Field(default=1080, description="Ширина холста")
    canvas_height: int = Field(default=1350, description="Высота холста")


class CarouselTemplate(BaseModel):
    """Шаблон карусели"""
    id: str = Field(..., description="ID шаблона")
    name: str = Field(..., description="Название шаблона")
    description: Optional[str] = Field(None, description="Описание шаблона")
    slides: List[SlideTemplate] = Field(..., min_items=1, description="Слайды")
    tags: List[str] = Field(default_factory=list, description="Теги для поиска")
    created_at: Optional[str] = Field(None, description="Дата создания")
    updated_at: Optional[str] = Field(None, description="Дата обновления")
    
    class Config:
        schema_extra = {
            "example": {
                "id": "instagram_carousel_v1",
                "name": "Instagram карусель",
                "description": "Классический шаблон Instagram карусели с обложкой и контент-слайдами",
                "slides": [
                    {
                        "id": "cover",
                        "name": "Обложка",
                        "zones": [
                            {
                                "id": "cover_bg",
                                "type": "image",
                                "x": 0, "y": 0, "width": 1080, "height": 1350,
                                "source": "uploaded",
                                "fit_mode": "cover"
                            },
                            {
                                "id": "cover_title",
                                "type": "text", 
                                "x": 80, "y": 930, "width": 920, "height": 320,
                                "content": "{{title}}",
                                "font_family": "Inter-Bold",
                                "font_size": 72,
                                "font_color": "#FFFFFF",
                                "align": "left"
                            }
                        ],
                        "background": {"type": "solid", "color": "#000000"}
                    }
                ]
            }
        }


# Данные для рендеринга
class RenderContent(BaseModel):
    """Контент для подстановки в шаблон"""
    title: Optional[str] = None
    subtitle: Optional[str] = None  
    body_text: Optional[str] = None
    bullet_points: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class RenderRequest(BaseModel):
    """Запрос на рендеринг"""
    template_id: str = Field(..., description="ID шаблона")
    slides_content: List[RenderContent] = Field(..., description="Контент для каждого слайда")
    output_format: Literal["png", "jpg", "pdf"] = Field(default="png")
    quality: int = Field(default=95, ge=1, le=100, description="Качество изображения")


