#!/usr/bin/env python3
"""
Скрипт для запуска веб-сервера Reels Generator
"""
import uvicorn
import os
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.append(str(Path(__file__).parent))

if __name__ == "__main__":
    # Создаем необходимые директории
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    print("🚀 Запуск Reels Generator Web Server...")
    print("📱 Веб-интерфейс: http://localhost:8000")
    print("📚 API документация: http://localhost:8000/docs")
    print("🔧 Админ-панель: http://localhost:8000/api/admin")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )



