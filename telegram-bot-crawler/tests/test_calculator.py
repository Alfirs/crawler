from __future__ import annotations

from pathlib import Path

from app.domain.calculator import Calculator, CalculatorInput
from app.domain.rates import RatesConfig, RatesStore


def test_calculator_estimates() -> None:
    store = RatesStore(path=Path("rates.yaml"), rates=RatesConfig())
    calc = Calculator(store)
    data = CalculatorInput(
        product_category=None,
        weight_kg=10.0,
        volume_m3=0.5,
        goods_value=1000.0,
    )
    result = calc.calculate(data)
    assert result.cargo_cost_estimate >= 0
    assert result.official_cost_estimate >= 0
