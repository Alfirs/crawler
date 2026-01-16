import os
from typing import Dict

THEMES: Dict[str, Dict[str, str]] = {
    "midnight": {
        "name": "Midnight",
        "background": "#0f1117",
        "text": "#f4f4f4",
        "accent": "#9db5ff",
        "subtitle": "#d9d9d9",
        "footer": "#97a2c7",
        "badge": "#9db5ff",
        "shadow": "0 40px 80px rgba(0,0,0,0.45)",
    },
    "sunrise": {
        "name": "Sunrise",
        "background": "#fff8ef",
        "text": "#2c2c2c",
        "accent": "#ff6f3c",
        "subtitle": "#555555",
        "footer": "#a56b2e",
        "badge": "#ff6f3c",
        "shadow": "0 40px 80px rgba(255,110,60,0.25)",
    },
    "forest": {
        "name": "Forest",
        "background": "#0f1f1a",
        "text": "#f0f7f2",
        "accent": "#4fe3a5",
        "subtitle": "#cde7d6",
        "footer": "#7fba98",
        "badge": "#4fe3a5",
        "shadow": "0 40px 80px rgba(23,62,44,0.5)",
    },
}

DEFAULT_THEME = os.getenv("DEFAULT_THEME", "midnight").lower()


def normalize_theme_id(theme_id: str | None) -> str:
    key = (theme_id or DEFAULT_THEME).lower()
    if key not in THEMES:
        return DEFAULT_THEME
    return key


def resolve_theme(theme_id: str | None) -> Dict[str, str]:
    return THEMES[normalize_theme_id(theme_id)]
