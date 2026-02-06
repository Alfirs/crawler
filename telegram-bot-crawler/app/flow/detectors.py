from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from app.flow.loader import RawLogEntry
from app.flow.signatures import normalize_text


class InputType(str, Enum):
    NUMBER = "number"
    WEIGHT_KG = "weight_kg"
    VOLUME_M3 = "volume_m3"
    LENGTH_CM = "length_cm"
    WIDTH_CM = "width_cm"
    HEIGHT_CM = "height_cm"
    QUANTITY = "quantity"
    PRICE_VALUE = "price_value"
    CITY = "city"
    NAME = "name"
    TEXT = "text"

@dataclass
class LogHints:
    prompt_samples: dict[str, list[str]] = field(default_factory=dict)
    button_mode: dict[str, str] = field(default_factory=dict)


def build_log_hints(entries: Iterable[RawLogEntry]) -> LogHints:
    hints = LogHints()
    last_prompt: str | None = None
    last_has_buttons = False

    for entry in entries:
        if entry.event_type in {"message_received", "message_edited"}:
            last_prompt = entry.data.get("text")
            last_has_buttons = bool(entry.data.get("has_buttons"))
            continue

        if entry.event_type == "button_clicked" and last_prompt:
            key = normalize_text(last_prompt)
            hints.button_mode[key] = "inline"
            continue

        if entry.event_type == "text_sent" and last_prompt:
            text = str(entry.data.get("text", ""))
            if not text.strip():
                continue
            key = normalize_text(last_prompt)
            hints.prompt_samples.setdefault(key, []).append(text)
            if last_has_buttons:
                hints.button_mode[key] = "reply"

    return hints

class InputDetector:
    def __init__(self, hints: LogHints) -> None:
        self.hints = hints

    def detect_input_type(self, prompt: str) -> InputType:
        text = prompt.lower()
        # Order matters! Specific dimensions first
        if _contains_any(text, _LENGTH_HINTS):
            return InputType.LENGTH_CM
        if _contains_any(text, _WIDTH_HINTS):
            return InputType.WIDTH_CM
        if _contains_any(text, _HEIGHT_HINTS):
            return InputType.HEIGHT_CM
        if _contains_any(text, _QUANTITY_HINTS):
            return InputType.QUANTITY
        if _contains_any(text, _WEIGHT_HINTS):
            return InputType.WEIGHT_KG
        if _contains_any(text, _VOLUME_HINTS):
            return InputType.VOLUME_M3
        if _contains_any(text, _PRICE_HINTS):
            return InputType.PRICE_VALUE
        if _contains_any(text, _CITY_HINTS):
            return InputType.CITY
        if _contains_any(text, _NAME_HINTS):
            return InputType.NAME
        if _contains_any(text, _NUMBER_HINTS) or (text.isdigit() and len(text) in [4, 6, 8, 10]):
            return InputType.NUMBER
        return InputType.TEXT
    
    def format_hint(self, input_type: InputType) -> str:
        return _HINTS.get(input_type, "Please enter a response.")

    def samples_for_prompt(self, prompt: str) -> list[str]:
        return list(self.hints.prompt_samples.get(normalize_text(prompt), []))

    def keyboard_hint(self, prompt: str) -> str | None:
        return self.hints.button_mode.get(normalize_text(prompt))

    def should_calculate(self, prompt: str, data: dict[str, object]) -> bool:
        text = prompt.lower()
        if _contains_any(text, _CALCULATOR_HINTS):
            return True
        # If we have Dimensions + Weight + Price, we can calculate
        # Or if we have Volume + Weight + Price
        has_dims = all(k in data for k in ["length_cm", "width_cm", "height_cm"])
        has_w_p = all(k in data for k in ["weight_kg", "goods_value"])
        if has_dims and has_w_p:
            return True
            
        keys = {"weight_kg", "volume_m3", "goods_value"}
        return any(key in data for key in keys)

def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)

# Tokens
_LENGTH_HINTS = ["\u0434\u043b\u0438\u043d", "length"] # длина
_WIDTH_HINTS = ["\u0448\u0438\u0440\u0438\u043d", "width"] # ширина
_HEIGHT_HINTS = ["\u0432\u044b\u0441\u043e\u0442", "height"] # высота
_QUANTITY_HINTS = ["\u043a\u043e\u043b\u0438\u0447", "\u0448\u0442", "quantity", "pcs"] # количество, штук

_WEIGHT_HINTS = [
    "kg",
    "\u043a\u0433",
    "\u0432\u0435\u0441",
    "\u043a\u0438\u043b\u043e\u0433\u0440\u0430\u043c",
]

_VOLUME_HINTS = [
    "m3",
    "\u043c3",
    "\u043a\u0443\u0431",
    "\u043e\u0431\u044a\u0435\u043c",
]

_PRICE_HINTS = [
    "\u0441\u0442\u043e\u0438\u043c",
    "\u0446\u0435\u043d",
    "value",
    "usd",
    "eur",
    "\u0440\u0443\u0431",
]

_CITY_HINTS = [
    "\u0433\u043e\u0440\u043e\u0434",
    "city",
    "\u043e\u0442\u043a\u0443\u0434\u0430",
    "\u043a\u0443\u0434\u0430",
    "\u043f\u0443\u043d\u043a\u0442",
]

_NAME_HINTS = [
    "\u0438\u043c\u044f",
    "name",
    "\u0444\u0438\u043e",
]

_NUMBER_HINTS = [
    "\u043a\u043e\u0434",
    "\u0442\u043d \u0432\u044d\u0434",
    "hs",
]

_CALCULATOR_HINTS = [
    "\u0440\u0430\u0441\u0447\u0435\u0442",
    "\u043a\u0430\u043b\u044c\u043a\u0443\u043b\u044f\u0442\u043e\u0440",
    "cost",
    "price",
]

_HINTS = {
    InputType.WEIGHT_KG: "Enter weight in kg, e.g. 12.5",
    InputType.VOLUME_M3: "Enter volume in m3, e.g. 0.3",
    InputType.LENGTH_CM: "Enter length in cm",
    InputType.WIDTH_CM: "Enter width in cm",
    InputType.HEIGHT_CM: "Enter height in cm",
    InputType.QUANTITY: "Enter quantity",
    InputType.PRICE_VALUE: "Enter goods value, e.g. 1500",
    InputType.CITY: "Enter a city name",
    InputType.NAME: "Enter a name",
    InputType.NUMBER: "Enter a number",
    InputType.TEXT: "Please enter a response.",
}
