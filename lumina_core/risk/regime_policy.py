"""RegimePolicyMixin (M5 extract)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from lumina_core.risk.regime_types import AdaptiveRegimePolicy, RegimeSnapshot


class RegimePolicyMixin:
    def _policy_for(self, label: str) -> AdaptiveRegimePolicy:
        route = tuple(self.route_map.get(label, self.route_map["NEUTRAL"]))
        high_risk = label in self.high_risk_regimes
        return AdaptiveRegimePolicy(
            fast_path_weight=float(self.fast_path_weight_map.get(label, self.fast_path_weight_map["NEUTRAL"])),
            agent_route=route,
            risk_multiplier=float(self.risk_multiplier_map.get(label, self.risk_multiplier_map["NEUTRAL"])),
            emotional_twin_sensitivity=float(
                self.emotional_sensitivity_map.get(label, self.emotional_sensitivity_map["NEUTRAL"])
            ),
            cooldown_minutes=int(self.cooldown_minutes_map.get(label, self.cooldown_minutes_map["NEUTRAL"])),
            high_risk=high_risk,
            nightly_evolution_focus=label.lower(),
        )

    def _confidence_for(self, label: str, features: dict[str, float]) -> float:
        if label == "TRENDING":
            score = (features["adx"] / 40.0 + features["price_efficiency"] + features["slope_strength"]) / 3.0
        elif label == "RANGING":
            score = ((1.0 - min(1.0, features["adx"] / 30.0)) + (1.0 - features["price_efficiency"])) / 2.0
        elif label == "HIGH_VOLATILITY":
            score = min(1.0, max(features["atr_ratio"], features["realized_vol_ratio"]) / 2.2)
        elif label == "NEWS_DRIVEN":
            score = min(
                1.0, (features["volume_ratio"] / 3.0 + features["gap_score"] / 2.0 + features["breakout_score"]) / 3.0
            )
        elif label == "ROLLOVER":
            score = features["rollover_score"]
        elif label == "LOW_LIQUIDITY":
            score = min(1.0, ((features["spread_ticks"] / 4.0) + (1.0 - min(1.0, features["volume_ratio"]))) / 2.0)
        else:
            score = 0.55
        return max(0.35, min(0.98, float(score)))

    def _neutral_snapshot(self, reason: str) -> RegimeSnapshot:
        return RegimeSnapshot(
            label="NEUTRAL",
            confidence=0.35,
            risk_state="NORMAL",
            evidence=[reason],
            features={},
            adaptive_policy=self._policy_for("NEUTRAL"),
        )

