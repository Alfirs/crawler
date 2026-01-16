"""
Интеграционный тест для проверки генерации карусели с AI-фонами
"""
import os
import sys
import asyncio
import tempfile
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient
from PIL import Image
import io


@pytest.fixture
def client():
    """Создаёт тестового клиента"""
    from app.min_app import app
    return TestClient(app)


@pytest.fixture
def test_cover_image():
    """Создаёт тестовое изображение обложки"""
    img = Image.new('RGB', (1080, 1350), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf


def test_generate_carousel_with_ai_backgrounds(client, test_cover_image, monkeypatch):
    """Тест генерации карусели с AI-фонами"""
    # Устанавливаем переменные окружения для теста
    monkeypatch.setenv("USE_AI_BACKGROUNDS", "true")
    monkeypatch.setenv("NEUROAPI_TEXT_MODEL", "gpt-5-mini")
    monkeypatch.setenv("NEUROAPI_IMAGE_MODEL", "gpt-image-1")
    
    # Проверяем что API ключ есть
    if not os.getenv("NEUROAPI_API_KEY"):
        pytest.skip("NEUROAPI_API_KEY не установлен, пропускаем тест")
    
    # Выполняем запрос
    response = client.post(
        "/generate",
        files={
            "cover_image": ("test_cover.png", test_cover_image, "image/png"),
        },
        data={
            "title": "5 ошибок целеполагания",
            "slides_count": "3",
            "bg_prompt": "modern office, people planning, dynamic composition",
            "watermark_text": "@alfirs"
        }
    )
    
    assert response.status_code == 200, f"Ошибка: {response.status_code} - {response.text[:500]}"
    
    # Проверяем что получили ZIP
    assert response.headers["content-type"] == "application/zip"
    
    # Сохраняем ZIP во временную директорию
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "carousel.zip")
        with open(zip_path, "wb") as f:
            f.write(response.content)
        
        # Распаковываем ZIP
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert len(files) >= 3, f"Ожидалось минимум 3 файла, получено {len(files)}"
            
            # Проверяем что файлы имеют разумный размер (>100KB)
            for filename in files:
                if filename.endswith('.png'):
                    file_data = zf.read(filename)
                    assert len(file_data) > 100 * 1024, f"Файл {filename} слишком маленький: {len(file_data)} байт"
                    
                    # Проверяем что это валидное изображение
                    img = Image.open(io.BytesIO(file_data))
                    assert img.size[0] > 0 and img.size[1] > 0


def test_logs_contain_image_api_calls(capsys):
    """Проверяет что в логах есть вызовы Image API"""
    # Этот тест нужно запускать вручную с реальным сервером
    # или мокать логирование
    pass


if __name__ == "__main__":
    # Запуск теста напрямую
    pytest.main([__file__, "-v"])










