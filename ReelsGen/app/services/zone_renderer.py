"""
Рендер-движок для обработки зон шаблонов
"""
from __future__ import annotations
import re
import io
import asyncio
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat
from pathlib import Path

from ..schemas.template_schema import (
    TextZone, ImageZone, ShapeZone, 
    SolidBackground, GradientBackground, ImageBackground,
    TextAlign, FormattingEffect, ImageSource
)
from .text_overlay import load_font, wrap_text
from .image_provider import generate_image_bytes
from .utils_io import cover_fit, CANVAS_SIZE
from .font_manager import font_manager


class ZoneRenderer:
    """Рендер-движок для зон слайдов"""
    
    def __init__(self):
        self.fonts_cache = {}
        
    def create_canvas(self, width: int = 1080, height: int = 1350) -> Image.Image:
        """Создать пустой холст"""
        return Image.new("RGBA", (width, height), (255, 255, 255, 0))
    
    async def render_background(self, bg_config: Dict[str, Any], canvas_size: tuple = CANVAS_SIZE, content_values: Optional[Dict[str, Any]] = None) -> Image.Image:
        """
        Рендер фона слайда
        
        Args:
            bg_config: Конфигурация фона
            canvas_size: Размер холста (width, height)
            content_values: Значения для подстановки переменных
            
        Returns:
            Изображение фона
        """
        width, height = canvas_size
        
        if bg_config["type"] == "solid":
            # Сплошной цвет
            color = bg_config["color"]
            if content_values:
                color = self._substitute_variables(color, content_values)
            img = Image.new("RGBA", canvas_size, color)
            return img
            
        elif bg_config["type"] == "gradient":
            # Градиент - обрабатываем переменные в цветах
            gradient_config = bg_config.copy()
            if content_values and "colors" in gradient_config:
                gradient_config["colors"] = [
                    self._substitute_variables(str(color), content_values)
                    for color in gradient_config["colors"]
                ]
            return self._create_gradient(gradient_config, canvas_size)
            
        elif bg_config["type"] == "image":
            # Изображение как фон
            return await self._render_background_image(bg_config, canvas_size)
            
        else:
            # Fallback - белый фон
            return Image.new("RGBA", canvas_size, "#FFFFFF")
    
    def _create_gradient(self, config: Dict[str, Any], canvas_size: tuple) -> Image.Image:
        """Создать градиентный фон"""
        width, height = canvas_size
        colors = config["colors"]
        direction = config.get("direction", "vertical")
        
        # Создаем простой линейный градиент
        img = Image.new("RGBA", canvas_size)
        draw = ImageDraw.Draw(img)
        
        if direction == "vertical":
            # Вертикальный градиент
            for y in range(height):
                # Интерполяция между цветами
                ratio = y / height
                color = self._interpolate_colors(colors, ratio)
                draw.line([(0, y), (width, y)], fill=color)
                
        elif direction == "horizontal":
            # Горизонтальный градиент
            for x in range(width):
                ratio = x / width
                color = self._interpolate_colors(colors, ratio)
                draw.line([(x, 0), (x, height)], fill=color)
                
        return img
    
    def _interpolate_colors(self, colors: List[str], ratio: float) -> str:
        """Интерполяция между цветами"""
        if len(colors) < 2:
            return colors[0] if colors else "#FFFFFF"
            
        # Простая линейная интерполяция между первым и последним цветом
        color1 = colors[0]
        color2 = colors[-1]
        
        # Парсим hex цвета
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        
        # Интерполяция
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)  
        b = int(b1 + (b2 - b1) * ratio)
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    async def _render_background_image(self, config: Dict[str, Any], canvas_size: tuple) -> Image.Image:
        """Рендер изображения как фона"""
        source = config["source"]
        fit_mode = config.get("fit_mode", "cover")
        blur_radius = config.get("blur_radius", 0)
        opacity = config.get("opacity", 1.0)
        
        img = None
        
        if source == "ai_generated" and config.get("ai_prompt"):
            # AI генерация
            try:
                image_bytes = await generate_image_bytes(
                    prompt=config["ai_prompt"],
                    width=canvas_size[0],
                    height=canvas_size[1]
                )
                if image_bytes:
                    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            except Exception as e:
                print(f"[zone_renderer] Ошибка AI генерации фона: {e}")
                
        elif source == "uploaded" and config.get("uploaded_path"):
            # Загруженный файл
            try:
                img = Image.open(config["uploaded_path"]).convert("RGBA")
            except Exception as e:
                print(f"[zone_renderer] Ошибка загрузки фона: {e}")
                
        elif source == "url" and config.get("image_url"):
            # URL изображения
            try:
                import requests
                response = requests.get(config["image_url"], timeout=30)
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
            except Exception as e:
                print(f"[zone_renderer] Ошибка загрузки фона по URL: {e}")
        
        if not img:
            # Fallback - серый фон
            return Image.new("RGBA", canvas_size, "#F0F0F0")
        
        # Масштабирование
        if fit_mode == "cover":
            img = cover_fit(img, canvas_size)
        elif fit_mode == "contain":
            img.thumbnail(canvas_size, Image.LANCZOS)
            # Центрирование на белом фоне
            bg = Image.new("RGBA", canvas_size, "#FFFFFF")
            x = (canvas_size[0] - img.width) // 2
            y = (canvas_size[1] - img.height) // 2
            bg.paste(img, (x, y))
            img = bg
        elif fit_mode == "stretch":
            img = img.resize(canvas_size, Image.LANCZOS)
        
        # Размытие
        if blur_radius > 0:
            img = img.filter(ImageFilter.GaussianBlur(blur_radius))
            
        # Прозрачность
        if opacity < 1.0:
            alpha = img.split()[-1]
            alpha = alpha.point(lambda p: int(p * opacity))
            img.putalpha(alpha)
        
        return img
    
    async def render_text_zone(self, zone: TextZone, canvas: Image.Image, content_values: Dict[str, Any]) -> Image.Image:
        """
        Рендер текстовой зоны
        
        Args:
            zone: Конфигурация текстовой зоны
            canvas: Холст для рендеринга
            content_values: Значения для подстановки (например, {"title": "Заголовок"})
            
        Returns:
            Обновленный холст
        """
        # Подстановка переменных в текст
        text = self._substitute_variables(zone.content, content_values)
        if not text.strip():
            return canvas
        
        # Область для текста
        text_box = (zone.x, zone.y, zone.x + zone.width, zone.y + zone.height)
        
        # Выбор шрифта: используем предвыбранные шрифты карусели или AI
        optimal_font_id = self._get_carousel_font(zone, content_values) or await self._select_optimal_font(text, zone, content_values)
        font_path = self._resolve_font_path(optimal_font_id)
        
        if zone.auto_fit:
            # Автоподбор размера шрифта
            font_size = self._calculate_auto_fit_size(text, text_box, font_path, zone.line_height)
        else:
            font_size = zone.font_size
            
        font = load_font([font_path], font_size)
        
        # Адаптируем цвет текста к фону
        adapted_color = self._adapt_text_color_to_background(canvas, text_box, zone.font_color)
        
        # Рендеринг текста
        self._draw_text_with_formatting(
            canvas, text, text_box, font, 
            adapted_color, zone.align, zone.line_height, zone.formatting
        )
        
        return canvas
    
    async def render_image_zone(self, zone: ImageZone, canvas: Image.Image, content_values: Dict[str, Any]) -> Image.Image:
        """
        Рендер зоны с изображением
        
        Args:
            zone: Конфигурация зоны изображения
            canvas: Холст для рендеринга  
            content_values: Значения для подстановки в промты
            
        Returns:
            Обновленный холст
        """
        img = None
        
        if zone.source == ImageSource.AI_GENERATED and zone.ai_prompt:
            # AI генерация
            prompt = self._substitute_variables(zone.ai_prompt, content_values)
            print(f"[zone_renderer] [AI_IMAGE] Генерация для зоны {zone.id}: {prompt[:100]}...")
            try:
                image_bytes = await generate_image_bytes(
                    prompt=prompt,
                    width=zone.width, 
                    height=zone.height
                )
                if image_bytes:
                    import io
                    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
                    print(f"[zone_renderer] [AI_IMAGE] ✅ Сгенерировано: {img.size}, mode={img.mode}")
                else:
                    print(f"[zone_renderer] [AI_IMAGE] ❌ Пустой результат генерации")
            except Exception as e:
                print(f"[zone_renderer] [AI_IMAGE] ❌ Ошибка AI генерации: {e}")
                import traceback
                traceback.print_exc()
                
        elif zone.source == ImageSource.UPLOADED:
            # Загруженный файл - проверяем zone.uploaded_path или content_values
            uploaded_path = zone.uploaded_path or content_values.get('cover_image_path')
            if uploaded_path:
                try:
                    img = Image.open(uploaded_path).convert("RGBA")
                    print(f"[zone_renderer] ✅ Загружен файл: {uploaded_path}")
                except Exception as e:
                    print(f"[zone_renderer] Ошибка загрузки {uploaded_path}: {e}")
            else:
                print(f"[zone_renderer] ❌ Не найден путь к загруженному файлу для зоны {zone.id}")
                
        elif zone.source == ImageSource.URL and zone.image_url:
            # URL изображения
            try:
                import requests
                response = requests.get(zone.image_url, timeout=30)
                import io
                img = Image.open(io.BytesIO(response.content)).convert("RGBA")
            except Exception as e:
                print(f"[zone_renderer] Ошибка загрузки по URL: {e}")
        
        if not img:
            # Fallback - серый прямоугольник
            img = Image.new("RGBA", (zone.width, zone.height), "#D0D0D0")
        
        # Масштабирование
        target_size = (zone.width, zone.height)
        if zone.fit_mode == "cover":
            img = cover_fit(img, target_size)
        elif zone.fit_mode == "contain":
            img.thumbnail(target_size, Image.LANCZOS)
        elif zone.fit_mode == "stretch":
            img = img.resize(target_size, Image.LANCZOS)
        
        # Размытие
        if zone.blur_radius > 0:
            img = img.filter(ImageFilter.GaussianBlur(zone.blur_radius))
            
        # Прозрачность
        if zone.opacity < 1.0:
            alpha = img.split()[-1] if img.mode == "RGBA" else None
            if alpha:
                alpha = alpha.point(lambda p: int(p * zone.opacity))
                img.putalpha(alpha)
        
        # Вставка в холст
        if img:
            # Убеждаемся что изображение правильного размера
            if img.size != (zone.width, zone.height):
                print(f"[zone_renderer] [AI_IMAGE] ⚠️ Размер не совпадает: {img.size} != {(zone.width, zone.height)}, масштабируем")
                img = img.resize((zone.width, zone.height), Image.LANCZOS)
            
            # Вставляем с маской для прозрачности
            mask = img if img.mode == "RGBA" else None
            canvas.paste(img, (zone.x, zone.y), mask)
            print(f"[zone_renderer] [AI_IMAGE] ✅ Вставлено в canvas: позиция=({zone.x}, {zone.y}), размер={img.size}, opacity={zone.opacity}, blur={zone.blur_radius}")
            
            # Проверяем что изображение действительно вставлено (берем пиксель из центра)
            center_x, center_y = zone.x + zone.width // 2, zone.y + zone.height // 2
            if center_x < canvas.width and center_y < canvas.height:
                pixel = canvas.getpixel((center_x, center_y))
                print(f"[zone_renderer] [AI_IMAGE] Проверка пикселя в центре ({center_x}, {center_y}): {pixel}")
        else:
            print(f"[zone_renderer] [AI_IMAGE] ❌ Нет изображения для вставки")
        
        return canvas
    
    def render_shape_zone(self, zone: ShapeZone, canvas: Image.Image) -> Image.Image:
        """
        Рендер геометрической фигуры
        
        Args:
            zone: Конфигурация зоны фигуры
            canvas: Холст для рендеринга
            
        Returns:
            Обновленный холст
        """
        draw = ImageDraw.Draw(canvas)
        
        x1, y1 = zone.x, zone.y
        x2, y2 = zone.x + zone.width, zone.y + zone.height
        
        if zone.shape_type == "rectangle":
            # Прямоугольник
            if zone.fill_color:
                draw.rectangle([x1, y1, x2, y2], fill=zone.fill_color)
            if zone.stroke_color and zone.stroke_width > 0:
                draw.rectangle([x1, y1, x2, y2], outline=zone.stroke_color, width=zone.stroke_width)
                
        elif zone.shape_type == "circle":
            # Круг/эллипс
            if zone.fill_color:
                draw.ellipse([x1, y1, x2, y2], fill=zone.fill_color)
            if zone.stroke_color and zone.stroke_width > 0:
                draw.ellipse([x1, y1, x2, y2], outline=zone.stroke_color, width=zone.stroke_width)
                
        elif zone.shape_type == "line":
            # Линия
            if zone.stroke_color:
                draw.line([x1, y1, x2, y2], fill=zone.stroke_color, width=zone.stroke_width or 1)
        
        return canvas
    
    def _substitute_variables(self, text: str, values: Dict[str, Any]) -> str:
        """Подстановка переменных в текст типа {{variable}}"""
        def replace_var(match):
            var_name = match.group(1)
            value = values.get(var_name, f"{{{{{var_name}}}}}")
            if var_name not in values:
                print(f"[zone_renderer] [SUBSTITUTE] ⚠️ Переменная {{{{{var_name}}}}} не найдена в values")
            return str(value)
        
        result = re.sub(r'\{\{(\w+)\}\}', replace_var, text)
        if "{{" in result:
            print(f"[zone_renderer] [SUBSTITUTE] ⚠️ Остались неподставленные переменные в: {result[:100]}")
        return result
    
    async def _select_optimal_font(self, text: str, zone: TextZone, content_values: Dict[str, Any]) -> str:
        """
        Выбрать оптимальный шрифт на основе контекста
        
        Args:
            text: Текст для анализа
            zone: Конфигурация текстовой зоны
            content_values: Контекст (title, slide_text и т.д.)
            
        Returns:
            ID выбранного шрифта
        """
        try:
            # Определяем тип текста на основе размера шрифта и содержимого
            if zone.font_size >= 60 or "title" in zone.id.lower() or "headline" in zone.id.lower():
                text_type = "heading"
            elif "body" in zone.id.lower() or "content" in zone.id.lower():
                text_type = "body" 
            elif "creative" in zone.id.lower() or "artistic" in zone.id.lower():
                text_type = "creative"
            else:
                # Определяем по длине текста
                text_type = "heading" if len(text) < 100 else "body"
            
            # Извлекаем тему из контекста
            title = content_values.get("title", "")
            slide_text = content_values.get("slide_text", "")
            combined_context = f"{title} {slide_text}".lower()
            
            # Простая классификация темы
            theme = None
            if any(word in combined_context for word in ["бизнес", "стартап", "предпринимател", "компани", "финанс"]):
                theme = "business"
            elif any(word in combined_context for word in ["спорт", "фитнес", "тренировк", "здоровь"]):
                theme = "sport"  
            elif any(word in combined_context for word in ["мода", "стиль", "красот", "дизайн"]):
                theme = "fashion"
            elif any(word in combined_context for word in ["технолог", "программ", "it", "digital", "софт"]):
                theme = "tech"
            elif any(word in combined_context for word in ["искусств", "творчеств", "креатив", "художеств"]):
                theme = "creative"
            
            # Определяем настроение
            mood = None
            if any(word in combined_context for word in ["элегант", "роскош", "премиум", "изыска"]):
                mood = "elegant"
            elif any(word in combined_context for word in ["игрив", "весел", "радост", "яркий"]):
                mood = "playful"
            elif any(word in combined_context for word in ["серьезн", "профессионал", "деловой"]):
                mood = "serious"
            elif any(word in combined_context for word in ["соврем", "новый", "инновац", "будущ"]):
                mood = "modern"
            
            # Используем AI для выбора шрифта
            selected_font = await font_manager.select_font_by_context(
                text=text,
                text_type=text_type,
                theme=theme,
                mood=mood
            )
            
            # Убеждаемся что шрифт доступен
            is_available = await font_manager.ensure_font_available(selected_font)
            if not is_available:
                print(f"[zone_renderer] ⚠️ Шрифт {selected_font} недоступен, используем Inter-Bold")
                selected_font = "Inter-Bold"
            
            return selected_font
            
        except Exception as e:
            print(f"[zone_renderer] ❌ Ошибка выбора шрифта: {e}")
            return "Inter-Bold"  # Безопасный fallback
    
    def _get_carousel_font(self, zone: TextZone, content_values: Dict[str, Any]) -> Optional[str]:
        """
        Получить предвыбранный шрифт из carousel_fonts
        
        Args:
            zone: Текстовая зона
            content_values: Контекст с выбранными шрифтами
            
        Returns:
            ID шрифта или None если нет предвыбранных
        """
        carousel_fonts = content_values.get("carousel_fonts")
        if not carousel_fonts:
            return None
        
        # Определяем роль зоны по ID и размеру шрифта
        zone_id_lower = zone.id.lower()
        
        # Заголовок обложки
        if any(word in zone_id_lower for word in ["cover", "title"]) and zone.font_size >= 80:
            return carousel_fonts.get("cover_title")
        
        # Заголовки контентных слайдов  
        elif any(word in zone_id_lower for word in ["heading", "title"]) and zone.font_size >= 50:
            return carousel_fonts.get("content_heading")
            
        # UI элементы (кнопки, счетчики)
        elif any(word in zone_id_lower for word in ["button", "nav", "page", "num", "counter"]) or zone.font_size <= 45:
            return carousel_fonts.get("ui_elements")
            
        # Основной текст
        else:
            return carousel_fonts.get("content_body")
    
    def _resolve_font_path(self, font_identifier: str) -> str:
        """
        Получить путь к файлу шрифта
        
        Args:
            font_identifier: ID шрифта из font_manager или имя семейства
            
        Returns:
            Путь к файлу шрифта
        """
        # Сначала пытаемся найти через font_manager
        font_path = font_manager.get_font_path(font_identifier)
        if font_path:
            return font_path
        
        # Fallback к старой системе для совместимости
        font_map = {
            "Inter-Regular": "app/assets/fonts/Inter-Regular.ttf",
            "Inter-Bold": "app/assets/fonts/Inter-Bold.ttf", 
            "Inter-Light": "app/assets/fonts/Inter-Light.ttf"
        }
        
        return font_map.get(font_identifier, font_map["Inter-Regular"])
    
    def _calculate_auto_fit_size(self, text: str, box: tuple, font_path: str, line_height: float) -> int:
        """Автоподбор размера шрифта для вписывания в область"""
        x1, y1, x2, y2 = box
        max_width = x2 - x1
        max_height = y2 - y1
        
        # Бинарный поиск оптимального размера
        min_size, max_size = 12, 200
        best_size = min_size
        
        # Создаем временное изображение для измерения текста
        temp_img = Image.new("RGB", (max_width, 100), "white")
        temp_draw = ImageDraw.Draw(temp_img)
        
        for _ in range(10):  # Максимум 10 итераций
            size = (min_size + max_size) // 2
            font = load_font([font_path], size)
            
            # Пробуем перенести текст
            lines = wrap_text(text, font, max_width, temp_draw)
            
            # Высота текста
            line_height_px = int(size * line_height)
            total_height = len(lines) * line_height_px
            
            if total_height <= max_height and len(lines) > 0:
                best_size = size
                min_size = size + 1
            else:
                max_size = size - 1
                
            if min_size > max_size:
                break
        
        return max(best_size, 12)  # Минимум 12px
    
    def _draw_text_with_formatting(self, canvas: Image.Image, text: str, box: tuple, 
                                  font: ImageFont.ImageFont, color: str, align: str, 
                                  line_height: float, formatting: List[Dict[str, Any]]):
        """Рендер текста с форматированием"""
        x1, y1, x2, y2 = box
        max_width = x2 - x1
        
        draw = ImageDraw.Draw(canvas)
        
        # Переносим текст по словам
        lines = wrap_text(text, font, max_width, draw)
        
        # Определяем высоту строки
        line_height_px = int(font.size * line_height)
        
        # Начальная позиция Y
        if align == "center":
            total_height = len(lines) * line_height_px  
            start_y = y1 + (y2 - y1 - total_height) // 2
        else:
            start_y = y1
        
        # Рендерим строки
        for i, line in enumerate(lines):
            y = start_y + i * line_height_px
            
            # Позиция X в зависимости от выравнивания
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            
            if align == "center":
                x = x1 + (max_width - text_width) // 2
            elif align == "right":
                x = x2 - text_width
            else:  # left
                x = x1
            
            # Основной текст
            draw.text((x, y), line, fill=color, font=font)
            
            # TODO: Применить эффекты форматирования (underline, highlight, etc)
        
        print(f"[zone_renderer] Отрендерен текст: {len(lines)} строк, размер шрифта: {font.size}")
    
    def _adapt_text_color_to_background(self, canvas: Image.Image, text_box: tuple, original_color: str) -> str:
        """
        Адаптирует цвет текста к яркости фона для лучшей читаемости
        
        Args:
            canvas: Холст с фоном
            text_box: Область текста (x1, y1, x2, y2)
            original_color: Исходный цвет текста
            
        Returns:
            Адаптированный цвет текста
        """
        try:
            x1, y1, x2, y2 = text_box
            
            # Ограничиваем область размерами холста
            x1 = max(0, x1)
            y1 = max(0, y1)  
            x2 = min(canvas.width, x2)
            y2 = min(canvas.height, y2)
            
            if x1 >= x2 or y1 >= y2:
                return original_color
                
            # Извлекаем область фона под текстом
            bg_region = canvas.crop((x1, y1, x2, y2))
            
            # Вычисляем среднюю яркость фона
            if bg_region.mode != "L":
                gray_region = bg_region.convert("L")
            else:
                gray_region = bg_region
                
            # Используем ImageStat для вычисления средней яркости
            brightness = ImageStat.Stat(gray_region).mean[0]
            
            # Пороговое значение для переключения цвета
            threshold = 128
            
            if brightness > threshold:
                # Светлый фон - темный текст
                adapted_color = "#1A1A1A"  # Очень темный серый
                contrast_info = f"светлый фон (яркость: {brightness:.0f})"
            else:
                # Темный фон - светлый текст  
                adapted_color = "#FFFFFF"  # Белый
                contrast_info = f"темный фон (яркость: {brightness:.0f})"
            
            # Логируем только если цвет изменился
            if adapted_color != original_color:
                print(f"[zone_renderer] 🎨 Адаптация цвета: {original_color} → {adapted_color} ({contrast_info})")
            
            return adapted_color
            
        except Exception as e:
            print(f"[zone_renderer] ⚠️ Ошибка адаптации цвета: {e}")
            return original_color


# Глобальный экземпляр
zone_renderer = ZoneRenderer()
