"""
Сервис для генерации видео
"""
import os
import random
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.generation import Generation, VideoGeneration, GenerationStatus
from app.models.template import Template
from app.core.config import settings

class VideoGenerationService:
    """Сервис для генерации видео"""
    
    @staticmethod
    async def process_video_generation(generation_id: int, db: Session):
        """Обработка генерации видео"""
        try:
            # Получаем генерацию
            generation = db.query(Generation).filter(Generation.id == generation_id).first()
            if not generation:
                return
            
            # Обновляем статус на "обрабатывается"
            generation.status = GenerationStatus.PROCESSING
            generation.started_at = datetime.utcnow()
            db.commit()
            
            # Получаем детали генерации видео
            video_gen = db.query(VideoGeneration).filter(
                VideoGeneration.generation_id == generation_id
            ).first()
            
            if not video_gen:
                raise Exception("Детали генерации видео не найдены")
            
            # Получаем шаблон если указан
            template = None
            if video_gen.template_id:
                template = db.query(Template).filter(Template.id == video_gen.template_id).first()
            
            # Создаем выходную директорию
            output_dir = Path(settings.OUTPUT_DIR) / str(generation.user_id) / str(generation_id)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Обрабатываем каждое видео
            output_files = []
            for i, (video_file, title, description) in enumerate(zip(
                video_gen.video_files, 
                video_gen.titles, 
                video_gen.descriptions
            )):
                try:
                    # Генерируем выходной файл
                    output_file = output_dir / f"reel_{i+1:03d}.mp4"
                    
                    # Здесь вызываем существующую логику из ReelsGen.py
                    await VideoGenerationService._generate_single_video(
                        video_file=video_file,
                        music_file=video_gen.music_file,
                        output_file=str(output_file),
                        title=title,
                        description=description,
                        template=template,
                        music_mode=video_gen.music_mode,
                        keep_original_audio=video_gen.keep_original_audio
                    )
                    
                    output_files.append(str(output_file))
                    
                except Exception as e:
                    print(f"Ошибка при генерации видео {i+1}: {e}")
                    continue
            
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
            print(f"Ошибка в генерации видео {generation_id}: {e}")
    
    @staticmethod
    async def _generate_single_video(
        video_file: str,
        music_file: str,
        output_file: str,
        title: str,
        description: str,
        template: Template = None,
        music_mode: str = "random",
        keep_original_audio: bool = False
    ):
        """Генерация одного видео"""
        # Импортируем функции из существующего ReelsGen.py
        import sys
        sys.path.append(str(Path(__file__).parent.parent.parent))
        
        try:
            import ReelsGen as RG
            
            # Настройки маски (по умолчанию или из шаблона)
            if template:
                mask = (template.mask_x, template.mask_y, template.mask_width, template.mask_height)
                caption_mask = (template.caption_mask_x, template.caption_mask_y, 
                              template.caption_mask_width, template.caption_mask_height)
                title_font = template.title_font
                title_size = template.title_size
                caption_size = template.caption_size
                text_color = template.text_color
                box_color = template.box_color
                box_alpha = template.box_alpha / 100.0
                full_vertical = template.full_vertical
                gradient_height = template.gradient_height
                gradient_strength = template.gradient_strength
            else:
                # Значения по умолчанию
                mask = (50, 50, 500, 200)
                caption_mask = (50, 1700, 400, 100)
                title_font = "fonts/InstagramSansCondensedCYR-Bold.ttf"
                title_size = 48
                caption_size = 36
                text_color = "#FFFFFF"
                box_color = "#000000"
                box_alpha = 0.5
                full_vertical = False
                gradient_height = None
                gradient_strength = None
            
            # Выбираем музыку
            music_path = None
            if not keep_original_audio and music_file:
                music_path = music_file
            elif not keep_original_audio and music_mode != "none":
                # Используем случайную музыку из папки
                music_dir = Path("music")
                if music_dir.exists():
                    music_files = list(music_dir.glob("*.mp3"))
                    if music_files:
                        music_path = str(random.choice(music_files))
            
            # Генерируем видео
            RG.process_video(
                video_path=video_file,
                music_path=music_path,
                out_path=output_file,
                title=title,
                description=description,
                mask=mask,
                caption_mask=caption_mask,
                title_font=title_font,
                caption_font=title_font,
                title_size=title_size,
                caption_size=caption_size,
                text_color=text_color,
                box_color=box_color,
                box_alpha=box_alpha,
                full_vertical=full_vertical,
                top_gradient_height=gradient_height,
                top_gradient_strength=gradient_strength
            )
            
        except Exception as e:
            print(f"Ошибка в _generate_single_video: {e}")
            raise































