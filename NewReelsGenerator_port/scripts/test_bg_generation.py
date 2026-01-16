# scripts/test_bg_generation.py - Тест единственного вызова генерации фона
import os
import tempfile
from pathlib import Path
from PIL import Image

# Устанавливаем путь к проекту
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.image_style_adapter import generate_single_bg_from_style

def test_without_api_key():
    """Тест без API ключа - должен использовать fallback."""
    print("=== Тест без NEUROAPI_API_KEY ===")
    
    # Убираем ключ API
    os.environ.pop("NEUROAPI_API_KEY", None)
    
    # Создаем тестовое изображение
    test_img = Image.new("RGB", (200, 200), color=(50, 100, 150))
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        test_img.save(f.name, "JPEG")
        test_path = f.name
    
    try:
        # Генерируем фон - должен быть fallback
        bg_path = generate_single_bg_from_style(test_path)
        
        print(f"✓ Фон создан: {bg_path}")
        assert Path(bg_path).exists(), "Файл фона не создан"
        
        # Проверяем, что это PNG 1080x1350
        bg_img = Image.open(bg_path)
        assert bg_img.size == (1080, 1350), f"Неверный размер: {bg_img.size}"
        print(f"✓ Размер корректный: {bg_img.size}")
        
        # Повторный вызов должен вернуть тот же путь (кэш)
        bg_path2 = generate_single_bg_from_style(test_path)
        assert bg_path == bg_path2, "Кэш не работает"
        print("✓ Кэш работает корректно")
        
    finally:
        # Очистка
        os.unlink(test_path)
        if Path(bg_path).exists():
            os.unlink(bg_path)
    
    print("=== Тест завершен успешно ===\n")

def test_with_fake_api_key():
    """Тест с фейковым API ключом - должен fallback при ошибке."""
    print("=== Тест с фейковым NEUROAPI_API_KEY ===")
    
    # Устанавливаем фейковый ключ
    os.environ["NEUROAPI_API_KEY"] = "sk-fake-key-for-test"
    
    # Создаем тестовое изображение
    test_img = Image.new("RGB", (200, 200), color=(200, 50, 50))
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        test_img.save(f.name, "JPEG")
        test_path = f.name
    
    try:
        # Генерируем фон - должен быть fallback из-за ошибки API
        bg_path = generate_single_bg_from_style(test_path)
        
        print(f"✓ Фон создан (fallback): {bg_path}")
        assert Path(bg_path).exists(), "Файл фона не создан"
        
        # Проверяем размер
        bg_img = Image.open(bg_path)
        assert bg_img.size == (1080, 1350), f"Неверный размер: {bg_img.size}"
        print(f"✓ Размер корректный: {bg_img.size}")
        
    finally:
        # Очистка
        os.unlink(test_path)
        if Path(bg_path).exists():
            os.unlink(bg_path)
        os.environ.pop("NEUROAPI_API_KEY", None)
    
    print("=== Тест завершен успешно ===\n")

if __name__ == "__main__":
    test_without_api_key()
    test_with_fake_api_key()
    print("🎉 Все тесты пройдены успешно!")
