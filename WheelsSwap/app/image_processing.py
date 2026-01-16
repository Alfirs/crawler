from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.config import ImageProcessingSettings
from app.wheels import Wheel

PROMPT_TEMPLATE = (
    "Replace the car wheels with {description}. Keep the car body, paint, reflections, "
    "background and lighting exactly the same. Modify only the masked wheel areas."
)

COLOR_REFERENCE_MAP = {
    "black": np.array([30, 30, 30]),
    "dark gray": np.array([70, 70, 70]),
    "silver": np.array([170, 170, 170]),
    "white": np.array([230, 230, 230]),
    "red": np.array([180, 40, 40]),
    "orange": np.array([210, 110, 40]),
    "yellow": np.array([230, 190, 60]),
    "green": np.array([60, 140, 60]),
    "blue": np.array([60, 90, 170]),
    "navy": np.array([30, 50, 110]),
    "brown": np.array([120, 80, 50]),
    "dark teal": np.array([40, 80, 100]),
    "petrol blue": np.array([35, 70, 90]),
}


@dataclass
class WheelDetection:
    x: int
    y: int
    radius: int
    confidence: float | None = None


@dataclass
class CarMeta:
    description: str
    color_name: Optional[str] = None
    hex_color: Optional[str] = None
    median_rgb: Optional[Tuple[float, float, float]] = None


def load_and_normalize_image(source: str | Path | bytes, max_size: int) -> Image.Image:
    """Load the image, convert it to RGB and optionally resize to the target max size."""

    if isinstance(source, (str, Path)):
        image = Image.open(source)
    else:
        image = Image.open(io.BytesIO(source))
    image = image.convert("RGB")
    width, height = image.size
    longest = max(width, height)
    if longest > max_size:
        scale = max_size / float(longest)
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.LANCZOS)
    return image


def detect_wheels(image: Image.Image, settings: ImageProcessingSettings) -> List[WheelDetection]:
    """Detect wheel circles using OpenCV. Returns up to two best matches."""

    np_image = np.array(image)
    gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    # Focus the lower part of the image to avoid false positives on the roof or windows.
    mask = np.zeros_like(gray)
    lower_start = int(height * (1 - settings.wheel_region_height_ratio))
    mask[lower_start:, :] = 255
    focused_gray = cv2.bitwise_and(gray, gray, mask=mask)
    blur = cv2.GaussianBlur(focused_gray, (settings.gaussian_kernel, settings.gaussian_kernel), 0)

    min_dist = max(20, int(width * settings.hough_min_dist_ratio))
    min_radius = max(10, int(min(height, width) * settings.hough_min_radius_ratio))
    max_radius = max(min_radius + 2, int(min(height, width) * settings.hough_max_radius_ratio))

    detections: List[WheelDetection] = _detect_with_hough(
        blur=blur,
        gray=gray,
        lower_start=lower_start,
        max_radius=max_radius,
        settings=settings,
        min_dist=min_dist,
        min_radius=min_radius,
    )

    if len(detections) < 2:
        contour_candidates = _detect_with_contours(
            blur=blur,
            gray=gray,
            lower_start=lower_start,
            min_radius=min_radius,
            max_radius=max_radius,
        )
        for candidate in contour_candidates:
            if not _is_close(candidate, detections, threshold=0.1 * width):
                detections.append(candidate)
    if len(detections) < 2:
        slice_candidates = _detect_in_slices(
            gray=gray,
            focused_gray=focused_gray,
            lower_start=lower_start,
            settings=settings,
        )
        for candidate in slice_candidates:
            if not _is_close(candidate, detections, threshold=0.1 * width):
                detections.append(candidate)

    # Sort by radius desc then by x position to keep front/back order deterministic.
    detections.sort(key=lambda d: (-d.radius, d.x))
    return detections


def generate_wheel_mask(
    image_size: Tuple[int, int],
    detections: Sequence[WheelDetection],
    padding_ratio: float,
) -> Image.Image:
    """Create a binary mask that isolates the detected wheel regions."""

    mask = Image.new("L", image_size, 0)
    draw = ImageDraw.Draw(mask)
    for detection in detections:
        radius = detection.radius * (1.0 + padding_ratio)
        bbox = (
            int(round(detection.x - radius)),
            int(round(detection.y - radius)),
            int(round(detection.x + radius)),
            int(round(detection.y + radius)),
        )
        draw.ellipse(bbox, fill=255)
    return mask


def _detect_with_hough(
    *,
    blur: np.ndarray,
    gray: np.ndarray,
    lower_start: int,
    max_radius: int,
    settings: ImageProcessingSettings,
    min_dist: int,
    min_radius: int,
) -> List[WheelDetection]:
    detections: List[WheelDetection] = []
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=settings.hough_dp,
        minDist=min_dist,
        param1=settings.hough_param1,
        param2=settings.hough_param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    if circles is None:
        return detections

    for x, y, r in np.round(circles[0, :]).astype(int):
        if y < lower_start:
            continue
        refined_radius = _refine_radius(gray, x, y, r, max_radius)
        detections.append(WheelDetection(x=x, y=y, radius=refined_radius))
    return detections


