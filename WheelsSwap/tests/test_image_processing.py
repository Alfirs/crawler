from __future__ import annotations

from PIL import Image

from app.image_processing import WheelDetection, build_prompt, generate_wheel_mask
from app.wheels import Wheel


def test_generate_wheel_mask_draws_white_pixels() -> None:
    detections = [WheelDetection(x=50, y=50, radius=20)]
    mask = generate_wheel_mask((100, 100), detections, padding_ratio=0.1)
    pixels = list(mask.getdata())
    assert any(value > 0 for value in pixels), "Mask should contain non-zero pixels for detected wheels"


def test_build_prompt_includes_description() -> None:
    wheel = Wheel(id="test", name="Test Wheel", short_description="gloss black five spoke wheels")
    prompt = build_prompt(wheel)
    assert "gloss black five spoke wheels" in prompt
