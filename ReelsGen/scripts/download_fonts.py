#!/usr/bin/env python3
"""
Скрипт для загрузки базовых шрифтов Google Fonts
"""
import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.font_manager import font_manager


async def download_essential_fonts():
    """Скачать основные шрифты для системы"""
    
    # Список приоритетных шрифтов для скачивания
    essential_fonts = [
        # Основные универсальные
        "Inter-Bold",
        "Inter-Regular", 
        
        # Заголовки
        "Montserrat-Bold",
        "Poppins-Bold",
        "Oswald-Bold",
        
        # Основной текст
        "OpenSans-Regular",
        "Source-Regular",
        
        # Элегантные
        "Playfair-Bold", 
        "Raleway-Bold",
        
        # Креативные
        "Comfortaa-Bold",
        "Righteous-Regular"
    ]
    
    print("[FONTS] Загрузка базовых шрифтов Google Fonts...")
    print(f"Всего к загрузке: {len(essential_fonts)} шрифтов\n")
    
    successful = 0
    failed = 0
    
    for font_id in essential_fonts:
        try:
            print(f"[DOWNLOAD] {font_id}...", end=" ")
            
            # Проверяем доступность и скачиваем если нужно
            is_available = await font_manager.ensure_font_available(font_id)
            
            if is_available:
                print("[OK]")
                successful += 1
            else:
                print("[FAILED]")
                failed += 1
                
        except Exception as e:
            print(f"[ERROR] {e}")
            failed += 1
    
    print(f"\n[RESULT]")
    print(f"[SUCCESS] Успешно: {successful}")
    print(f"[FAILED] Ошибки: {failed}")
    print(f"[FOLDER] Папка шрифтов: {font_manager.fonts_dir}")
    
    # Показываем доступные шрифты
    print(f"\n[FONTS] Доступные шрифты:")
    for font_id, font_info in font_manager.fonts_catalog.items():
        if font_manager.get_font_path(font_id):
            status = "[OK]"
        else:
            status = "[MISSING]"
        print(f"{status} {font_id} ({font_info.category}, {font_info.weight})")


if __name__ == "__main__":
    asyncio.run(download_essential_fonts())
