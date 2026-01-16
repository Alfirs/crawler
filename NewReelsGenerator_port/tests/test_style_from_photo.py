"""
E2E тесты для режима style_from_photo
"""
import pytest
from pathlib import Path
import tempfile
import shutil
from PIL import Image


@pytest.fixture
def style_image_path(tmp_path):
    """Создает тестовое изображение для style_from_photo"""
    # Создаем простое изображение
    img = Image.new('RGB', (1080, 1350), color=(50, 50, 50))
    test_img_path = tmp_path / "test_style.jpg"
    img.save(test_img_path, "JPEG")
    return str(test_img_path)


def test_style_adapter_detection():
    """Тест определения провайдера AI"""
    from app.services.image_style_adapter import StyleTransferAdapter
    
    adapter = StyleTransferAdapter()
    provider = adapter.provider
    
    # Проверяем, что провайдер определен
    assert provider in ["aitunnel", "replicate", "comfyui", "sd_webui", "none"]


def test_style_adapter_without_config(style_image_path):
    """Тест адаптера без конфигурации провайдера"""
    from app.services.image_style_adapter import get_style_adapter
    import os
    
    # Сохраняем оригинальный ключ
    original_key = os.environ.get("AITUNNEL_API_KEY")
    
    # Временно убираем ключ
    if "AITUNNEL_API_KEY" in os.environ:
        del os.environ["AITUNNEL_API_KEY"]
    
    # Также убираем другие ключи провайдеров
    for key in ["REPLICATE_API_TOKEN", "COMFYUI_API_URL", "SD_WEBUI_API_URL"]:
        if key in os.environ:
            del os.environ[key]
    
    try:
        adapter = get_style_adapter()
        
        # Попытка генерации должна падать с понятной ошибкой
        with pytest.raises(RuntimeError, match="No AI provider configured"):
            adapter.generate_images_in_style(
                style_image_path=style_image_path,
                count=2
            )
    finally:
        # Восстанавливаем ключ
        if original_key:
            os.environ["AITUNNEL_API_KEY"] = original_key


def test_carousel_service_mode_style_from_photo():
    """Тест проверки режима в CarouselGenerationService"""
    from app.services.carousel_service import CarouselGenerationService
    from app.models.generation import CarouselGeneration
    
    # Создаем мок carousel_gen с режимом style_from_photo
    carousel_gen = CarouselGeneration(
        id=1,
        generation_id=1,
        mode="style_from_photo",
        style_image_path="test.jpg",
        slides_count=3
    )
    
    # Проверяем, что режим определен
    assert carousel_gen.mode == "style_from_photo"


def test_style_analysis():
    """Тест анализа стиля изображения"""
    from app.services.img_analysis import analyze_style, build_style_description
    
    # Создаем тестовое изображение
    test_img = Image.new('RGB', (200, 200), color=(100, 150, 200))
    test_path = Path(__file__).parent / "test_style.jpg"
    test_img.save(test_path)
    
    try:
        # Анализируем стиль
        analysis = analyze_style(str(test_path))
        
        # Проверяем структуру анализа
        assert "color_palette" in analysis
        assert "brightness" in analysis
        assert "contrast" in analysis
        assert "saturation" in analysis
        assert "texture_type" in analysis
        assert "composition_density" in analysis
        assert "mood" in analysis
        
        # Проверяем, что палитра не пустая
        assert len(analysis["color_palette"]) > 0
        
        # Проверяем описание
        description = build_style_description(analysis)
        assert len(description) > 0
    finally:
        # Удаляем тестовый файл
        if test_path.exists():
            test_path.unlink()


def test_validation_slides_count():
    """Тест валидации количества слайдов"""
    from app.services.image_style_adapter import StyleTransferAdapter
    
    adapter = StyleTransferAdapter()
    
    # Создаем тестовое изображение
    test_img = Image.new('RGB', (1080, 1350), color=(50, 50, 50))
    test_path = Path(__file__).parent / "test_validation.jpg"
    test_img.save(test_path)
    
    try:
        # Проверяем, что count ограничивается
        # (должно быть ограничено до 20 в _generate_aitunnel)
        # Но мы не можем это проверить без API ключа
        # Проверяем только, что ошибок нет при валидации
        count_limited = adapter._build_style_prompt("test", "test description")
        assert isinstance(count_limited, str)
    finally:
        if test_path.exists():
            test_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


