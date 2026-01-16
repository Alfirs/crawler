from __future__ import annotations

import io
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from PIL import Image

from app.image_processing import WheelDetection


def extract_wheel_rgba(source: str | Path | bytes) -> Image.Image:
    """Return RGBA wheel image with transparent background using circle mask."""

    if isinstance(source, (str, Path)):
        image = Image.open(source).convert("RGBA")
    else:
        image = Image.open(io.BytesIO(source)).convert("RGBA")

    np_img = np.array(image)
    gray = cv2.cvtColor(np_img[..., :3], cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (9, 9), 0)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min(gray.shape) // 4,
        param1=120,
        param2=50,
        minRadius=int(min(gray.shape) * 0.2),
        maxRadius=int(min(gray.shape) * 0.48),
    )

    mask = np.zeros(gray.shape, dtype=np.uint8)
    if circles is not None:
        best = sorted(circles[0], key=lambda c: c[2], reverse=True)[0]
        x, y, r = map(int, best)
    else:
        # Fallback: assume wheel is centered
        h, w = gray.shape
        r = int(min(h, w) * 0.45)
        x, y = w // 2, h // 2
    cv2.circle(mask, (x, y), r, 255, -1)

    rgba = np.dstack([np_img[..., :3], mask])
    return Image.fromarray(rgba)


def overlay_wheels(
    base_image: Image.Image,
    wheel_rgba: Image.Image,
    detections: Sequence[WheelDetection],
    *,
    radius_scale: float = 1.0,
) -> Image.Image:
    """Overlay the wheel texture over detected wheel regions."""

    canvas = base_image.convert("RGBA")
    wheel_rgba = wheel_rgba.convert("RGBA")

    for detection in detections:
        scaled_radius = max(1, int(detection.radius * radius_scale))
        diameter = max(10, scaled_radius * 2)
        resized = wheel_rgba.resize((diameter, diameter), Image.LANCZOS)
        tmp = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        offset = scaled_radius
        position = (detection.x - offset, detection.y - offset)
        tmp.paste(resized, position, resized)
        canvas = Image.alpha_composite(canvas, tmp)

    return canvas.convert("RGB")
