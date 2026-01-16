# app/services/img_analysis.py
from __future__ import annotations
import os
from typing import List, Tuple, Dict, Optional
from pathlib import Path

def _safe_cv2():
    try:
        import cv2  # type: ignore
        return cv2
    except Exception:
        return None

def dominant_palette(path: str, k: int = 5) -> List[Tuple[int,int,int]]:
    cv2 = _safe_cv2()
    if not cv2 or not os.path.exists(path):
        # тёмная дефолтная палитра
        return [(20,22,28), (35,37,45), (60,62,74), (92,96,116), (140,146,170)]
    import numpy as np
    from sklearn.cluster import KMeans
    img = cv2.imread(path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    sample = img.reshape(-1,3)[::20]
    km = KMeans(n_clusters=k, n_init=4).fit(sample)
    centers = (km.cluster_centers_).clip(0,255).astype(int).tolist()
    return [tuple(map(int, c)) for c in centers]

def safe_palette_from(path: str, k: int = 5) -> list[tuple[int, int, int]]:
    try:
        return dominant_palette(path, k=k)
    except Exception:
        return [(20,22,28),(35,37,45),(60,62,74)]

def subject_side(path: str) -> str:
    cv2 = _safe_cv2()
    if not cv2 or not os.path.exists(path):
        return "center"
    img = cv2.imread(path, 0)
    img = cv2.GaussianBlur(img, (0,0), 2)
    edges = cv2.Canny(img, 60, 180)
    h, w = edges.shape
    left = edges[:, :w//2].sum()
    right = edges[:, w//2:].sum()
    if abs(left-right) < 0.08*edges.sum():
        return "center"
    return "left" if left > right else "right"

def template_type(path: str) -> str:
    cv2 = _safe_cv2()
    if not cv2 or not os.path.exists(path):
        return "flat_gradient"
    img = cv2.imread(path, 0)
    var = cv2.Laplacian(img, cv2.CV_64F).var()
    return "flat_gradient" if var < 60 else "busy_photo"


def analyze_style(image_path: str) -> Dict[str, any]:
    """
    Локальный анализ стилистики изображения.
    Возвращает словарь с характеристиками стиля:
    - color_palette: основные цвета
    - brightness: яркость (0-255)
    - contrast: контраст (0-1)
    - saturation: насыщенность (0-1)
    - texture_type: тип текстуры (smooth/rough/grainy)
    - composition_density: плотность деталей (low/medium/high)
    - mood: настроение (warm/cool/neutral)
    """
    cv2 = _safe_cv2()
    if not cv2 or not os.path.exists(image_path):
        return _default_style_analysis()
    
    try:
        import numpy as np
        img = cv2.imread(image_path)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # 1. Цветовая палитра (уже есть функция)
        palette = dominant_palette(image_path, k=5)
        
        # 2. Яркость (среднее значение по яркости)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        
        # 3. Контраст (стандартное отклонение)
        contrast = float(np.std(gray)) / 255.0
        
        # 4. Насыщенность
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        saturation = float(np.mean(hsv[:, :, 1])) / 255.0
        
        # 5. Тип текстуры (на основе вариации яркости)
        texture_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if texture_variance < 100:
            texture_type = "smooth"
        elif texture_variance < 500:
            texture_type = "moderate"
        else:
            texture_type = "rough"
        
        # 6. Плотность деталей
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.sum(edges > 0)) / (edges.shape[0] * edges.shape[1])
        if edge_density < 0.05:
            composition_density = "low"
        elif edge_density < 0.15:
            composition_density = "medium"
        else:
            composition_density = "high"
        
        # 7. Настроение (теплое/холодное на основе преобладающих цветов)
        avg_color = np.mean(img_rgb.reshape(-1, 3), axis=0)
        # Теплые цвета имеют больше красного/желтого, холодные - синего
        warm_score = (avg_color[0] + avg_color[1]) / (avg_color[2] + 1)
        if warm_score > 1.3:
            mood = "warm"
        elif warm_score < 0.9:
            mood = "cool"
        else:
            mood = "neutral"
        
        return {
            "color_palette": palette,
            "brightness": brightness,
            "contrast": contrast,
            "saturation": saturation,
            "texture_type": texture_type,
            "composition_density": composition_density,
            "mood": mood,
        }
    except Exception as exc:
        print(f"WARN: style analysis failed for {image_path}: {exc}")
        return _default_style_analysis()


def _default_style_analysis() -> Dict[str, any]:
    """Возвращает дефолтные значения анализа стиля."""
    return {
        "color_palette": [(20, 22, 28), (35, 37, 45), (60, 62, 74)],
        "brightness": 128.0,
        "contrast": 0.5,
        "saturation": 0.5,
        "texture_type": "moderate",
        "composition_density": "medium",
        "mood": "neutral",
    }


def build_style_description(style_analysis: Dict[str, any]) -> str:
    """
    Преобразует результаты анализа стиля в текстовое описание
    для включения в промпт генерации изображения.
    """
    palette_desc = ", ".join([f"rgb{r},{g},{b}" for r, g, b in style_analysis["color_palette"][:3]])
    
    brightness_desc = "яркое" if style_analysis["brightness"] > 180 else "темное" if style_analysis["brightness"] < 80 else "среднее"
    contrast_desc = "высокий контраст" if style_analysis["contrast"] > 0.6 else "низкий контраст" if style_analysis["contrast"] < 0.3 else "умеренный контраст"
    saturation_desc = "насыщенные цвета" if style_analysis["saturation"] > 0.6 else "приглушенные цвета" if style_analysis["saturation"] < 0.3 else "средняя насыщенность"
    
    mood_desc = "теплое настроение" if style_analysis["mood"] == "warm" else "холодное настроение" if style_analysis["mood"] == "cool" else "нейтральное настроение"
    texture_desc = "гладкая текстура" if style_analysis["texture_type"] == "smooth" else "шероховатая текстура" if style_analysis["texture_type"] == "rough" else "умеренная текстура"
    density_desc = "минималистичная композиция" if style_analysis["composition_density"] == "low" else "детализированная композиция" if style_analysis["composition_density"] == "high" else "умеренная детализация"
    
    return f"""Анализ стиля референса:
- Основные цвета: {palette_desc}
- Яркость: {brightness_desc}, {contrast_desc}
- Насыщенность: {saturation_desc}
- Текстура: {texture_desc}
- Композиция: {density_desc}
- Настроение: {mood_desc}"""
