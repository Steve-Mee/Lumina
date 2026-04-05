from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TapeReadingAgent:
    """Scores real-time tape momentum from rolling delta and bid/ask imbalance."""

    volume_multiplier_threshold: float = 2.0
    imbalance_threshold: float = 1.5

    def score_momentum(self, tape: dict[str, float]) -> dict[str, Any]:
        volume_delta = float(tape.get("volume_delta", 0.0))
        avg_volume_delta = max(1e-6, float(tape.get("avg_volume_delta_10", 0.0)))
        imbalance = float(tape.get("bid_ask_imbalance", 1.0))
        cumulative_delta = float(tape.get("cumulative_delta_10", 0.0))

        vol_spike = volume_delta > (avg_volume_delta * self.volume_multiplier_threshold)
        imbalanced = imbalance > self.imbalance_threshold

        direction = "NEUTRAL"
        if cumulative_delta > 0:
            direction = "BUY"
        elif cumulative_delta < 0:
            direction = "SELL"

        confidence = 0.0
        if vol_spike:
            confidence += 0.5
        if imbalanced:
            confidence += 0.5
        if direction == "NEUTRAL":
            confidence *= 0.5

        fast_path_trigger = bool(vol_spike and imbalanced and direction != "NEUTRAL")

        return {
            "signal": direction if fast_path_trigger else "HOLD",
            "direction": direction,
            "confidence": round(confidence, 3),
            "fast_path_trigger": fast_path_trigger,
            "volume_delta": volume_delta,
            "avg_volume_delta_10": avg_volume_delta,
            "bid_ask_imbalance": imbalance,
            "cumulative_delta_10": cumulative_delta,
            "reason": (
                f"vol_delta={volume_delta:.0f} vs avg={avg_volume_delta:.0f}, "
                f"imbalance={imbalance:.2f}, cum_delta_10={cumulative_delta:.0f}"
            ),
        }
