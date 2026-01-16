"""
Главный модуль веб-приложения для генерации Reels и каруселей
"""
from app.env_loader import load_env

load_env()

from fastapi import FastAPI, Depends, HTTPException, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
from pathlib import Path

from app.api import auth, video_generation, carousel_generation, admin, templates, ai_providers
from app.core.config import settings
from app.core.database import engine, Base
from app.core.security import get_current_user
from routes.carousel import router as carousel_router
from app.routes.ui_carousel import router as ui_carousel_router
from app.auto_generator import auto_generator

# Создаем таблицы в БД
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Reels Generator",
    description="Веб-сервис для автоматизации генерации видео и каруселей для Instagram",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем API роуты
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(video_generation.router, prefix="/api/video", tags=["video"])
app.include_router(carousel_generation.router, prefix="/api/carousel", tags=["carousel"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(templates.router, prefix="/api/templates", tags=["templates"])
app.include_router(ai_providers.router, prefix="/api/ai", tags=["ai"])
app.include_router(carousel_router)
app.include_router(ui_carousel_router)


@app.on_event("startup")
async def start_background_jobs():
    await auto_generator.start()

# Статические файлы
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Главная страница"""
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reels Generator</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .feature { margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎬 Reels Generator</h1>
            <p>Веб-сервис для автоматизации генерации видео и каруселей для Instagram</p>
            
            <div class="feature">
                <h2>📹 Генерация видео</h2>
                <p>Создание Reels с наложением текста, музыки и эффектов</p>
            </div>
            
            <div class="feature">
                <h2>🎠 Генерация каруселей</h2>
                <p>Создание каруселей из изображений с текстом</p>
            </div>
            
            <div class="feature">
                <h2>🤖 AI-интеграция</h2>
                <p>Автоматическая генерация текстов и изображений</p>
            </div>
            
            <p><a href="/docs">📚 API Документация</a></p>
        </div>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Проверка состояния сервиса"""
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