def _detect_with_contours(
    *,
    blur: np.ndarray,
    gray: np.ndarray,
    lower_start: int,
    min_radius: int,
    max_radius: int,
) -> List[WheelDetection]:
    """Fallback contour-based detection for low-contrast wheels."""

    edges = cv2.Canny(blur, 30, 90)
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detections: List[WheelDetection] = []
    min_area = math.pi * (min_radius**2) * 0.4
    height, width = gray.shape

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter == 0:
            continue
        circularity = 4 * math.pi * area / (perimeter**2)
        if circularity < 0.4:
            continue
        (x, y), radius = cv2.minEnclosingCircle(contour)
        if not (min_radius <= radius <= max_radius):
            continue
        if y < lower_start or x < 0 or y < 0 or x >= width or y >= height:
            continue
        detections.append(WheelDetection(x=int(x), y=int(y), radius=int(radius)))

    detections.sort(key=lambda d: (-d.radius, d.x))
    return detections


def _detect_in_slices(
    *,
    gray: np.ndarray,
    focused_gray: np.ndarray,
    lower_start: int,
    settings: ImageProcessingSettings,
) -> List[WheelDetection]:
    """Fallback detection that scans overlapping vertical slices independently."""

    height, width = gray.shape
    slices = [
        (0, int(width * 0.65)),
        (int(width * 0.35), width),
    ]
    detections: List[WheelDetection] = []

    for x_start, x_end in slices:
        roi = focused_gray[:, x_start:x_end]
        if roi.size == 0:
            continue
        roi_blur = cv2.GaussianBlur(roi, (settings.gaussian_kernel, settings.gaussian_kernel), 0)
        roi_width = max(1, x_end - x_start)
        min_dim = min(height, roi_width)
        dynamic_min_radius = max(6, int(min_dim * max(settings.hough_min_radius_ratio * 0.5, 0.03)))
        dynamic_max_radius = max(
            dynamic_min_radius + 2,
            int(min_dim * min(settings.hough_max_radius_ratio * 1.5, 0.45)),
        )
        circles = cv2.HoughCircles(
            roi_blur,
            cv2.HOUGH_GRADIENT,
            dp=settings.hough_dp,
            minDist=max(15, int(roi_width * 0.2)),
            param1=max(50, settings.hough_param1 - 20),
            param2=max(18, settings.hough_param2 - 10),
            minRadius=dynamic_min_radius,
            maxRadius=dynamic_max_radius,
        )
        if circles is None:
            continue
        for x, y, r in np.round(circles[0, :]).astype(int):
            if y < lower_start:
                continue
            refined_radius = _refine_radius(gray, x + x_start, y, r, dynamic_max_radius)
            detections.append(WheelDetection(x=x + x_start, y=y, radius=refined_radius))
    detections.sort(key=lambda d: (-d.radius, d.x))
    return detections


def _refine_radius(
    gray: np.ndarray,
    x: int,
    y: int,
    initial_radius: int,
    max_radius: int,
    *,
    samples: int = 32,
    inner_offset: int = 4,
) -> int:
    """Expand radius outward until gradient around circumference is strongest."""

    height, width = gray.shape

    def score(radius: int) -> float:
        total = 0.0
        count = 0
        inner_radius = max(1, radius - inner_offset)
        for angle in np.linspace(0, 2 * np.pi, samples, endpoint=False):
            outer_x = int(round(x + radius * np.cos(angle)))
            outer_y = int(round(y + radius * np.sin(angle)))
            inner_x = int(round(x + inner_radius * np.cos(angle)))
            inner_y = int(round(y + inner_radius * np.sin(angle)))
            if (
                0 <= outer_x < width
                and 0 <= outer_y < height
                and 0 <= inner_x < width
                and 0 <= inner_y < height
            ):
                total += abs(int(gray[outer_y, outer_x]) - int(gray[inner_y, inner_x]))
                count += 1
        return total / count if count else 0.0

    best_radius = initial_radius
    best_score = score(initial_radius)
    decay_threshold = best_score * 0.6
    for radius in range(initial_radius + 1, max_radius + 1):
        current_score = score(radius)
        if current_score >= best_score:
            best_score = current_score
            best_radius = radius
        elif current_score < decay_threshold:
            break
    return best_radius


def _is_close(candidate: WheelDetection, existing: Iterable[WheelDetection], threshold: float) -> bool:
    return any(abs(candidate.x - det.x) < threshold and abs(candidate.y - det.y) < threshold for det in existing)


