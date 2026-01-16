"""
Модель пользователя
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Социальные сети
    instagram_connected = Column(Boolean, default=False)
    tiktok_connected = Column(Boolean, default=False)
    
    # Настройки пользователя
    language = Column(String(10), default="ru")
    timezone = Column(String(50), default="Europe/Moscow")
    
    # Лимиты генерации
    daily_video_limit = Column(Integer, default=10)
    daily_carousel_limit = Column(Integer, default=5)
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"

