"""Types and seed helpers for multi-day SIM evaluation."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


def stable_seed(*parts: str) -> int:
    payload = "|".join(parts)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)


# Back-compat alias used by runner modules
_stable_seed = stable_seed


@dataclass(slots=True)
class ShadowFill:
    day_index: int
    side: str
    qty: int
    entry_price: float
    exit_price: float
    pnl: float
    reason: str


@dataclass(slots=True)
class SimResult:
    dna_hash: str
    day_count: int
    avg_pnl: float
    max_drawdown_ratio: float
    regime_fit_bonus: float
    fitness: float
    shadow_mode: bool = False
    hypothetical_fills: list[ShadowFill] | None = None


__all__ = ["ShadowFill", "SimResult", "stable_seed", "_stable_seed"]
