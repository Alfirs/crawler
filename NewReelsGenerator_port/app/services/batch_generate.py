from pathlib import Path
from typing import List

from .template_loader import load_template
from .text_gen import generate_carousel_text
from .image_gen import generate_image

# render_reels is assumed to exist under app.carousel.core
# If located elsewhere, adjust the import accordingly.
from app.carousel.core import render_carousel


def _build_slides_from_template(template: dict, topic: str) -> List[dict]:
    slides_cfg = template.get("slides", [])
    slides = []
    cover_path: Path | None = None

    for cfg in slides_cfg:
        bg_type = cfg.get("bg")
        role = cfg.get("role")
        slide_entry = {"type": role or "text"}

        if bg_type == "generate":
            # Use new signature: img_prompt, style_image_path (optional), out_path
            generated_path = generate_image(
                img_prompt=topic,
                out_path=Path("output") / "latest_tmp.png"
            )
            cover_path = generated_path
            slide_entry["bg"] = {"mode": "photo", "path": str(generated_path)} if generated_path else None
        elif bg_type == "reuse_cover":
            if cover_path:
                slide_entry["bg"] = {"mode": "photo", "path": str(cover_path)}
            else:
                slide_entry["bg"] = None
        elif isinstance(bg_type, str) and bg_type.startswith("photo:"):
            photo_path = bg_type.split("photo:", 1)[1]
            slide_entry["bg"] = {"mode": "photo", "path": photo_path}
        else:
            slide_entry["bg"] = None

        slides.append(slide_entry)

    return slides


def batch_generate(template_name: str, topic: str, count: int = 5) -> List[str]:
    template = load_template(template_name)
    outputs: List[str] = []

    for _ in range(count):
        text_data = generate_carousel_text(topic)
        slides = _build_slides_from_template(template, topic)

        job = {
            "username": template.get("watermark", "@username"),
            "slides": slides,
        }

        output_dir = Path("output") / Path(template_name)
        output_dir.mkdir(parents=True, exist_ok=True)

        result_path = render_carousel(job, output_dir, seed=None, username_override=None)
        outputs.append(str(result_path))

    return outputs
