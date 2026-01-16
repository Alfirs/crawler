import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = BASE_DIR / "templates"


def load_template(name: str) -> dict:
    """Load a carousel template by name from the templates directory."""
    template_path = TEMPLATE_DIR / f"{name}.json"
    if not template_path.exists():
        raise FileNotFoundError(f"Template '{name}' not found")

    with template_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