def pil_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """Serialize PIL image to bytes."""

    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return buffer.read()


def build_prompt(wheel: Wheel) -> str:
    """Generate an English prompt for the Seedream edit model."""

    description = wheel.short_description or wheel.name
    return PROMPT_TEMPLATE.format(description=description)


def extract_basic_car_meta(image: Image.Image) -> CarMeta:
    """Return a lightweight description of the car for catalog renders."""

    np_img = np.array(image)
    height, width = np_img.shape[:2]
    top = int(height * 0.35)
    bottom = int(height * 0.8)
    left = int(width * 0.15)
    right = int(width * 0.85)
    roi = np_img[top:bottom, left:right]
    if roi.size == 0:
        roi = np_img
    pixels = roi.reshape(-1, 3)
    if pixels.size == 0:
        pixels = np_img.reshape(-1, 3)
    median_color = np.median(pixels, axis=0)
    color_name = _rgb_to_color_name(median_color)
    description = "classic sedan"
    hex_color = "#{:02x}{:02x}{:02x}".format(
        int(np.clip(median_color[0], 0, 255)),
        int(np.clip(median_color[1], 0, 255)),
        int(np.clip(median_color[2], 0, 255)),
    )
    return CarMeta(
        description=description,
        color_name=color_name,
        hex_color=hex_color,
        median_rgb=(float(median_color[0]), float(median_color[1]), float(median_color[2])),
    )


def build_nano_banana_prompt(wheel_caption: str | None = None) -> str:
    """Return catalog-style swap instructions for nano-banana-pro."""

    caption = wheel_caption or "the provided reference rims"
    return f"""
Generate a single realistic automotive catalog photo.

Use the **first image in `image_input`** as the base reference.
Recreate the **same car** from that image: same make and model, same body kit, same doors, windows, mirrors, trim pieces and badges, the same camera angle, perspective, framing, background and lighting.

The car **body color and paint finish must stay exactly the same** as in the first image: no recolor, no change in brightness, contrast or saturation, no changes to reflections on the paint.

The **only** change you are allowed to make is the wheels.
Replace the factory wheels on the car with the custom rims from the **second image in `image_input`** (wheel reference).
Copy the rim design **exactly**: same spoke count, spoke shape, spoke thickness, concavity, center cap style and overall material and color.
Match the color and finish precisely: {caption}.
Apply these new rims to **all visible wheels** on the car.
The tire sidewalls must look realistic, with normal thickness, no stretched or balloon tires.

**Do NOT**:
– do not change the car model, generation or body shape;
– do not change ride height or suspension geometry;
– do not change the car body color or paint finish;
– do not change or replace the background;
– do not add any extra cars, extra wheels, people or objects;
– do not create collages, split screens, before/after comparisons, zoom-in circles or close-up insets;
– do not place a separate giant wheel in the frame;
– do not crop to only a wheel – the full car should remain the main subject.

Output: a **single** clean catalog-style photo that looks identical to the original reference photo, except that the wheels have been swapped to match the reference rims perfectly.
""".strip()


def match_car_color_to_reference(image: Image.Image, car_meta: CarMeta, *, strength: float = 0.9) -> Image.Image:
    """Return a color-corrected copy of image biased toward the reference car color."""

    if not car_meta.median_rgb:
        return image

    arr = np.asarray(image).astype(np.float32)
    height, width = arr.shape[:2]
    top = int(height * 0.32)
    bottom = int(height * 0.82)
    left = int(width * 0.12)
    right = int(width * 0.88)
    patch = arr[top:bottom, left:right]
    if patch.size == 0:
        return image

    import cv2  # local import to avoid circular dependency

    patch_bgr = cv2.cvtColor(patch.astype(np.uint8), cv2.COLOR_RGB2BGR)
    patch_lab = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    current_mean = patch_lab.reshape(-1, 3).mean(axis=0)

    target_rgb = np.array(car_meta.median_rgb, dtype=np.float32)
    target_bgr = target_rgb[::-1]
    target_lab = cv2.cvtColor(target_bgr.reshape((1, 1, 3)).astype(np.uint8), cv2.COLOR_BGR2LAB)[0, 0].astype(
        np.float32
    )

    delta = (target_lab - current_mean) * strength
    patch_lab += delta
    patch_lab = np.clip(patch_lab, 0, 255)
    corrected_patch = cv2.cvtColor(patch_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
    arr[top:bottom, left:right] = corrected_patch.astype(np.float32)
    corrected = Image.fromarray(arr.astype(np.uint8))
    return corrected


def _rgb_to_color_name(mean_rgb: np.ndarray) -> str:
    distances = {
        name: np.linalg.norm(mean_rgb - reference) for name, reference in COLOR_REFERENCE_MAP.items()
    }
    closest = min(distances, key=distances.get)
    return closest
