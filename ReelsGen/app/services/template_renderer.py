"""
Основной сервис для рендеринга шаблонов в готовые изображения
"""
from __future__ import annotations
import asyncio
from typing import List, Dict, Any, Optional, Union
from PIL import Image

from ..schemas.template_schema import CarouselTemplate, SlideTemplate, RenderContent, TextZone, ImageZone, ShapeZone
from .template_manager import template_manager
from .zone_renderer import zone_renderer


class TemplateRenderer:
    """Рендеринг шаблонов в готовые изображения"""
    
    def __init__(self):
        self.zone_renderer = zone_renderer
        
    async def render_carousel(self, template_id: str, slides_content: List[RenderContent]) -> List[Image.Image]:
        """
        Рендеринг полной карусели по шаблону
        
        Args:
            template_id: ID шаблона
            slides_content: Контент для каждого слайда
            
        Returns:
            Список готовых изображений слайдов
        """
        # Загружаем шаблон
        template = template_manager.load_template(template_id)
        if not template:
            raise ValueError(f"Шаблон {template_id} не найден")
        
        print(f"[template_renderer] Рендеринг карусели '{template.name}', слайдов: {len(slides_content)}")
        
        # === БАТЧИНГ ВЫБОРА ШРИФТОВ ===
        # Выбираем шрифты для всей карусели за один запрос
        carousel_fonts = await self._select_carousel_fonts(slides_content)
        
        # Определяем количество слайдов для рендеринга
        total_slides = len(slides_content)
        result_images = []
        
        for i, slide_content in enumerate(slides_content):
            # Определяем какой шаблон слайда использовать
            slide_template = self._select_slide_template(template, i, total_slides)
            
            # Готовим контент для подстановки
            content_values = self._prepare_content_values(slide_content, i, total_slides)
            
            # Добавляем выбранные шрифты в контекст
            content_values["carousel_fonts"] = carousel_fonts
            
            # Рендерим слайд
            slide_image = await self.render_slide(slide_template, content_values)
            result_images.append(slide_image)
            
            print(f"[template_renderer] Слайд {i+1}/{total_slides} отрендерен")
        
        return result_images
    
    async def render_slide(self, slide_template: SlideTemplate, content_values: Dict[str, Any]) -> Image.Image:
        """
        Рендеринг одного слайда
        
        Args:
            slide_template: Шаблон слайда
            content_values: Значения для подстановки
            
        Returns:
            Готовое изображение слайда
        """
        canvas_size = (slide_template.canvas_width, slide_template.canvas_height)
        
        # 1. Создаем фон
        background_img = await self.zone_renderer.render_background(
            slide_template.background.dict(), canvas_size, content_values
        )
        
        # 2. Сортируем зоны по z_index
        zones = sorted(slide_template.zones, key=lambda z: z.z_index)
        
        # 3. Рендерим зоны поочередно
        for zone in zones:
            print(f"[template_renderer] Рендеринг зоны: id={zone.id}, type={zone.type}, z_index={zone.z_index}")
            if isinstance(zone, TextZone):
                background_img = await self.zone_renderer.render_text_zone(
                    zone, background_img, content_values
                )
            elif isinstance(zone, ImageZone):
                print(f"[template_renderer] [IMAGE_ZONE] Рендеринг ImageZone: id={zone.id}, source={zone.source}, ai_prompt={zone.ai_prompt[:50] if zone.ai_prompt else None}...")
                background_img = await self.zone_renderer.render_image_zone(
                    zone, background_img, content_values
                )
            elif isinstance(zone, ShapeZone):
                background_img = self.zone_renderer.render_shape_zone(
                    zone, background_img
                )
        
        return background_img
    
    def _select_slide_template(self, carousel_template: CarouselTemplate, slide_index: int, total_slides: int) -> SlideTemplate:
        """
        Выбрать шаблон слайда для конкретной позиции
        
        Args:
            carousel_template: Шаблон карусели
            slide_index: Индекс слайда (0-based)
            total_slides: Общее количество слайдов
            
        Returns:
            Шаблон для конкретного слайда
        """
        # Логика выбора шаблона:
        # - Если есть слайд с id="cover" - используем его для первого слайда
        # - Для остальных используем слайд с id="content" или первый доступный
        
        available_templates = {slide.id: slide for slide in carousel_template.slides}
        
        if slide_index == 0 and "cover" in available_templates:
            # Первый слайд - обложка
            return available_templates["cover"]
        elif "content" in available_templates:
            # Контент-слайд
            return available_templates["content"]
        else:
            # Первый доступный шаблон
            return carousel_template.slides[0]
    
    def _prepare_content_values(self, slide_content: RenderContent, slide_index: int, total_slides: int) -> Dict[str, Any]:
        """
        Подготовить значения для подстановки в шаблон
        
        Args:
            slide_content: Контент слайда
            slide_index: Индекс слайда (0-based)
            total_slides: Общее количество слайдов
            
        Returns:
            Словарь для подстановки переменных
        """
        # Генерируем красивые градиентные цвета
        gradient_colors = self._get_gradient_colors(slide_index, slide_content.custom_fields.get("gradient_color"))
        
        values = {
            # Основной контент
            "title": slide_content.title or "",
            "subtitle": slide_content.subtitle or "",
            "body_text": slide_content.body_text or "",
            "headline": slide_content.title or slide_content.subtitle or "",
            
            # Метаданные слайда
            "slide_num": slide_index + 1,
            "total_slides": total_slides,
            "page_num": f"{slide_index + 1}/{total_slides}",
            
            # Буллеты как текст
            "bullets_text": "\n".join([f"→ {bullet}" for bullet in slide_content.bullet_points]),
            
            # Комбинированный текст слайда для AI промтов
            "slide_text": self._build_slide_text(slide_content),
            
            # Градиентные цвета
            "gradient_color_1": gradient_colors[0],
            "gradient_color_2": gradient_colors[1],
            
            # Пользовательские поля
            **slide_content.custom_fields
        }
        
        print(f"[template_renderer] [CONTENT_VALUES] slide_text={values.get('slide_text', '')[:100]}...")
        print(f"[template_renderer] [CONTENT_VALUES] title={values.get('title', '')}, bullets={len(slide_content.bullet_points)}")
        
        return values
    
    def _get_gradient_colors(self, slide_index: int, user_color: Optional[str] = None) -> tuple[str, str]:
        """
        Генерирует красивые градиентные цвета для слайда
        
        Args:
            slide_index: Индекс слайда (0-based)
            user_color: Пользовательский цвет (если указан)
            
        Returns:
            Кортеж из двух цветов (начальный, конечный)
        """
        # Красивые градиентные палитры
        gradient_palettes = [
            # Синий → Фиолетовый
            ("#667eea", "#764ba2"),
            # Розовый → Оранжевый
            ("#f093fb", "#f5576c"),
            # Зеленый → Бирюзовый
            ("#4facfe", "#00f2fe"),
            # Фиолетовый → Розовый
            ("#a8edea", "#fed6e3"),
            # Оранжевый → Красный
            ("#fa709a", "#fee140"),
            # Синий → Голубой
            ("#30cfd0", "#330867"),
            # Фиолетовый → Синий
            ("#a8caba", "#5d4e75"),
            # Розовый → Фиолетовый
            ("#ff9a9e", "#fecfef"),
            # Зеленый → Синий
            ("#84fab0", "#8fd3f4"),
            # Оранжевый → Желтый
            ("#ffecd2", "#fcb69f"),
        ]
        
        # Если пользователь указал цвет, используем его как базовый
        if user_color:
            # Генерируем второй цвет на основе пользовательского
            color2 = self._generate_complementary_color(user_color)
            return (user_color, color2)
        
        # Выбираем палитру на основе индекса слайда
        palette_index = slide_index % len(gradient_palettes)
        return gradient_palettes[palette_index]
    
    def _generate_complementary_color(self, base_color: str) -> str:
        """
        Генерирует дополнительный цвет на основе базового
        
        Args:
            base_color: Базовый цвет в формате #RRGGBB
            
        Returns:
            Дополнительный цвет в формате #RRGGBB
        """
        # Парсим базовый цвет
        r = int(base_color[1:3], 16)
        g = int(base_color[3:5], 16)
        b = int(base_color[5:7], 16)
        
        # Генерируем дополнительный цвет (инвертируем и затемняем)
        r2 = min(255, int(255 - r * 0.7))
        g2 = min(255, int(255 - g * 0.7))
        b2 = min(255, int(255 - b * 0.7))
        
        return f"#{r2:02x}{g2:02x}{b2:02x}"
    
    def _build_slide_text(self, slide_content: RenderContent) -> str:
        """Собрать весь текст слайда в одну строку для AI промтов"""
        parts = []
        
        if slide_content.title:
            parts.append(slide_content.title)
        if slide_content.subtitle:
            parts.append(slide_content.subtitle)
        if slide_content.body_text:
            parts.append(slide_content.body_text)
        
        # Добавляем буллеты
        for bullet in slide_content.bullet_points:
            parts.append(bullet)
        
        return ". ".join(parts)
    
    async def render_preview(self, template_id: str, slide_id: Optional[str] = None) -> Image.Image:
        """
        Быстрый рендер превью шаблона с placeholder контентом
        
        Args:
            template_id: ID шаблона
            slide_id: ID конкретного слайда (если None - первый слайд)
            
        Returns:
            Превью изображение
        """
        template = template_manager.load_template(template_id)
        if not template:
            raise ValueError(f"Шаблон {template_id} не найден")
        
        # Выбираем слайд
        if slide_id:
            slide_template = next((s for s in template.slides if s.id == slide_id), template.slides[0])
        else:
            slide_template = template.slides[0]
        
        # Placeholder контент
        placeholder_content = {
            "title": "Заголовок слайда",
            "subtitle": "Подзаголовок",
            "body_text": "Основной текст слайда с описанием содержимого",
            "headline": "Заголовок слайда", 
            "slide_text": "демонстрация шаблона",
            "page_num": "1/5",
            "slide_num": 1,
            "total_slides": 5
        }
        
        return await self.render_slide(slide_template, placeholder_content)
    
    async def _select_carousel_fonts(self, slides_content: List[RenderContent]) -> Dict[str, str]:
        """Выбрать шрифты для всей карусели"""
        try:
            from .font_manager import font_manager
            
            # Извлекаем title из первого слайда (обложки)
            title = ""
            content_slides = []
            
            for i, content in enumerate(slides_content):
                # Первый слайд = обложка, остальные = контент
                if i == 0:
                    title = content.title or ""
                else:
                    # Формируем данные для анализа
                    slide_data = {}
                    if content.title:
                        slide_data["thesis"] = content.title
                    
                    # Собираем текст из body_text и bullet_points
                    slide_text_parts = []
                    if content.body_text:
                        slide_text_parts.append(content.body_text)
                    if content.bullet_points:
                        slide_text_parts.extend(content.bullet_points)
                    
                    if slide_text_parts:
                        slide_data["points"] = slide_text_parts
                    
                    content_slides.append(slide_data)
            
            # Выбираем шрифты для карусели
            selected_fonts = await font_manager.select_fonts_for_carousel(
                title=title,
                content_slides=content_slides
            )
            
            return selected_fonts
            
        except Exception as e:
            print(f"[template_renderer] [ERROR] Ошибка выбора шрифтов карусели: {e}")
            # Fallback к простому набору
            return {
                "cover_title": "Inter-Bold",
                "content_heading": "Montserrat-Bold",
                "content_body": "Inter-Regular",
                "ui_elements": "Inter-Bold"
            }


