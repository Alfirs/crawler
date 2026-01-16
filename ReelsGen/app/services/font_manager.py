"""
Менеджер шрифтов - автоматический выбор и управление шрифтами
"""
from __future__ import annotations
import os
import json
import requests
import zipfile
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
from dataclasses import dataclass

from .neuroapi import chat_complete


@dataclass
class FontInfo:
    """Информация о шрифте"""
    name: str
    family: str
    file_path: str
    category: str  # serif, sans-serif, display, handwriting, monospace
    moods: List[str]  # modern, elegant, playful, serious, creative
    best_for: List[str]  # headings, body, creative, corporate, sports
    avoid_for: List[str]  # luxury, vintage, children
    supports_cyrillic: bool = True
    weight: str = "regular"  # regular, bold, light


class FontManager:
    """Управление шрифтами и автоматический выбор"""
    
    def __init__(self, fonts_dir: str = "app/assets/fonts"):
        self.fonts_dir = Path(fonts_dir)
        self.fonts_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем подпапки
        (self.fonts_dir / "downloaded").mkdir(exist_ok=True)
        
        self.fonts_catalog: Dict[str, FontInfo] = {}
        self.load_fonts_catalog()
    
    def load_fonts_catalog(self):
        """Загрузить каталог доступных шрифтов"""
        # Базовый каталог отличных Google Fonts
        fonts_data = {
            # === ЗАГОЛОВКИ (HEADINGS) ===
            "Inter-Bold": FontInfo(
                name="Inter-Bold",
                family="Inter",
                file_path="Inter-Bold.ttf",
                category="sans-serif",
                moods=["modern", "clean", "professional", "tech"],
                best_for=["headings", "corporate", "tech", "presentations"],
                avoid_for=["luxury", "vintage", "handwriting"],
                weight="bold"
            ),
            "Montserrat-Bold": FontInfo(
                name="Montserrat-Bold", 
                family="Montserrat",
                file_path="Montserrat-Bold.ttf",
                category="sans-serif",
                moods=["geometric", "modern", "confident", "stylish"],
                best_for=["headings", "branding", "fashion", "design"],
                avoid_for=["traditional", "academic"],
                weight="bold"
            ),
            "Playfair-Bold": FontInfo(
                name="Playfair-Bold",
                family="Playfair Display", 
                file_path="PlayfairDisplay-Bold.ttf",
                category="serif",
                moods=["elegant", "luxury", "sophisticated", "classic"],
                best_for=["headings", "luxury", "fashion", "culture"],
                avoid_for=["tech", "sports", "casual"],
                weight="bold"
            ),
            "Oswald-Bold": FontInfo(
                name="Oswald-Bold",
                family="Oswald",
                file_path="Oswald-Bold.ttf", 
                category="sans-serif",
                moods=["strong", "condensed", "impactful", "sporty"],
                best_for=["headings", "sports", "news", "bold-statements"],
                avoid_for=["elegant", "body-text", "luxury"],
                weight="bold"
            ),
            "Poppins-Bold": FontInfo(
                name="Poppins-Bold",
                family="Poppins",
                file_path="Poppins-Bold.ttf",
                category="sans-serif", 
                moods=["friendly", "rounded", "approachable", "modern"],
                best_for=["headings", "startups", "creative", "youth"],
                avoid_for=["formal", "traditional"],
                weight="bold"
            ),
            "Raleway-Bold": FontInfo(
                name="Raleway-Bold",
                family="Raleway",
                file_path="Raleway-Bold.ttf",
                category="sans-serif",
                moods=["refined", "elegant", "thin", "sophisticated"],
                best_for=["headings", "fashion", "art", "minimal"],
                avoid_for=["heavy", "sports"],
                weight="bold"
            ),
            
            # === ОСНОВНОЙ ТЕКСТ (BODY) ===
            "Inter-Regular": FontInfo(
                name="Inter-Regular",
                family="Inter", 
                file_path="Inter-Regular.ttf",
                category="sans-serif",
                moods=["neutral", "readable", "clean", "modern"],
                best_for=["body", "UI", "corporate", "presentations"],
                avoid_for=["decorative"],
                weight="regular"
            ),
            "Lora-Regular": FontInfo(
                name="Lora-Regular",
                family="Lora",
                file_path="Lora-Regular.ttf",
                category="serif",
                moods=["readable", "warm", "friendly", "classic"],
                best_for=["body", "articles", "blogs", "storytelling"],
                avoid_for=["tech", "modern-ui"],
                weight="regular"
            ),
            "Source-Regular": FontInfo(
                name="Source-Regular", 
                family="Source Sans Pro",
                file_path="SourceSansPro-Regular.ttf",
                category="sans-serif",
                moods=["neutral", "professional", "clean", "reliable"],
                best_for=["body", "corporate", "documentation", "UI"],
                avoid_for=["creative", "artistic"],
                weight="regular"
            ),
            "OpenSans-Regular": FontInfo(
                name="OpenSans-Regular",
                family="Open Sans",
                file_path="OpenSans-Regular.ttf",
                category="sans-serif",
                moods=["friendly", "readable", "humanist", "versatile"],
                best_for=["body", "web", "mobile", "accessibility"],
                avoid_for=["luxury", "artistic"],
                weight="regular"
            ),
            
            # === КРЕАТИВНЫЕ (CREATIVE) ===
            "Comfortaa-Bold": FontInfo(
                name="Comfortaa-Bold",
                family="Comfortaa", 
                file_path="Comfortaa-Bold.ttf",
                category="display",
                moods=["rounded", "friendly", "playful", "soft"],
                best_for=["headings", "children", "creative", "brands"],
                avoid_for=["formal", "serious", "corporate"],
                weight="bold"
            ),
            "Righteous-Regular": FontInfo(
                name="Righteous-Regular",
                family="Righteous",
                file_path="Righteous-Regular.ttf", 
                category="display",
                moods=["retro", "bold", "vintage", "confident"],
                best_for=["headings", "vintage", "brands", "logos"],
                avoid_for=["body-text", "formal"],
                weight="regular"
            ),
            "Lobster-Regular": FontInfo(
                name="Lobster-Regular",
                family="Lobster",
                file_path="Lobster-Regular.ttf",
                category="display",
                moods=["script", "casual", "handwritten", "cheerful"],
                best_for=["headings", "casual", "fun", "personal"],
                avoid_for=["corporate", "serious", "body-text"],
                weight="regular"
            ),
            
            # === ОСОБЫЕ СЛУЧАИ ===
            "Roboto-Bold": FontInfo(
                name="Roboto-Bold",
                family="Roboto",
                file_path="Roboto-Bold.ttf",
                category="sans-serif", 
                moods=["mechanical", "modern", "google", "android"],
                best_for=["headings", "tech", "mobile", "digital"],
                avoid_for=["luxury", "handmade"],
                weight="bold"
            ),
            "Merriweather-Bold": FontInfo(
                name="Merriweather-Bold",
                family="Merriweather",
                file_path="Merriweather-Bold.ttf",
                category="serif",
                moods=["traditional", "readable", "scholarly", "trustworthy"],
                best_for=["headings", "editorial", "academic", "traditional"],
                avoid_for=["modern", "tech"],
                weight="bold"
            )
        }
        
        # Добавляем в каталог только те шрифты, файлы которых существуют
        for font_id, font_info in fonts_data.items():
            font_path = self.fonts_dir / font_info.file_path
            if font_path.exists():
                self.fonts_catalog[font_id] = font_info
            else:
                # Помечаем как требующий загрузки
                font_info.file_path = str(font_path)
                self.fonts_catalog[font_id] = font_info
        
        print(f"[font_manager] Загружен каталог: {len(self.fonts_catalog)} шрифтов")
    
    async def ensure_font_available(self, font_id: str) -> bool:
        """Убедиться что шрифт доступен (скачать если нужно)"""
        if font_id not in self.fonts_catalog:
            print(f"[font_manager] [ERROR] Шрифт {font_id} не найден в каталоге")
            return False
            
        font_info = self.fonts_catalog[font_id]
        font_path = Path(font_info.file_path)
        
        if font_path.exists():
            return True
            
        # Пытаемся скачать с Google Fonts
        try:
            await self.download_google_font(font_info)
            return font_path.exists()
        except Exception as e:
            print(f"[font_manager] [ERROR] Ошибка загрузки {font_id}: {e}")
            return False
    
    async def download_google_font(self, font_info: FontInfo):
        """Скачать шрифт с Google Fonts через CSS API"""
        print(f"[font_manager] [DOWNLOAD] Скачивание {font_info.name}...")
        
        # Определяем weight из названия шрифта
        if "Bold" in font_info.name:
            weight = "700"
        elif "Light" in font_info.name:
            weight = "300"
        else:
            weight = "400"
        
        # Формируем family name для Google Fonts CSS API
        family_name = font_info.family.replace(" ", "+")
        
        # Google Fonts CSS API URL
        css_url = f"https://fonts.googleapis.com/css2?family={family_name}:wght@{weight}&display=swap"
        
        try:
            # Получаем CSS файл с ссылками на шрифты
            css_response = requests.get(css_url, timeout=30)
            css_response.raise_for_status()
            css_content = css_response.text
            
            # Ищем ссылку на TTF файл в CSS
            import re
            # Ищем паттерн url(https://fonts.gstatic.com/s/...)
            font_url_match = re.search(r'url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)', css_content)
            
            if not font_url_match:
                # Пробуем найти woff2 и конвертировать
                woff2_match = re.search(r'url\((https://fonts\.gstatic\.com/[^)]+\.woff2)\)', css_content)
                if woff2_match:
                    # Заменяем woff2 на ttf в URL (иногда работает)
                    font_url = woff2_match.group(1).replace('.woff2', '.ttf')
                else:
                    raise Exception(f"TTF ссылка не найдена в CSS для {font_info.name}")
            else:
                font_url = font_url_match.group(1)
            
            print(f"[font_manager] Найден URL: {font_url}")
            
            # Скачиваем TTF файл
            font_response = requests.get(font_url, timeout=60)
            font_response.raise_for_status()
            
            # Проверяем что это действительно шрифт
            if not font_response.content.startswith(b'\x00\x01\x00\x00') and \
               not font_response.content.startswith(b'OTTO') and \
               not font_response.content.startswith(b'true'):
                # Пробуем альтернативный подход - прямая загрузка с GitHub для популярных шрифтов
                await self._download_from_github(font_info)
                return
            
            # Сохраняем шрифт
            target_path = Path(font_info.file_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_path, 'wb') as f:
                f.write(font_response.content)
            
            print(f"[font_manager] [SUCCESS] {font_info.name} скачан: {target_path}")
            
        except Exception as e:
            print(f"[font_manager] [ERROR] Ошибка скачивания через CSS: {e}")
            # Пробуем альтернативный способ
            try:
                await self._download_from_github(font_info)
            except Exception as github_error:
                print(f"[font_manager] [ERROR] Ошибка GitHub загрузки: {github_error}")
                raise e
    
    async def _download_from_github(self, font_info: FontInfo):
        """Альтернативная загрузка с GitHub для популярных шрифтов"""
        github_urls = {
            "Inter": "https://github.com/rsms/inter/releases/download/v3.19/Inter-3.19.zip",
            "Roboto": "https://github.com/googlefonts/roboto/releases/download/v2.138/roboto-unhinted.zip"
        }
        
        family_key = font_info.family.split()[0]  # Берем первое слово
        
        if family_key not in github_urls:
            raise Exception(f"GitHub источник для {font_info.family} не найден")
        
        zip_url = github_urls[family_key]
        print(f"[font_manager] [GITHUB] Загрузка с GitHub: {zip_url}")
        
        # Скачиваем ZIP
        response = requests.get(zip_url, timeout=120)
        response.raise_for_status()
        
        zip_path = self.fonts_dir / f"{font_info.name}_github.zip"
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # Извлекаем нужный шрифт
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Ищем подходящий файл
            target_weight = "Bold" if "Bold" in font_info.name else "Regular"
            
            for file_name in zip_ref.namelist():
                if file_name.endswith('.ttf') and target_weight in file_name:
                    # Извлекаем файл
                    zip_ref.extract(file_name, self.fonts_dir)
                    
                    # Переименовываем в ожидаемое имя
                    extracted_path = self.fonts_dir / file_name
                    target_path = Path(font_info.file_path)
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    if extracted_path.exists():
                        extracted_path.rename(target_path)
                        print(f"[font_manager] [SUCCESS] GitHub загрузка: {target_path}")
                        break
        
        # Удаляем ZIP
        zip_path.unlink()
    
    async def select_fonts_for_carousel(self, 
                                       title: str,
                                       content_slides: List[Dict[str, Any]],
                                       theme: Optional[str] = None
                                       ) -> Dict[str, str]:
        """
        Выбрать набор шрифтов для всей карусели за один AI-запрос
        
        Args:
            title: Заголовок карусели
            content_slides: Список слайдов с контентом
            theme: Тематика (опционально)
            
        Returns:
            Dict с выбранными шрифтами для разных элементов:
            {
                "cover_title": "Inter-Bold",
                "content_heading": "Montserrat-Bold", 
                "content_body": "Source-Regular",
                "ui_elements": "Inter-Bold"
            }
        """
        try:
            # Формируем контекст для анализа
            combined_text = f"{title}. "
            for slide in content_slides[:3]:  # Анализируем первые 3 слайда
                if 'thesis' in slide:
                    combined_text += f"{slide['thesis']}. "
                if 'points' in slide and slide['points']:
                    combined_text += f"{' '.join(slide['points'][:2])}. "  # Первые 2 пункта
            
            # Определяем тему автоматически если не задана
            if not theme:
                theme = self._detect_theme(combined_text)
            
            # Создаем список доступных шрифтов
            available_fonts = {}
            for font_id, font_info in self.fonts_catalog.items():
                available_fonts[font_id] = {
                    "name": font_info.name,
                    "category": font_info.category,
                    "moods": font_info.moods,
                    "best_for": font_info.best_for,
                    "weight": font_info.weight
                }
            
            # Системный промпт для батчинг-выбора
            system_prompt = """Ты — эксперт по типографике. Твоя задача — создать красивую типографическую иерархию для Instagram-карусели.

ВАЖНО: 
1. Используй РАЗНЫЕ шрифты для создания визуального контраста и иерархии
2. Заголовок обложки должен быть самым ярким и заметным
3. Заголовки слайдов - средний вес 
4. Основной текст - читаемый, нейтральный
5. UI элементы (кнопки, счетчики) - четкие, не отвлекающие

Отвечай ТОЛЬКО в JSON формате."""

            user_prompt = f"""Контекст карусели:
Заголовок: "{title}"
Тематика: {theme or 'бизнес/общее'}
Содержание: {combined_text[:500]}...

Доступные шрифты:
{json.dumps(available_fonts, ensure_ascii=False, indent=2)}

Выбери шрифты для создания красивой типографической иерархии:

{{
  "cover_title": "название_шрифта",
  "content_heading": "название_шрифта", 
  "content_body": "название_шрифта",
  "ui_elements": "название_шрифта",
  "reasoning": "краткое обоснование выбора и контраста"
}}"""

            # Запрос к AI
            response = await chat_complete(system_prompt, user_prompt, temperature=0.3)
            
            try:
                result = json.loads(response)
                selected_fonts = {
                    "cover_title": result.get("cover_title", "Inter-Bold"),
                    "content_heading": result.get("content_heading", "Montserrat-Bold"),
                    "content_body": result.get("content_body", "Inter-Regular"), 
                    "ui_elements": result.get("ui_elements", "Inter-Bold")
                }
                
                reasoning = result.get("reasoning", "Автоматический выбор")
                
                # Проверяем что все шрифты существуют
                for role, font_id in selected_fonts.items():
                    if font_id not in self.fonts_catalog:
                        print(f"[font_manager] [WARNING] Шрифт {font_id} для {role} не найден, используем fallback")
                        selected_fonts[role] = self._get_fallback_font(role)
                
                # Обеспечиваем доступность всех шрифтов
                for font_id in set(selected_fonts.values()):
                    await self.ensure_font_available(font_id)
                
                print(f"[font_manager] [BATCH] Выбраны шрифты для карусели: {selected_fonts}")
                print(f"[font_manager] [BATCH] Обоснование: {reasoning}")
                
                return selected_fonts
                
            except json.JSONDecodeError:
                print(f"[font_manager] [ERROR] Ошибка парсинга батч-ответа: {response}")
                return self._get_fallback_fonts()
                
        except Exception as e:
            print(f"[font_manager] [ERROR] Ошибка батч-выбора шрифтов: {e}")
            return self._get_fallback_fonts()
    
    def _detect_theme(self, text: str) -> str:
        """Автоматическое определение темы по тексту"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["бизнес", "стартап", "предпринимател", "компани", "финанс", "прибыл", "доход"]):
            return "business"
        elif any(word in text_lower for word in ["спорт", "фитнес", "тренировк", "здоровь", "мышц"]):
            return "sport"
        elif any(word in text_lower for word in ["мода", "стиль", "красот", "дизайн", "трен"]):
            return "fashion"
        elif any(word in text_lower for word in ["технолог", "программ", "it", "digital", "софт", "код"]):
            return "tech"
        elif any(word in text_lower for word in ["искусств", "творчеств", "креатив", "художеств"]):
            return "creative"
        else:
            return "general"
    
    def _get_fallback_font(self, role: str) -> str:
        """Получить резервный шрифт для роли"""
        fallback_map = {
            "cover_title": "Inter-Bold",
            "content_heading": "Inter-Bold", 
            "content_body": "Inter-Regular",
            "ui_elements": "Inter-Bold"
        }
        return fallback_map.get(role, "Inter-Bold")
    
    def _get_fallback_fonts(self) -> Dict[str, str]:
        """Получить набор резервных шрифтов"""
        return {
            "cover_title": "Inter-Bold",
            "content_heading": "Montserrat-Bold",
            "content_body": "Inter-Regular", 
            "ui_elements": "Inter-Bold"
        }

    async def select_font_by_context(self, 
                                   text: str, 
                                   text_type: str = "heading",  # heading, body, creative
                                   theme: Optional[str] = None,  # business, sport, fashion, tech
                                   mood: Optional[str] = None    # modern, elegant, playful, serious
                                   ) -> str:
        """
        Выбрать подходящий шрифт на основе контекста с помощью AI
        
        Args:
            text: Текст для анализа
            text_type: Тип текста (heading, body, creative)  
            theme: Тематика (business, sport, fashion, tech)
            mood: Настроение (modern, elegant, playful, serious)
            
        Returns:
            ID выбранного шрифта
        """
        try:
            # Формируем список доступных шрифтов для выбора
            available_fonts = {}
            for font_id, font_info in self.fonts_catalog.items():
                available_fonts[font_id] = {
                    "name": font_info.name,
                    "category": font_info.category, 
                    "moods": font_info.moods,
                    "best_for": font_info.best_for,
                    "avoid_for": font_info.avoid_for,
                    "weight": font_info.weight
                }
            
            # Создаем промпт для GPT
            system_prompt = """Ты — эксперт по типографике и дизайну шрифтов. 
