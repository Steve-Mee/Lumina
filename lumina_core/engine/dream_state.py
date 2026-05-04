from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any

from .trade_signal_normalize import canonicalize_trade_signal


DEFAULT_DREAM: dict[str, Any] = {
    "signal": "HOLD",
    "confidence": 0.0,
    "stop": 0.0,
    "target": 0.0,
    "reason": "Initial",
    "why_no_trade": "",
    "confluence_score": 0.0,
    "fib_levels": {},
    "swing_high": 0.0,
    "swing_low": 0.0,
    "a_been_direction": "NEUTRAL",
    "chosen_strategy": "None",
    "emotional_bias": {
        "fomo_score": 0.0,
        "tilt_score": 0.0,
        "boredom_score": 0.0,
        "revenge_risk": 0.0,
    },
    "counterfactual_human_decision": "HOLD",
    "min_confluence_override": 0.0,
    "position_size_multiplier": 1.0,
    "stop_widen_multiplier": 1.0,
    "hold_until_ts": 0.0,
}


@dataclass(slots=True)
class DreamState:
    """Thread-safe holder for the current AI dream state."""

    data: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_DREAM))
    lock: threading.RLock = field(default_factory=threading.RLock)

    def __post_init__(self) -> None:
        if not isinstance(self.data, dict):
            raise TypeError("DreamState.data must be a dictionary")

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.data)

    def update(self, updates: dict[str, Any]) -> None:
        with self.lock:
            if "signal" in updates:
                updates = dict(updates)
                updates["signal"] = canonicalize_trade_signal(updates.get("signal"))
            self.data.update(updates)

    def set_value(self, key: str, value: Any) -> None:
        with self.lock:
            if key == "signal":
                value = canonicalize_trade_signal(value)
            self.data[key] = value

    def apply_emotional_correction(
        self,
        emotional_bias: dict[str, float],
        *,
        base_min_confluence: float,
        now_ts: float | None = None,
    ) -> dict[str, Any]:
        """Apply deliberate anti-bias corrections onto the active dream state."""
        ts_now = float(now_ts if now_ts is not None else time.time())

        fomo = float(emotional_bias.get("fomo_score", 0.0))
        tilt = float(emotional_bias.get("tilt_score", 0.0))
        boredom = float(emotional_bias.get("boredom_score", 0.0))
        revenge = float(emotional_bias.get("revenge_risk", 0.0))

        with self.lock:
            self.data["emotional_bias"] = {
                "fomo_score": round(max(0.0, min(1.0, fomo)), 3),
                "tilt_score": round(max(0.0, min(1.0, tilt)), 3),
                "boredom_score": round(max(0.0, min(1.0, boredom)), 3),
                "revenge_risk": round(max(0.0, min(1.0, revenge)), 3),
            }

            min_conf_override = float(base_min_confluence)
            position_size_multiplier = 1.0
            stop_widen_multiplier = 1.0
            hold_until_ts = float(self.data.get("hold_until_ts", 0.0) or 0.0)

            # If fomo is elevated, require more evidence before allowing execution.
            if fomo > 0.7:
                min_conf_override = max(min_conf_override, float(base_min_confluence) + 0.08)

            # If tilt is elevated, de-risk by halving size and widening stop.
            if tilt > 0.6:
                position_size_multiplier = 0.5
                stop_widen_multiplier = 1.25

            # If boredom dominates, enforce HOLD cooldown for at least 15 minutes.
            if boredom > 0.8:
                hold_until_ts = max(hold_until_ts, ts_now + 15 * 60)
                self.data["signal"] = "HOLD"
                self.data["reason"] = str(self.data.get("reason", "")) + " | Emotional cooldown (boredom)"

            self.data["min_confluence_override"] = round(float(min_conf_override), 4)
            self.data["position_size_multiplier"] = float(position_size_multiplier)
            self.data["stop_widen_multiplier"] = float(stop_widen_multiplier)
            self.data["hold_until_ts"] = float(hold_until_ts)

            return {
                "min_confluence_override": self.data["min_confluence_override"],
                "position_size_multiplier": self.data["position_size_multiplier"],
                "stop_widen_multiplier": self.data["stop_widen_multiplier"],
                "hold_until_ts": self.data["hold_until_ts"],
            }
