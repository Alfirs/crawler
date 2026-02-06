from __future__ import annotations

from dataclasses import dataclass
import re

from app.flow.detectors import InputType

_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    value: float | str | None
    normalized: str
    hint: str | None = None


def _parse_number(text: str) -> float | None:
    match = _NUMBER_RE.search(text.replace(" ", ""))
    if not match:
        return None
    raw = match.group(0).replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def validate_input(input_type: InputType, text: str) -> ValidationResult:
    normalized = text.strip()
    if not normalized:
        return ValidationResult(False, None, normalized, "Input is empty.")

    if input_type in {
        InputType.WEIGHT_KG,
        InputType.VOLUME_M3,
        InputType.PRICE_VALUE,
        InputType.NUMBER,
    }:
        number = _parse_number(normalized)
        if number is None:
            return ValidationResult(False, None, normalized, "Enter a number.")
        if number <= 0 and input_type != InputType.NUMBER:
            return ValidationResult(False, None, normalized, "Value must be positive.")
        return ValidationResult(True, number, normalized)

    return ValidationResult(True, normalized, normalized)
