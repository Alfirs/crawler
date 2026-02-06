from __future__ import annotations

from app.domain.validation import validate_input
from app.flow.detectors import InputType


def test_validate_weight() -> None:
    result = validate_input(InputType.WEIGHT_KG, "12,5 \u043a\u0433")
    assert result.ok
    assert result.value == 12.5


def test_validate_volume() -> None:
    result = validate_input(InputType.VOLUME_M3, "0.3m3")
    assert result.ok
    assert result.value == 0.3


def test_validate_price() -> None:
    result = validate_input(InputType.PRICE_VALUE, "1000$")
    assert result.ok
    assert result.value == 1000.0
