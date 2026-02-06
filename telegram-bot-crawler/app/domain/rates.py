from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RatesConfig:
    cargo_rate_per_kg: float = 4.0
    cargo_rate_per_m3: float = 220.0
    official_customs_duty_pct: float = 0.1
    vat_pct: float = 0.2
    broker_fee: float = 60.0
    cargo_min_charge: float = 120.0
    official_min_charge: float = 80.0
    eta_cargo_days: str = "12-18"
    eta_official_days: str = "18-28"
    categories: dict[str, dict[str, float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RatesConfig":
        defaults = dict(data.get("defaults", data) or {})
        categories = dict(data.get("categories", {}) or {})
        return cls(
            cargo_rate_per_kg=float(defaults.get("cargo_rate_per_kg", cls.cargo_rate_per_kg)),
            cargo_rate_per_m3=float(defaults.get("cargo_rate_per_m3", cls.cargo_rate_per_m3)),
            official_customs_duty_pct=float(
                defaults.get("official_customs_duty_pct", cls.official_customs_duty_pct)
            ),
            vat_pct=float(defaults.get("vat_pct", cls.vat_pct)),
            broker_fee=float(defaults.get("broker_fee", cls.broker_fee)),
            cargo_min_charge=float(defaults.get("cargo_min_charge", cls.cargo_min_charge)),
            official_min_charge=float(
                defaults.get("official_min_charge", cls.official_min_charge)
            ),
            eta_cargo_days=str(defaults.get("eta_cargo_days", cls.eta_cargo_days)),
            eta_official_days=str(
                defaults.get("eta_official_days", cls.eta_official_days)
            ),
            categories={
                str(key): {str(k): float(v) for k, v in (val or {}).items()}
                for key, val in categories.items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "defaults": {
                "cargo_rate_per_kg": self.cargo_rate_per_kg,
                "cargo_rate_per_m3": self.cargo_rate_per_m3,
                "official_customs_duty_pct": self.official_customs_duty_pct,
                "vat_pct": self.vat_pct,
                "broker_fee": self.broker_fee,
                "cargo_min_charge": self.cargo_min_charge,
                "official_min_charge": self.official_min_charge,
                "eta_cargo_days": self.eta_cargo_days,
                "eta_official_days": self.eta_official_days,
            },
            "categories": self.categories,
        }


class RatesStore:
    def __init__(self, path: Path, rates: RatesConfig) -> None:
        self.path = path
        self.rates = rates

    @classmethod
    def load(cls, path: Path) -> "RatesStore":
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            data = yaml.safe_load(raw) or {}
        else:
            data = {}
        return cls(path=path, rates=RatesConfig.from_dict(data))

    def save(self) -> None:
        payload = self.rates.to_dict()
        self.path.write_text(
            yaml.safe_dump(payload, sort_keys=False),
            encoding="utf-8",
        )

    def get_rates(self, category: str | None) -> RatesConfig:
        if not category:
            return self.rates
        overrides = self.rates.categories.get(category, {})
        merged = dict(self.rates.to_dict()["defaults"])
        merged.update(overrides)
        return RatesConfig.from_dict({"defaults": merged, "categories": self.rates.categories})

    def update_rate(self, key: str, value: float, category: str | None = None) -> None:
        if category:
            bucket = self.rates.categories.setdefault(category, {})
            bucket[key] = value
        else:
            if not hasattr(self.rates, key):
                raise KeyError(f"Unknown rate key: {key}")
            setattr(self.rates, key, value)
        self.save()

    def render(self) -> str:
        lines = ["Current rates:", ""]
        defaults = self.rates.to_dict()["defaults"]
        for key, value in defaults.items():
            lines.append(f"- {key}: {value}")
        if self.rates.categories:
            lines.append("")
            lines.append("Category overrides:")
            for category, overrides in self.rates.categories.items():
                lines.append(f"- {category}:")
                for key, value in overrides.items():
                    lines.append(f"  - {key}: {value}")
        return "\n".join(lines)
