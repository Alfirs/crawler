"""
Utilities for I/O operations - paths, slugification, image scaling
"""
from __future__ import annotations

import os
import re
import json
import datetime
from typing import Tuple

from PIL import Image

CANVAS_SIZE = (1080, 1350)


def slugify(text: str) -> str:
    """
    Преобразует текст в slug для использования в путях
    
    Args:
        text: Исходный текст
        
    Returns:
        Slug (латиница, цифры, дефисы, до 60 символов)
    """
    text = text.strip().lower()
    # Оставляем только буквы, цифры, пробелы, дефисы и подчёркивания
    text = re.sub(r"[^a-z0-9а-яё _-]", "", text, flags=re.IGNORECASE)
    # Заменяем пробелы на дефисы
    text = re.sub(r"\s+", "-", text)
    return text[:60] or "untitled"


def make_run_dir(base_dir: str, title: str) -> str:
    """
    Создаёт директорию для запуска генерации
    
    Args:
        base_dir: Базовая директория (outputs)
        title: Заголовок карусели
        
    Returns:
        Путь к созданной директории
    """
    slug = slugify(title)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base_dir, slug, ts)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def save_manifest(run_dir: str, data: dict) -> None:
    """
    Сохраняет манифест в JSON файл
    
    Args:
        run_dir: Директория для сохранения
        data: Словарь с данными манифеста
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cover_fit(img: Image.Image, target: Tuple[int, int] = CANVAS_SIZE) -> Image.Image:
    """
    Масштабирует изображение с центр-кропом (object-fit: cover)
    
    Args:
        img: Исходное изображение
        target: Целевой размер (ширина, высота)
        
    Returns:
        Обрезанное и масштабированное изображение
    """
    tw, th = target
    w, h = img.size
    
    if w == tw and h == th:
        return img.copy()
    
    # Вычисляем масштаб для покрытия всего целевого размера
    scale = max(tw / w, th / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    
    # Центр-кроп
    left = (nw - tw) // 2
    top = (nh - th) // 2
    right = left + tw
    bottom = top + th
    
    return img.crop((left, top, right, bottom)).convert("RGBA")


