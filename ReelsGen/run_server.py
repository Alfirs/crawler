#!/usr/bin/env python3
"""
Скрипт для запуска Instagram Carousel Generator
"""
import os
import sys

def main():
    """Запуск сервера разработки"""
    
    # Проверяем что мы в правильной директории
    if not os.path.exists("app/min_app.py"):
        print("❌ Ошибка: Запускайте скрипт из корневой директории проекта")
        print("   Должен существовать файл app/min_app.py")
        sys.exit(1)
    
    # Проверяем .env файл
    if not os.path.exists(".env"):
        print("⚠️  Предупреждение: Не найден файл .env")
        print("   Скопируйте env.example в .env и укажите ваш API ключ NeuroAPI")
        print("   Или установите NEUROAPI_DRYRUN=true для тестирования без API")
        print()
    
    # Проверяем зависимости
    try:
        import fastapi
        import uvicorn
        import pillow
        import httpx
        print("✅ Все зависимости установлены")
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("   Установите зависимости: pip install -r requirements.txt")
        sys.exit(1)
    
    # Запускаем сервер
    print("🚀 Запуск Instagram Carousel Generator...")
    print("📡 Сервер будет доступен по адресу: http://127.0.0.1:8010")
    print("🔄 Режим автоперезагрузки включён (для разработки)")
    print("⏹️  Нажмите Ctrl+C для остановки")
    print()
    
    try:
        os.system("uvicorn app.min_app:app --host 127.0.0.1 --port 8010 --reload")
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")


if __name__ == "__main__":
    main()

