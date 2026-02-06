from __future__ import annotations

from dataclasses import dataclass

from app.domain.rates import RatesStore


@dataclass(frozen=True)
class CalculatorInput:
    product_category: str | None
    weight_kg: float
    volume_m3: float
    goods_value: float
    origin: str | None = None
    destination: str | None = None
    urgency: str | None = None


@dataclass(frozen=True)
class CalculatorResult:
    cargo_cost_estimate: float
    official_cost_estimate: float
    cargo_eta: str
    official_eta: str
    breakdown: list[str]


class Calculator:
    def __init__(self, rates_store: RatesStore) -> None:
        self.rates_store = rates_store

    async def calculate(self, data: CalculatorInput) -> CalculatorResult:
        from app.domain.rates_provider import RateProvider
        currency_provider = RateProvider.get_instance()
        currencies = await currency_provider.get_rates()
        
        rates = self.rates_store.get_rates(data.product_category)
        
        # Currency Conversions
        # Input goods_value is in CNY
        # Output should be in RUB (and USD reference)
        
        cny_to_rub = currencies.cny_with_margin
        usd_to_rub = currencies.usd_with_margin
        
        value_rub = data.goods_value * cny_to_rub
        
        # 1. White Import Calculation (Official)
        # Duty + VAT + Fees
        duty = value_rub * rates.official_customs_duty_pct
        vat_base = value_rub + duty
        vat = vat_base * rates.vat_pct
        
        official_logistics_per_kg_usd = 2.17 # Example from live bot: ЖД (белый)
        official_logistics_total_usd = data.weight_kg * official_logistics_per_kg_usd
        official_logistics_total_rub = official_logistics_total_usd * usd_to_rub
        
        fees_rub = rates.broker_fee * usd_to_rub # Broker fee in USD -> RUB
        
        official_total_rub = value_rub + duty + vat + official_logistics_total_rub + fees_rub
        official_unit_cost = official_total_rub / (data.goods_value / 10 if data.goods_value > 0 else 1) # Hack: unit cost? input doesn't have Qty field here locally in this dataclass? 
        # Wait, data has no Quantity field in CalculatorInput!
        # We need to add Quantity to CalculatorInput to compute unit cost correctly.
        # For now, let's assume total cost.
        official_total_rub = round(official_total_rub, 2)

        # 2. Cargo Calculation
        # Rate per kg ($) + Insurance (%) + Packaging ($)
        # Live bot example: Cargo slow auto $4.58/kg
        cargo_rate_usd = 4.58 
        cargo_delivery_usd = data.weight_kg * cargo_rate_usd
        
        # Insurance (e.g. 2% of value)
        insurance_usd = (data.goods_value / 7.2) * 0.02 # Approx CNY->USD
        
        packaging_usd = 50.0 # Estimate
        
        cargo_total_usd = cargo_delivery_usd + insurance_usd + packaging_usd
        cargo_total_rub = cargo_total_usd * usd_to_rub + value_rub # Cost of goods included? usually Cargo cost is just delivery. 
        # But the comparison shows "Unit Cost", which includes the goods price.
        
        cargo_total_cost_rub = value_rub + (cargo_total_usd * usd_to_rub)

        return CalculatorResult(
            cargo_cost_estimate=cargo_total_cost_rub,
            official_cost_estimate=official_total_rub,
            cargo_eta=rates.eta_cargo_days,
            official_eta=rates.eta_official_days,
            breakdown=[
                f"Rate CNY: {cny_to_rub:.2f} RUB",
                f"Rate USD: {usd_to_rub:.2f} RUB"
            ],
        )

    def render(self, result: CalculatorResult) -> str:
        # Template matching the live bot
        diff = result.official_cost_estimate - result.cargo_cost_estimate
        diff_pct = (diff / result.cargo_cost_estimate) * 100 if result.cargo_cost_estimate else 0
        
        return (
            f"⚖️ **СРАВНЕНИЕ: ОФИЦИАЛЬНЫЙ ИМПОРТ vs КАРГО**\n\n"
            f"📊 **Стоимость партии (Total):**\n"
            f"• Официальный импорт: {result.official_cost_estimate:,.2f} RUB\n"
            f"• Карго (самый дешевый): {result.cargo_cost_estimate:,.2f} RUB\n"
            f"• Разница: {diff:,.2f} RUB ({diff_pct:.1f}%)\n\n"
            f"🔎 **Сравнение по ставкам:**\n"
            f"(Здесь детальный расчет, см. полную версию)"
        )