Твоя задача — выбрать наиболее подходящий шрифт для заданного текста на основе контекста.

Учитывай:
1. Читаемость (главный критерий)
2. Соответствие тематике и настроению
3. Тип текста (заголовок vs основной текст)
4. Целевую аудиторию

Отвечай ТОЛЬКО в формате JSON: {"font_id": "название", "reason": "краткое обоснование"}"""

            user_prompt = f"""Контекст:
- Текст: "{text}"
- Тип: {text_type}
- Тематика: {theme or 'не указана'}
- Настроение: {mood or 'не указано'}

Доступные шрифты:
{json.dumps(available_fonts, ensure_ascii=False, indent=2)}

Выбери наиболее подходящий шрифт."""

            # Запрос к GPT
            response = await chat_complete(system_prompt, user_prompt, temperature=0.1)
            
            # Парсим ответ
            try:
                result = json.loads(response)
                selected_font = result.get("font_id", "Inter-Bold")
                reason = result.get("reason", "Выбор по умолчанию")
                
                # Проверяем что шрифт существует в каталоге
                if selected_font in self.fonts_catalog:
                    print(f"[font_manager] [AI] AI выбор: {selected_font} ({reason})")
                    return selected_font
                else:
                    print(f"[font_manager] [WARNING] AI выбрал несуществующий шрифт {selected_font}, используем Inter-Bold")
                    return "Inter-Bold"
                    
            except json.JSONDecodeError:
                print(f"[font_manager] [ERROR] Ошибка парсинга ответа AI: {response}")
                return self._fallback_font_selection(text_type)
                
        except Exception as e:
            print(f"[font_manager] [ERROR] Ошибка AI выбора шрифта: {e}")
            return self._fallback_font_selection(text_type)
    
    def _fallback_font_selection(self, text_type: str) -> str:
        """Резервный выбор шрифта без AI"""
        fallback_map = {
            "heading": "Inter-Bold",
            "body": "Inter-Regular", 
            "creative": "Comfortaa-Bold"
        }
        return fallback_map.get(text_type, "Inter-Bold")
    
    def get_font_path(self, font_id: str) -> Optional[str]:
        """Получить путь к файлу шрифта"""
        if font_id in self.fonts_catalog:
            font_path = self.fonts_catalog[font_id].file_path
            if Path(font_path).exists():
                return font_path
        return None
    
    def list_fonts_by_category(self, category: str) -> List[str]:
        """Получить список шрифтов по категории"""
        return [
            font_id for font_id, font_info in self.fonts_catalog.items() 
            if category in font_info.best_for
        ]


# Глобальный экземпляр
font_manager = FontManager()
