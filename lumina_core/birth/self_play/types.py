"""Self-play lab types (ADR-0037 Phase 0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SelfPlayLabConfig:
    """Lab config — default OFF; SIM/Birth/lab only."""

    enabled: bool = False
    max_variants: int = 8
    min_window_trades: int = 1
    meaningful_lift_delta: float = 0.01
    capital_mode_hint: str = "sim"
    # Phase 0: never apply; report only
    allow_apply: bool = False


@dataclass(frozen=True)
class SelfPlayVariantResult:
    """One variant's frozen-window evaluation (same physics as swarm tournament)."""

    variant_id: str
    trades: int
    wins: int
    total_pnl: float
    label: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "trades": int(self.trades),
            "wins": int(self.wins),
            "total_pnl": float(self.total_pnl),
            "label": self.label,
            "meta": dict(self.meta or {}),
        }
