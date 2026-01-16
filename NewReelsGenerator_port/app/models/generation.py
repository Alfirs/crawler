"""
Модели для генерации контента
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum

class GenerationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class GenerationType(str, enum.Enum):
    VIDEO = "video"
    CAROUSEL = "carousel"

class Generation(Base):
    __tablename__ = "generations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(Enum(GenerationType), nullable=False)
    status = Column(Enum(GenerationStatus), default=GenerationStatus.PENDING)
    
    # Конфигурация генерации
    config = Column(JSON)
    
    # Результаты
    output_files = Column(JSON)  # Список путей к сгенерированным файлам
    error_message = Column(Text)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Связи
    user = relationship("User")
    
    def __repr__(self):
        return f"<Generation(id={self.id}, type={self.type}, status={self.status})>"

class VideoGeneration(Base):
    __tablename__ = "video_generations"
    
    id = Column(Integer, primary_key=True, index=True)
    generation_id = Column(Integer, ForeignKey("generations.id"), nullable=False)
    
    # Исходные данные
    video_files = Column(JSON)  # Список исходных видео
    music_file = Column(String(255))
    titles = Column(JSON)  # Список заголовков
    descriptions = Column(JSON)  # Список описаний
    
    # Настройки
    template_id = Column(Integer, ForeignKey("templates.id"))
    music_mode = Column(String(50), default="random")
    keep_original_audio = Column(Boolean, default=False)
    
    # Результаты
    output_videos = Column(JSON)  # Список сгенерированных видео
    
    # Связи
    generation = relationship("Generation")
    template = relationship("Template")
    
    def __repr__(self):
        return f"<VideoGeneration(id={self.id}, generation_id={self.generation_id})>"

class CarouselGeneration(Base):
    __tablename__ = "carousel_generations"
    
    id = Column(Integer, primary_key=True, index=True)
    generation_id = Column(Integer, ForeignKey("generations.id"), nullable=False)
    
    # Режим генерации
    mode = Column(String(50), nullable=False)  # "backgrounds", "user_images", "ai_generated", "style_from_photo"
    
    # Исходные данные
    background_images = Column(JSON)  # Для режима backgrounds
    user_images = Column(JSON)  # Для режима user_images
    ai_prompts = Column(JSON)  # Для режима ai_generated
    
    # Настройки для режима style_from_photo
    style_image_path = Column(String(500))  # Путь к референсному изображению
    slides_count = Column(Integer, default=5)  # Общее количество слайдов
    prompt_hint = Column(Text)  # Подсказка для содержания
    style_strength = Column(String(10), default="0.6")  # Сила переноса стиля (0.0-1.0)
    seed = Column(Integer)  # Seed для воспроизводимости
    
    # Настройки
    template_id = Column(Integer, ForeignKey("templates.id"))
    text_content = Column(JSON)  # Тексты для наложения
    
    # Результаты
    output_images = Column(JSON)  # Список сгенерированных изображений
    
    # Связи
    generation = relationship("Generation")
    template = relationship("Template")
    
    def __repr__(self):
        return f"<CarouselGeneration(id={self.id}, mode={self.mode})>"





























