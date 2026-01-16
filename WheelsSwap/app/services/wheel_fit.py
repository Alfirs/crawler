from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

from app.compositor import extract_wheel_rgba
from app.config import get_settings, resolve_media_path
from app.image_processing import (
    WheelDetection,
    build_nano_banana_prompt,
    detect_wheels,
    load_and_normalize_image,
    pil_to_bytes,
)
from app.kie_client import KieClient, KieClientError
from app.wheels import Wheel

logger = logging.getLogger(__name__)


class WheelFitService:
    """High-level service that calls nano-banana-pro edit API with fallback overlays."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.kie_client = KieClient(self.settings)

    async def close(self) -> None:
        await self.kie_client.close()

    async def fit_wheels(
        self,
        *,
        car_photo_bytes: bytes,
        wheel_photo_bytes: Optional[bytes],
        wheel_prompt: Optional[str],
        wheel_metadata: Optional[Wheel] = None,
    ) -> Path:
        return await self.render_catalog(
            car_photo_bytes=car_photo_bytes,
            wheel_photo_bytes=wheel_photo_bytes,
            wheel_prompt=wheel_prompt,
            wheel_metadata=wheel_metadata,
        )

    async def render_catalog(
        self,
        *,
        car_photo_bytes: bytes,
        wheel_photo_bytes: Optional[bytes],
        wheel_prompt: Optional[str],
        wheel_metadata: Optional[Wheel] = None,
    ) -> Path:
        if wheel_photo_bytes is None:
            raise RuntimeError("Wheel reference photo is required.")

        context = self._prepare_edit_context(
            car_photo_bytes=car_photo_bytes,
            wheel_photo_bytes=wheel_photo_bytes,
            prefix="catalog-",
        )

        if not wheel_metadata:
            wheel_metadata = Wheel(
                id="custom",
                name=wheel_prompt or "custom wheel",
                short_description=wheel_prompt or "custom wheel",
                style_prompt=wheel_prompt or "custom wheel",
            )
        wheel_caption = wheel_metadata.style_prompt or wheel_metadata.short_description or wheel_metadata.name
        prompt = build_nano_banana_prompt(wheel_caption)

        if self.settings.use_local_overlay_only:
            result_bytes = self._run_local_overlay(context)
            result_source = "overlay-debug"
        else:
            result_bytes, result_source = await self._run_seedream_with_fallback(context, prompt)

        context.result_path.write_bytes(result_bytes)
        logger.info("Wheel swap result saved at %s (source=%s)", context.result_path, result_source)
        return context.result_path

    async def _run_seedream_with_fallback(self, context: "_EditContext", prompt: str) -> tuple[bytes, str]:
        try:
            logger.info("Calling nano-banana: car=%s, ref=%s", context.car_path, context.wheel_reference_path)
            api_bytes = await self.kie_client.edit_image_with_seedream(
                base_image_path=context.car_path,
                wheel_reference_path=context.wheel_reference_path,
                prompt=prompt,
            )
        except KieClientError as exc:
            logger.exception("nano-banana-pro request failed: %s", exc)
            return self._run_local_overlay(context), "overlay-error"
        except Exception:
            logger.exception("Unexpected error from nano-banana-pro")
            return self._run_local_overlay(context), "overlay-error"

        if not self._is_valid_image_bytes(api_bytes):
            logger.warning("nano-banana returned invalid bytes, falling back to local overlay")
            return self._run_local_overlay(context), "overlay-invalid"

        return api_bytes, "nano-banana"

    def _is_valid_image_bytes(self, data: bytes) -> bool:
        if not data:
            return False
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            return True
        except Exception:
            return False

    def _run_local_overlay(self, context: "_EditContext") -> bytes:
        if not context.wheel_photo_bytes:
            raise RuntimeError("Wheel reference photo is required for wheel overlay.")

        base = context.car_image.convert("RGBA")
        wheel_rgba = extract_wheel_rgba(context.wheel_photo_bytes).convert("RGBA")
        radius_scale = self.settings.image_processing.overlay_radius_scale

        for detection in context.detections:
            target_radius = max(1.0, detection.radius * radius_scale)
            diameter = max(4, int(round(target_radius * 2)))
            resized = wheel_rgba.resize((diameter, diameter), Image.LANCZOS)
            x0 = int(round(detection.x - target_radius))
            y0 = int(round(detection.y - target_radius))
            tmp = Image.new("RGBA", base.size, (0, 0, 0, 0))
            tmp.paste(resized, (x0, y0), resized)
            base = Image.alpha_composite(base, tmp)

        return pil_to_bytes(base.convert("RGB"))

    def _prepare_edit_context(
        self,
        *,
        car_photo_bytes: bytes,
        wheel_photo_bytes: bytes,
        prefix: str,
    ) -> "_EditContext":
        car_image = load_and_normalize_image(
            car_photo_bytes, self.settings.image_processing.max_image_size
        )
        detections = detect_wheels(car_image, self.settings.image_processing)
        detections = _pick_two_wheels(detections, car_image.width)

        request_id = uuid.uuid4().hex
        car_path = resolve_media_path("originals", f"{prefix}{request_id}.png", create_parents=True)
        result_path = resolve_media_path("results", f"{prefix}{request_id}.png", create_parents=True)

        car_image.save(car_path)

        ref_name = f"{prefix}wheel-ref-{request_id}.png"
        wheel_reference_path = resolve_media_path("temp", ref_name, create_parents=True)
        Path(wheel_reference_path).write_bytes(wheel_photo_bytes)

        return _EditContext(
            car_image=car_image,
            detections=detections,
            car_path=car_path,
            wheel_reference_path=wheel_reference_path,
            wheel_photo_bytes=wheel_photo_bytes,
            result_path=result_path,
        )



def _pick_two_wheels(detections: list[WheelDetection], image_width: int) -> list[WheelDetection]:
    """Deduplicate detections and pick two well-separated wheels."""

    if not detections:
        raise RuntimeError(
            "?? ??????? ????? ???????? ????. ?????????? ?????? ????, ??? ????? ??? ?????? ????? ??????? ??????????."
        )

    horizontal_gap = max(10, int(image_width * 0.12))

    filtered: list[WheelDetection] = []
    for det in sorted(detections, key=lambda d: d.radius, reverse=True):
        too_close = any(abs(det.x - existing.x) < horizontal_gap for existing in filtered)
        if not too_close:
            filtered.append(det)

    if len(filtered) < 2:
        raise RuntimeError(
            "?? ??????? ????? ??? ??????. ?????????, ??? ?? ???? ?????? ????? ???????? ? ?????? ?????? ????? ???????."
        )

    best_pair: tuple[WheelDetection, WheelDetection] | None = None
    max_dx = -1
    for i in range(len(filtered)):
        for j in range(i + 1, len(filtered)):
            dx = abs(filtered[i].x - filtered[j].x)
            if dx > max_dx:
                max_dx = dx
                best_pair = (filtered[i], filtered[j])

    if not best_pair or max_dx < horizontal_gap:
        raise RuntimeError("??????? ???? ?????????? ? ???????. ?????????? ???? ? ??????? ????? ??????????.")

    left, right = sorted(best_pair, key=lambda d: d.x)
    return [left, right]



@dataclass
class _EditContext:
    car_image: Image.Image
    detections: list[WheelDetection]
    car_path: Path
    wheel_reference_path: Path
    wheel_photo_bytes: bytes
    result_path: Path
