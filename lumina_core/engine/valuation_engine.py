from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ContractSpec:
    root: str
    point_value: float
    tick_size: float


@dataclass(slots=True)
class ValuationEngine:
    """Single source of truth for valuation and fill economics."""

    contract_specs: dict[str, ContractSpec] = field(
        default_factory=lambda: {
            "MES": ContractSpec(root="MES", point_value=5.0, tick_size=0.25),
            "MNQ": ContractSpec(root="MNQ", point_value=2.0, tick_size=0.25),
            "MYM": ContractSpec(root="MYM", point_value=0.5, tick_size=1.0),
            "ES": ContractSpec(root="ES", point_value=50.0, tick_size=0.25),
            "NQ": ContractSpec(root="NQ", point_value=20.0, tick_size=0.25),
            "YM": ContractSpec(root="YM", point_value=5.0, tick_size=1.0),
        }
    )
    commission_per_side_points: float = 0.25
    slippage_base_ticks: float = 0.25
    regime_slippage_multiplier: Mapping[str, float] = field(
        default_factory=lambda: {
            "TRENDING": 1.0,
            "BREAKOUT": 1.3,
            "VOLATILE": 1.8,
            "RANGING": 0.7,
            "LOW_VOL": 0.85,
            "NEUTRAL": 1.0,
        }
    )

    def _root_from_symbol(self, symbol: str) -> str:
        text = str(symbol or "").strip().upper()
        return text.split(" ")[0] if text else "MES"

    def _spec(self, symbol: str) -> ContractSpec:
        root = self._root_from_symbol(symbol)
        return self.contract_specs.get(root, self.contract_specs["MES"])

    def point_value(self, symbol: str) -> float:
        return float(self._spec(symbol).point_value)

    def tick_size(self, symbol: str) -> float:
        return float(self._spec(symbol).tick_size)

    def commission_dollars(self, *, symbol: str, quantity: int, sides: int = 1) -> float:
        qty = max(0, int(quantity))
        side_count = max(1, int(sides))
        point_value = self.point_value(symbol)
        return float(qty * side_count * self.commission_per_side_points * point_value)

    def slippage_ticks(
        self,
        *,
        volume: float,
        avg_volume: float,
        regime: str,
        slippage_scale: float = 1.0,
    ) -> float:
        ratio = float(volume) / max(float(avg_volume), 1e-6)
        base = self.slippage_base_ticks + min(0.25, max(0.0, (2.0 - min(2.0, ratio)) * 0.125))
        regime_key = self.normalize_regime(regime)
        regime_mult = float(self.regime_slippage_multiplier.get(regime_key, 1.0))
        return float(base * regime_mult * max(0.5, float(slippage_scale)))

    def slippage_price(self, *, symbol: str, slippage_ticks: float, side: int) -> float:
        return float(slippage_ticks * self.tick_size(symbol) * int(side))

    def apply_entry_fill(self, *, symbol: str, price: float, side: int, slippage_ticks: float) -> float:
        return float(price + self.slippage_price(symbol=symbol, slippage_ticks=slippage_ticks, side=side))

    def apply_exit_fill(self, *, symbol: str, price: float, side: int, slippage_ticks: float) -> float:
        return float(price - self.slippage_price(symbol=symbol, slippage_ticks=slippage_ticks, side=side))

    def should_fill_order(
        self,
        *,
        rng: random.Random,
        volume: float,
        avg_volume: float,
        pending_age: int,
        regime: str,
    ) -> bool:
        ratio = float(volume) / max(float(avg_volume), 1e-6)
        base_prob = 0.35 + min(0.45, ratio * 0.2)
        age_boost = min(0.2, int(pending_age) * 0.07)
        regime_key = self.normalize_regime(regime)
        regime_adj = 0.03 if regime_key in {"TRENDING", "BREAKOUT"} else -0.02 if regime_key == "VOLATILE" else 0.0
        probability = min(0.95, max(0.05, base_prob + age_boost + regime_adj))
        return bool(rng.random() < probability)

    def estimate_fill_latency_ms(
        self,
        *,
        volume: float,
        avg_volume: float,
        pending_age: int,
        regime: str,
    ) -> float:
        ratio = float(volume) / max(float(avg_volume), 1e-6)
        base_ms = 250.0 + max(0.0, (1.2 - min(1.2, ratio)) * 500.0)
        regime_key = self.normalize_regime(regime)
        regime_ms = 120.0 if regime_key == "VOLATILE" else -40.0 if regime_key in {"TRENDING", "BREAKOUT"} else 0.0
        age_ms = max(0, int(pending_age)) * 80.0
        return float(max(20.0, base_ms + regime_ms + age_ms))

    def pnl_dollars(self, *, symbol: str, entry_price: float, exit_price: float, side: int, quantity: int) -> float:
        qty = max(0, int(quantity))
        pv = self.point_value(symbol)
        return float((float(exit_price) - float(entry_price)) * int(side) * qty * pv)

    @staticmethod
    def normalize_regime(raw: str) -> str:
        text = str(raw or "").upper()
        if any(x in text for x in ("TREND", "BREAKOUT", "MOMENTUM")):
            return "TRENDING"
        if any(x in text for x in ("RANGE", "SIDEWAYS", "MEAN")):
            return "RANGING"
        if any(x in text for x in ("VOLATILE", "CHAOS", "HIGH_VOL")):
            return "VOLATILE"
        if any(x in text for x in ("LOW_VOL", "CALM")):
            return "LOW_VOL"
        return "NEUTRAL"
