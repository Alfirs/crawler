"""
Сервис для генерации каруселей
"""
import os
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import textwrap

from app.models.generation import Generation, CarouselGeneration, GenerationStatus
from app.models.template import Template
from app.core.config import settings
from app.services.image_gen import ProviderModelUnavailable, ProviderRequestFailed
from app.services.img_analysis import dominant_palette
from app.services.image_style_adapter import generate_single_bg_from_style

# ==================== SINGLE BACKGROUND LOGIC ====================

def build_carousel_slides(style_image_path: str, slides_count: int):
    """Формирует пути для слайдов: обложка + повтор одного AI фона."""
    cover_path = style_image_path
    bg_path = generate_single_bg_from_style(cover_path)

    print(f"[BG] reuse -> slides 2..{slides_count}")
    slides = [cover_path]
    for _ in range(2, slides_count + 1):
        slides.append(bg_path)
    return slides

class CarouselGenerationService:
    """Сервис для генерации каруселей"""
    
    @staticmethod
    async def process_carousel_generation(generation_id: int, db: Session):
        """Обработка генерации карусели"""
        try:
            # Получаем генерацию
            generation = db.query(Generation).filter(Generation.id == generation_id).first()
            if not generation:
                return
            
            # Обновляем статус на "обрабатывается"
            generation.status = GenerationStatus.PROCESSING
            generation.started_at = datetime.utcnow()
            db.commit()
            
            # Получаем детали генерации карусели
            carousel_gen = db.query(CarouselGeneration).filter(
                CarouselGeneration.generation_id == generation_id
            ).first()
            
            if not carousel_gen:
                raise Exception("Детали генерации карусели не найдены")
            
            # Получаем шаблон если указан
            template = None
            if carousel_gen.template_id:
                template = db.query(Template).filter(Template.id == carousel_gen.template_id).first()
            
            # Создаем выходную директорию
            output_dir = Path(settings.OUTPUT_DIR) / str(generation.user_id) / str(generation_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем в зависимости от режима
            output_files = []
            
            if carousel_gen.mode == "backgrounds":
                output_files = await CarouselGenerationService._generate_from_backgrounds(
                    carousel_gen, template, output_dir
                )
            elif carousel_gen.mode == "user_images":
                output_files = await CarouselGenerationService._generate_from_user_images(
                    carousel_gen, template, output_dir
                )
            elif carousel_gen.mode == "ai_generated":
                output_files = await CarouselGenerationService._generate_from_ai(
                    carousel_gen, template, output_dir
                )
            elif carousel_gen.mode == "style_from_photo":
                output_files = await CarouselGenerationService._generate_from_style(
                    carousel_gen, template, output_dir
                )
            
            # Обновляем статус и результаты
            generation.status = GenerationStatus.COMPLETED
            generation.completed_at = datetime.utcnow()
            generation.output_files = output_files
            db.commit()
            
        except Exception as e:
            # Обновляем статус на "ошибка"
            generation.status = GenerationStatus.FAILED
            generation.completed_at = datetime.utcnow()
            generation.error_message = str(e)
            db.commit()
            print(f"Ошибка в генерации карусели {generation_id}: {e}")
    
    @staticmethod
    async def _generate_from_backgrounds(
        carousel_gen: CarouselGeneration,
        template: Template,
        output_dir: Path
    ) -> List[str]:
        """Генерация карусели из готовых фонов"""
        output_files = []
        
        for i, (background_path, text_data) in enumerate(zip(
            carousel_gen.background_images, 
            carousel_gen.text_content
        )):
            try:
                # Загружаем фоновое изображение
                background = Image.open(background_path)
                
                # Создаем изображение с текстом
                output_image = await CarouselGenerationService._add_text_to_image(
                    background, text_data, template
                )
                
                # Сохраняем результат
                output_file = output_dir / f"carousel_{i+1:03d}.jpg"
                output_image.save(output_file, "JPEG", quality=95)
                output_files.append(str(output_file))
                
            except Exception as e:
                print(f"Ошибка при генерации слайда {i+1}: {e}")
                continue
        
        return output_files
    
    @staticmethod
    async def _generate_from_user_images(
        carousel_gen: CarouselGeneration,
        template: Template,
        output_dir: Path
    ) -> List[str]:
        """Генерация карусели из пользовательских изображений"""
        output_files = []
        
        for i, (image_path, text_data) in enumerate(zip(
            carousel_gen.user_images,
            carousel_gen.text_content
        )):
            try:
                # Загружаем пользовательское изображение
                user_image = Image.open(image_path)
                
                # Создаем изображение с текстом
                output_image = await CarouselGenerationService._add_text_to_image(
                    user_image, text_data, template
                )
                
                # Сохраняем результат
                output_file = output_dir / f"carousel_{i+1:03d}.jpg"
                output_image.save(output_file, "JPEG", quality=95)
                output_files.append(str(output_file))
                
            except Exception as e:
                print(f"Ошибка при генерации слайда {i+1}: {e}")
                continue
        
        return output_files
    
    @staticmethod
    async def _generate_from_ai(
        carousel_gen: CarouselGeneration,
        template: Template,
        output_dir: Path
    ) -> List[str]:
        """Генерация карусели с AI-изображениями"""
        output_files = []
        
        # Здесь будет интеграция с AI сервисом для генерации изображений
        # Пока используем заглушку
        for i, (prompt, text_data) in enumerate(zip(
            carousel_gen.ai_prompts,
            carousel_gen.text_content
        )):
            try:
                # TODO: Интеграция с AI сервисом
                # ai_image = await generate_ai_image(prompt)
                
                # Пока создаем простое изображение
                ai_image = Image.new('RGB', (1080, 1920), color='lightblue')
                
                # Создаем изображение с текстом
                output_image = await CarouselGenerationService._add_text_to_image(
                    ai_image, text_data, template
                )
                
                # Сохраняем результат
                output_file = output_dir / f"carousel_{i+1:03d}.jpg"
                output_image.save(output_file, "JPEG", quality=95)
                output_files.append(str(output_file))
                
            except Exception as e:
                print(f"Ошибка при генерации слайда {i+1}: {e}")
                continue
        
        return output_files
    
    @staticmethod
    async def _generate_from_style(
        carousel_gen: CarouselGeneration,
        template: Template,
        output_dir: Path
    ) -> List[str]:
        """Генерация карусели в режиме style_from_photo (1 оригинал + N-1 сгенерированных)"""
        from app.services.image_style_adapter import get_style_adapter
        
        output_files = []
        
        # Получаем конфигурацию из carousel_gen.config или используем дефолты
        style_image_path = getattr(carousel_gen, 'style_image_path', None)
        slides_count = getattr(carousel_gen, 'slides_count', 5)
        prompt_hint = getattr(carousel_gen, 'prompt_hint', None)
        style_strength = getattr(carousel_gen, 'style_strength', 0.75)  # Дефолт 0.75 для более сильного стиля
        seed = getattr(carousel_gen, 'seed', None)
        
        # Получаем параметр with_text_overlay из config Generation
        generation = carousel_gen.generation
        with_text_overlay = True
        if generation and generation.config:
            with_text_overlay = generation.config.get('with_text_overlay', True)
        
        if not style_image_path or not Path(style_image_path).exists():
            raise ValueError(f"Style reference image not found: {style_image_path}")
        
        # Преобразуем style_strength в float если нужно
        if isinstance(style_strength, str):
            try:
                style_strength = float(style_strength)
            except:
                style_strength = 0.75  # Дефолт 0.75 для более сильного стиля
        
        # Слайд 1: оригинальное изображение (приводим к нужному размеру)
        try:
            original_image = Image.open(style_image_path)
            # Приводим к стандартному размеру для карусели
            original_image = original_image.resize((1080, 1350), Image.LANCZOS)
            
            # Добавляем текст только если with_text_overlay=True
            if with_text_overlay:
                text_data = carousel_gen.text_content[0] if carousel_gen.text_content else {}
                output_image = await CarouselGenerationService._add_text_to_image(
                    original_image, text_data, template
                )
            else:
                output_image = original_image
            
            output_file = output_dir / "carousel_001.jpg"
            output_image.save(output_file, "JPEG", quality=95)
            output_files.append(str(output_file))
        except Exception as e:
            print(f"Ошибка при обработке оригинального изображения: {e}")
            raise
        
        # Слайды 2..N: используем один сгенерированный фон
        generated_count = slides_count - 1
        if generated_count > 0:
            try:
                # Генерируем ОДИН фон для всех слайдов 2..N
                from app.services.image_style_adapter import generate_single_bg_from_style
                bg_path = generate_single_bg_from_style(style_image_path)
                
                # Цветокоррекция сгенерированного фона
                from PIL import ImageEnhance
                try:
                    # слегка затемнить/подогнать контраст
                    img = Image.open(bg_path).convert("RGB")
                    enhanced_img = ImageEnhance.Brightness(img).enhance(0.95)
                    enhanced_img = ImageEnhance.Contrast(enhanced_img).enhance(1.05)
                    enhanced_img.save(bg_path)
                    print(f"[BG] Applied color correction to {bg_path}")
                except Exception as e:
                    print(f"[BG] Color correction failed: {e}")
                
                print(f"[BG] reuse -> slides 2..{slides_count}")
                
                # Добавляем текст к каждому слайду, используя один фон
                for i in range(2, slides_count + 1):
                    try:
                        # Открываем один и тот же фон для каждого слайда
                        gen_image = Image.open(bg_path)
                        
                        # Применяем текст оверлей только если with_text_overlay=True
                        if with_text_overlay:
                            text_data = carousel_gen.text_content[i-1] if i-1 < len(carousel_gen.text_content) else {}
                            output_image = await CarouselGenerationService._add_text_to_image(
                                gen_image, text_data, template
                            )
                        else:
                            output_image = gen_image
                        
                        output_file = output_dir / f"carousel_{i:03d}.jpg"
                        output_image.save(output_file, "JPEG", quality=95)
                        output_files.append(str(output_file))
                    except Exception as e:
                        print(f"Ошибка при обработке сгенерированного изображения {i}: {e}")
                        continue
                        
            except (ProviderModelUnavailable, ProviderRequestFailed) as e:
                # Провайдер недоступен - делаем fallback на clean-фон
                print(f"[Carousel] AI-bg: fallback to clean background (no provider) -> {e}")
                # Извлекаем палитру из оригинального изображения
                palette = dominant_palette(style_image_path, k=3)
                base_color = palette[0] if palette else (31, 107, 67)
                
                # Генерируем градиентные фоны для слайдов 2..N
                for i in range(2, slides_count + 1):
                    try:
                        # Создаём градиентный фон
                        gradient_img = CarouselGenerationService._create_gradient_background(base_color)
                        
                        # Добавляем текст
                        if with_text_overlay:
                            text_data = carousel_gen.text_content[i-1] if i-1 < len(carousel_gen.text_content) else {}
                            output_image = await CarouselGenerationService._add_text_to_image(
                                gradient_img, text_data, template
                            )
                        else:
                            output_image = gradient_img
                        
                        output_file = output_dir / f"carousel_{i:03d}.jpg"
                        output_image.save(output_file, "JPEG", quality=95)
                        output_files.append(str(output_file))
                    except Exception as slide_e:
                        print(f"Ошибка при создании fallback-слайда {i}: {slide_e}")
                        continue
            except Exception as e:
                print(f"Ошибка при генерации стилизованных изображений: {e}")
                raise
        
        return output_files
    
    @staticmethod
    async def _add_text_to_image(
        base_image: Image.Image,
        text_data: Dict[str, Any],
        template: Template = None
    ) -> Image.Image:
        """Добавление текста к изображению"""
        # Создаем копию изображения
        image = base_image.copy()
        draw = ImageDraw.Draw(image)
        
        # Настройки из шаблона или по умолчанию
        if template:
            mask_x = template.mask_x
            mask_y = template.mask_y
            mask_width = template.mask_width
            mask_height = template.mask_height
            title_font_path = template.title_font
            title_size = template.title_size
            text_color = template.text_color
            box_color = template.box_color
            box_alpha = template.box_alpha
        else:
            # Значения по умолчанию
            mask_x = 50
            mask_y = 50
            mask_width = 500
            mask_height = 200
            title_font_path = "fonts/InstagramSansCondensedCYR-Bold.ttf"
            title_size = 48
            text_color = "#FFFFFF"
            box_color = "#000000"
            box_alpha = 50
        
        # Загружаем шрифт
        try:
            font = ImageFont.truetype(title_font_path, title_size)
        except:
            font = ImageFont.load_default()
        
        # Получаем текст
        title = text_data.get('title', '')
        description = text_data.get('description', '')
        
        # Рисуем фон для текста
        if box_alpha > 0:
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle(
                [mask_x, mask_y, mask_x + mask_width, mask_y + mask_height],
                fill=box_color + hex(int(box_alpha * 255 / 100))[2:].zfill(2)
            )
            image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(image)
        
        # Разбиваем текст на строки
        lines = textwrap.wrap(title, width=30)
        if description:
            lines.extend(textwrap.wrap(description, width=30))
        
        # Рисуем текст
        y_offset = mask_y + mask_height - len(lines) * (title_size + 10)
        for line in lines:
            # Получаем размеры текста
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Центрируем текст
            x = mask_x + (mask_width - text_width) // 2
            y = y_offset
            
            # Рисуем текст
            draw.text((x, y), line, fill=text_color, font=font)
            y_offset += text_height + 10
        
        return image
    
    @staticmethod
    def _create_gradient_background(base_color: tuple[int, int, int]):
        """Создаёт градиентный фон на основе базового цвета."""
        W, H = 1080, 1350
        img = Image.new("RGB", (W, H), base_color)
        overlay = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(overlay)
        for y in range(H):
            a = int(160 * (y / H))
            d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
        img.paste(overlay, (0, 0), overlay)
        return img





























