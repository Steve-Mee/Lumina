"""Per-contract research specs. Same 0.25 tick; different tick value and commission ticks.

Research defaults, independent of live NinjaTrader config.yaml. Numbers match the
published CME tick size / tick value and a conservative all-in commission converted
to ticks (Free-plan order of magnitude: ES/NQ richer tick value, micros more
expensive in ticks).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class ContractError(ValueError):
    """Unknown or inconsistent contract spec."""


@dataclass(frozen=True, slots=True)
class ContractSpec:
    root: str
    tick_size: float
    tick_value_usd: float
    multiplier: float
    commission_ticks: float
    half_spread_ticks: float

    def __post_init__(self) -> None:
        if self.tick_size != 0.25:
            raise ContractError(f"{self.root}: ES/NQ/MES/MNQ tick size must be 0.25")
        if self.tick_value_usd <= 0.0 or self.multiplier <= 0.0:
            raise ContractError(f"{self.root}: tick value and multiplier must be positive")
        if abs(self.tick_value_usd - self.tick_size * self.multiplier) > 1e-9:
            raise ContractError(f"{self.root}: tick_value must equal tick_size * multiplier")
        if self.commission_ticks < 0.0 or self.half_spread_ticks < 0.0:
            raise ContractError(f"{self.root}: commission and half-spread cannot be negative")

    @property
    def commission_usd_per_side(self) -> float:
        return self.commission_ticks * self.tick_value_usd


# All-in Free-plan USD / tick_value → commission in ticks.
ES = ContractSpec(
    root="ES",
    tick_size=0.25,
    tick_value_usd=12.50,
    multiplier=50.0,
    commission_ticks=2.87 / 12.50,
    half_spread_ticks=0.5,
)
NQ = ContractSpec(
    root="NQ",
    tick_size=0.25,
    tick_value_usd=5.00,
    multiplier=20.0,
    commission_ticks=2.87 / 5.00,
    half_spread_ticks=0.5,
)
MES = ContractSpec(
    root="MES",
    tick_size=0.25,
    tick_value_usd=1.25,
    multiplier=5.0,
    commission_ticks=0.94 / 1.25,
    half_spread_ticks=0.5,
)
MNQ = ContractSpec(
    root="MNQ",
    tick_size=0.25,
    tick_value_usd=0.50,
    multiplier=2.0,
    commission_ticks=0.94 / 0.50,
    half_spread_ticks=0.5,
)

CONTRACTS: Mapping[str, ContractSpec] = {
    "ES": ES,
    "NQ": NQ,
    "MES": MES,
    "MNQ": MNQ,
}


def spec_for(root: str) -> ContractSpec:
    key = root.strip().upper()
    try:
        return CONTRACTS[key]
    except KeyError as exc:
        raise ContractError(f"unsupported contract {root!r}; expected ES/NQ/MES/MNQ") from exc
