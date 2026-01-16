"""
Template loading service for carousel constructor.

Reads JSON templates from ``app/config/templates`` and exposes helpers
for FastAPI handlers/render pipeline. Provides validation and fallbacks.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "config" / "templates"


class TemplateValidationError(Exception):
    """Raised when template structure is invalid."""


def _ensure_templates_dir() -> None:
    """
    Create templates directory if it is missing.
    Allows shipping empty dir; prevents runtime errors when saving custom templates later.
    """
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def _validate_block(block: Dict[str, Any]) -> None:
    """
    Validate a single block definition.
    Accepts both text and image blocks; raises TemplateValidationError on inconsistencies.
    """
    required_box_keys = {"x0", "y0", "x1", "y1"}

    if not isinstance(block, dict):
        raise TemplateValidationError("Block must be a dictionary")

    block_type = block.get("type", "text")
    if block_type not in {"text", "image"}:
        raise TemplateValidationError(f"Unsupported block type '{block_type}'")

    box = block.get("box")
    if not isinstance(box, dict) or not required_box_keys.issubset(box):
        raise TemplateValidationError(f"Block '{block_type}' missing box definition")

    if block_type == "text":
        if "text" not in block:
            raise TemplateValidationError("Text block requires 'text' value")
    elif block_type == "image":
        # image blocks may rely on dynamic sources; enforce optional keys if provided
        if "source" in block and not isinstance(block["source"], str):
            raise TemplateValidationError("Image block 'source' must be string when provided")

    style = block.get("style", {})
    if style and not isinstance(style, dict):
        raise TemplateValidationError("Block 'style' must be an object when provided")


def _validate_template(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalise template payload.
    Returns sanitized copy to be used in rendering.
    """
    if not isinstance(data, dict):
        raise TemplateValidationError("Template payload must be an object")

    slides = data.get("slides")
    if not isinstance(slides, list) or not slides:
        raise TemplateValidationError("Template must define non-empty 'slides' array")

    sanitized_slides: List[Dict[str, Any]] = []

    for idx, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise TemplateValidationError(f"Slide #{idx} must be an object")

        slide_type = slide.get("type", "content")
        blocks = slide.get("blocks", [])
        if not isinstance(blocks, list) or not blocks:
            raise TemplateValidationError(f"Slide #{idx} must contain blocks array")

        for block in blocks:
            _validate_block(block)

        sanitized_slides.append(
            {
                "type": slide_type,
                "blocks": blocks,
            }
        )

    return {
        "name": data.get("name", "custom-template"),
        "slides": sanitized_slides,
    }


@lru_cache(maxsize=32)
def list_templates() -> Dict[str, Dict[str, Any]]:
    """
    Load templates from disk and cache them.
    Template id is filename without extension.
    """
    _ensure_templates_dir()
    templates: Dict[str, Dict[str, Any]] = {}

    for file in TEMPLATES_DIR.glob("*.json"):
        try:
            with file.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            templates[file.stem] = _validate_template(payload)
        except Exception as exc:
            # Skip invalid templates but keep loggable info.
            # In production one may plug actual logger; use print for debugging.
            print(f"[templates] warning: unable to load template '{file.name}': {exc}")

    return templates


def invalidate_cache() -> None:
    """Reset cached template mapping (useful for tests or admin updates)."""
    list_templates.cache_clear()  # type: ignore[attr-defined]


def load_template(template_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch template by id.
    Returns None if not found or invalid.
    """
    if not template_id:
        return None
    return list_templates().get(template_id)


def parse_template_payload(payload: Any) -> Optional[Dict[str, Any]]:
    """
    Accept template payload as dict or JSON string.
    Returns validated structure or None on failure.
    """
    if payload is None:
        return None

    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8")
        except Exception:
            raise TemplateValidationError("Invalid bytes payload for template")

    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return None
        payload = json.loads(payload)

    if isinstance(payload, dict):
        return _validate_template(payload)

    raise TemplateValidationError("Unsupported template payload format")


def get_default_template() -> Dict[str, Any]:
    """
    Build default template resembling legacy behaviour.
    Used as fallback when explicit templates fail.
    """
    return {
        "name": "legacy-default",
        "slides": [
            {
                "type": "cover",
                "blocks": [],
            },
            {
                "type": "content",
                "blocks": [],
            },
        ],
    }