# Глобальный экземпляр
template_renderer = TemplateRenderer()


async def create_carousel_from_legacy_data(title: str, slides_data: List[Dict[str, Any]]) -> List[Image.Image]:
    """
    Создать карусель в новом формате из данных старого формата
    
    Args:
        title: Заголовок карусели
        slides_data: Данные слайдов в старом формате
        
    Returns:
        Список готовых изображений
    """
    # Преобразуем данные в новый формат
    slides_content = []
    
    for i, slide in enumerate(slides_data):
        if slide.get("type") == "cover":
            # Обложка
            content = RenderContent(
                title=title,
                custom_fields={"cover_image_path": slide.get("image_path")}
            )
        else:
            # Контент-слайд
            title_text = slide.get("title") or slide.get("heading") or slide.get("thesis") or ""
            
            # Собираем body_text
            body_parts = []
            if slide.get("thesis"):
                body_parts.append(slide["thesis"])
            
            points = slide.get("points", [])
            if points:
                body_parts.extend([f"→ {point}" for point in points])
            
            body_text = "\n\n".join(body_parts)
            
            content = RenderContent(
                title=title_text,
                body_text=body_text,
                bullet_points=points
            )
        
        slides_content.append(content)
    
    # Используем шаблон instagram_carousel
    return await template_renderer.render_carousel("instagram_carousel", slides_content)
