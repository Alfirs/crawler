"""
РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ РїСЂРёР»РѕР¶РµРЅРёСЏ
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # РћСЃРЅРѕРІРЅС‹Рµ РЅР°СЃС‚СЂРѕР№РєРё
    APP_NAME: str = "Reels Generator"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Р‘Р°Р·Р° РґР°РЅРЅС‹С…
    DATABASE_URL: str = "sqlite:///./reels_generator.db"
    
    # JWT РЅР°СЃС‚СЂРѕР№РєРё
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Р¤Р°Р№Р»РѕРІРѕРµ С…СЂР°РЅРёР»РёС‰Рµ
    UPLOAD_DIR: str = "uploads"
    OUTPUT_DIR: str = "output"
    STATIC_DIR: str = "static"
    
    # OpenAI / внешние LLM API
    OPENAI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # OpenAI для генерации текста
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # AITunnel API (только для генерации картинок)
    AITUNNEL_API_KEY: Optional[str] = None
    AITUNNEL_BASE_URL: str = "https://api.aitunnel.ru/v1"
    AITUNNEL_MODEL: str = "gemini-2.5-flash-image"  # Модель для обложки (если нужна)
    AITUNNEL_MODEL_BG: str = "flux-fast"  # Дешевая модель для фонов внутренних слайдов (deprecated для style_from_photo)
    AITUNNEL_MODEL_FALLBACK: str = "gpt-5-image"  # Запасная модель при недоступности основной
    AITUNNEL_URL_IMAGE: str = "https://api.aitunnel.ru/v1/images/generations"
    AITUNNEL_SEND_MODE: str = "auto"  # auto|multipart|json
    AITUNNEL_TIMEOUT_SEC: int = 120  # Таймаут запросов к AITunnel
    AITUNNEL_MODEL_CANDIDATES: str = "gemini-2.5-flash-image,gpt-5-image"  # CSV список кандидатов для автодетекта
    # Экономия: используйте локальную генерацию clean backgrounds вместо AI
    USE_LOCAL_BG_GENERATION: bool = False  # True = дешевле (clean backgrounds), False = AI генерация через AITunnel (по умолчанию)
    
    # РЎРѕС†РёР°Р»СЊРЅС‹Рµ СЃРµС‚Рё
    INSTAGRAM_API_KEY: Optional[str] = None
    TIKTOK_API_KEY: Optional[str] = None
    
    # Р›РёРјРёС‚С‹
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    MAX_VIDEOS_PER_REQUEST: int = 10
    MAX_CAROUSELS_PER_REQUEST: int = 5
    
    # Redis (РґР»СЏ РѕС‡РµСЂРµРґРµР№ Р·Р°РґР°С‡)
    REDIS_URL: str = "redis://localhost:6379"
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# РЎРѕР·РґР°РµРј РЅРµРѕР±С…РѕРґРёРјС‹Рµ РґРёСЂРµРєС‚РѕСЂРёРё
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.STATIC_DIR, exist_ok=True)

