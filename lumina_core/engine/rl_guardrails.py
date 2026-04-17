from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RLGuardrailLayer:
    max_divergence_streak: int = 3
    max_action_delta: float = 1.0
    min_qty_pct: float = 0.1
    max_qty_pct_default: float = 1.5
    min_stop_mult: float = 0.5
    max_stop_mult: float = 1.8

    def _regime_caps(self, regime: str) -> tuple[float, float]:
        label = str(regime or "NEUTRAL").upper()
        if "VOL" in label or "HIGH" in label:
            return 1.0, 1.35
        if "TREND" in label:
            return 1.2, 1.6
        return self.max_qty_pct_default, self.max_stop_mult

    def apply(
        self,
        *,
        rl_action: dict[str, Any],
        baseline_signal: str,
        regime: str,
        shadow_state: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        safe = dict(rl_action or {})
        shadow = dict(shadow_state or {})

        raw_signal = int(safe.get("signal", 0) or 0)
        signal_map = {0: "HOLD", 1: "BUY", 2: "SELL"}
        rl_signal = signal_map.get(raw_signal, "HOLD")
        baseline = str(baseline_signal or "HOLD").upper()

        qty_cap, stop_cap = self._regime_caps(regime)
        qty_pct = float(safe.get("qty_pct", 1.0) or 1.0)
        stop_mult = float(safe.get("stop_mult", 1.0) or 1.0)
        safe["qty_pct"] = max(self.min_qty_pct, min(qty_cap, qty_pct))
        safe["stop_mult"] = max(self.min_stop_mult, min(stop_cap, stop_mult))

        divergence = bool(
            rl_signal in {"BUY", "SELL"} and baseline in {"BUY", "SELL", "HOLD"} and rl_signal != baseline
        )
        streak = int(shadow.get("divergence_streak", 0) or 0)
        streak = streak + 1 if divergence else 0
        shadow["divergence_streak"] = streak

        kill_triggered = streak >= self.max_divergence_streak
        if kill_triggered:
            safe["signal"] = 0

        metadata = {
            "baseline_signal": baseline,
            "rl_signal": rl_signal,
            "divergence": divergence,
            "divergence_streak": streak,
            "kill_triggered": kill_triggered,
            "bounded_qty_pct": float(safe["qty_pct"]),
            "bounded_stop_mult": float(safe["stop_mult"]),
            "regime": str(regime or "NEUTRAL"),
        }
        shadow["last_meta"] = metadata
        return safe, shadow
