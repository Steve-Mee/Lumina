from __future__ import annotations
import logging

import json
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


class _CalibrationStore:
    """Persist and load the emotional calibration profile."""

    def __init__(self, model_path: Path) -> None:
        """Initialize the store for the provided calibration file."""
        self.model_path = model_path

    def load_into(self, calibration: Dict[str, float]) -> None:
        """Load known calibration keys from disk into the provided mapping."""
        if not self.model_path.exists():
            return
        try:
            loaded = json.loads(self.model_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return
            for key in calibration:
                if key in loaded:
                    calibration[key] = float(loaded[key])
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/engine/emotional_twin_components.py:30"
            )
            return

    def save(self, calibration: Dict[str, float]) -> None:
        """Persist the calibration mapping to disk."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")


class _ObservationBuilder:
    """Build observation features from runtime context."""

    def __init__(self, context: Any) -> None:
        """Bind the runtime context used to build observations."""
        self.context = context

    def _extract_last_trade_hours(self) -> float:
        """Return hours elapsed since the most recent trade."""
        if not getattr(self.context, "trade_log", None):
            return 24.0
        ts_raw = self.context.trade_log[-1].get("ts")
        try:
            ts_dt = ts_raw if isinstance(ts_raw, datetime) else datetime.fromisoformat(str(ts_raw))
            return (datetime.now() - ts_dt).total_seconds() / 3600
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/engine/emotional_twin_components.py:54"
            )
            return 24.0

    def _calculate_drawdown(self) -> float:
        """Calculate drawdown using equity curve or simulator fallback values."""
        equity_curve = list(getattr(self.context, "equity_curve", []))
        if len(equity_curve) >= 2:
            peak = float(max(equity_curve))
            current = float(equity_curve[-1])
            return (peak - current) / peak if peak > 0 else 0.0
        sim_peak = float(getattr(self.context, "sim_peak", 0.0) or 0.0)
        equity = float(getattr(self.context, "account_equity", 0.0) or 0.0)
        return ((sim_peak - equity) / sim_peak) if sim_peak > 0 else 0.0

    def build(self) -> Dict[str, Any]:
        """Build and return the observation consumed by emotional bias logic."""
        dream = self.context.get_current_dream_snapshot()
        price = self.context.live_quotes[-1]["last"] if self.context.live_quotes else 5000.0
        regime = self.context.detect_market_regime(self.context.ohlc_1min.tail(60))
        recent_pnl = self.context.pnl_history[-15:] if hasattr(self.context, "pnl_history") else []
        drawdown = self._calculate_drawdown()
        last_trade_hours = self._extract_last_trade_hours()
        tape_delta = float(getattr(getattr(self.context, "market_data", None), "cumulative_delta_10", 0.0) or 0.0)

        return {
            "price": float(price),
            "regime": regime,
            "confidence": float(dream.get("confidence", 0.5)),
            "confluence": float(dream.get("confluence_score", 0.5)),
            "recent_pnl_mean": float(np.mean(recent_pnl)) if recent_pnl else 0.0,
            "recent_pnl_std": float(np.std(recent_pnl)) if len(recent_pnl) > 1 else 0.0,
            "equity_drawdown": float(drawdown),
            "time_since_last_trade": float(last_trade_hours),
            "last_pnl": float(self.context.pnl_history[-1]) if self.context.pnl_history else 0.0,
            "tape_delta": tape_delta,
        }


class _BiasDetector:
    """Compute the emotional bias vector from observation features."""

    def __init__(self, context: Any) -> None:
        """Initialize with context required for adaptive policy sensitivity."""
        self.context = context

    def _base_scores(self, obs: Dict[str, Any], pnl_len: int) -> Dict[str, float]:
        """Compute the raw pre-calibration bias scores."""
        bias = {
            "fomo_score": 0.0,
            "tilt_score": 0.0,
            "boredom_score": 0.0,
            "revenge_risk": 0.0,
        }

        if (
            obs["confidence"] > 0.80
            and obs["recent_pnl_mean"] > 0
            and (obs["regime"] in ["TRENDING", "BREAKOUT"] or obs.get("tape_delta", 0.0) > 500)
        ):
            bias["fomo_score"] = min(
                1.0,
                (obs["confidence"] - 0.75) * 3.0
                + abs(obs["recent_pnl_mean"]) / 200
                + obs.get("tape_delta", 0.0) / 20000.0,
            )

        if obs["equity_drawdown"] > 0.04 or (obs["recent_pnl_mean"] < -50 and pnl_len > 5):
            bias["tilt_score"] = min(1.0, obs["equity_drawdown"] * 15 + 0.4)

        if obs["time_since_last_trade"] > 4:
            bias["boredom_score"] = min(1.0, (obs["time_since_last_trade"] - 4) / 12)

        if obs["last_pnl"] < -300 and obs["confidence"] > 0.8:
            bias["revenge_risk"] = min(1.0, 0.7 + abs(obs["last_pnl"]) / 1000)

        return bias

    def _apply_sensitivity(
        self,
        bias: Dict[str, float],
        calibration: Dict[str, float],
    ) -> None:
        """Apply calibration and adaptive regime sensitivity in place."""
        bias["fomo_score"] *= calibration["fomo_sensitivity"]
        bias["tilt_score"] *= calibration["tilt_sensitivity"]
        bias["boredom_score"] *= calibration["boredom_sensitivity"]
        bias["revenge_risk"] *= calibration["revenge_sensitivity"]

        regime_snapshot = getattr(self.context, "current_regime_snapshot", {}) or {}
        adaptive_policy = regime_snapshot.get("adaptive_policy", {}) if isinstance(regime_snapshot, dict) else {}
        regime_sensitivity = float(adaptive_policy.get("emotional_twin_sensitivity", 1.0) or 1.0)
        for key in bias:
            bias[key] *= regime_sensitivity

    def _apply_baseline_and_noise(self, bias: Dict[str, float], baselines: Dict[str, float]) -> None:
        """Apply baseline continuity and bounded stochastic jitter in place."""
        bias["fomo_score"] += baselines["fomo_base"]
        bias["tilt_score"] += baselines["tilt_base"]
        bias["boredom_score"] += baselines["boredom_base"]
        bias["revenge_risk"] += baselines["revenge_base"]

        for key in bias:
            bias[key] = min(1.0, max(0.0, bias[key] + float(np.random.normal(0, 0.08))))

    def compute(
        self,
        obs: Dict[str, Any],
        calibration: Dict[str, float],
        baselines: Dict[str, float],
        pnl_len: int,
    ) -> Dict[str, float]:
        """Return the full emotional bias vector using observation and calibration."""
        bias = self._base_scores(obs, pnl_len)
        self._apply_sensitivity(bias, calibration)
        self._apply_baseline_and_noise(bias, baselines)
        return bias


class _DecisionCorrector:
    """Apply bias-based corrections to dream state proposals."""

    def __init__(self, context: Any) -> None:
        """Initialize with context for config and time dependent values."""
        self.context = context

    @staticmethod
    def _normalize_reason_seed(reason: Any) -> str:
        """Strip previously appended emotional correction fragments from the seed reason."""
        seed = str(reason or "").strip()
        marker = " | EMO_CORRECT:"
        if marker in seed:
            seed = seed.split(marker, 1)[0].strip()
        return seed or "Initial"

    def _apply_fomo(self, corrected: Dict[str, Any], bias: Dict[str, float]) -> None:
        """Apply FOMO correction rules in place when threshold is breached."""
        if bias.get("fomo_score", 0.0) <= 0.7:
            return
        corrected["confluence_score"] = max(corrected.get("confluence_score", 0.0), 0.88)
        min_conf = float(getattr(getattr(self.context, "config", None), "min_confluence", 0.7))
        corrected["min_confluence_override"] = max(
            float(corrected.get("min_confluence_override", 0.0)), min_conf + 0.08
        )
        corrected["reason"] += " | EMO_CORRECT: FOMO -> higher confluence"
        if corrected.get("signal") == "BUY" and "target" in corrected:
            corrected["target"] = float(corrected["target"]) * 0.85

    def _apply_tilt(self, corrected: Dict[str, Any], bias: Dict[str, float]) -> None:
        """Apply tilt correction rules in place when threshold is breached."""
        if bias.get("tilt_score", 0.0) <= 0.6:
            return
        corrected["position_size_multiplier"] = 0.5
        corrected["stop_widen_multiplier"] = 1.3
        corrected["reason"] += " | EMO_CORRECT: Tilt -> halved size, wider stop"
        corrected["qty"] = float(corrected.get("qty", 1)) * 0.4

    def _apply_boredom(self, corrected: Dict[str, Any], bias: Dict[str, float]) -> None:
        """Apply boredom correction rules in place when threshold is breached."""
        if bias.get("boredom_score", 0.0) <= 0.8:
            return
        corrected["signal"] = "HOLD"
        corrected["hold_until_ts"] = (datetime.now() + timedelta(minutes=15)).timestamp()
        corrected["reason"] += " | EMO_CORRECT: Boredom -> no trade"

    def _apply_revenge(self, corrected: Dict[str, Any], bias: Dict[str, float]) -> None:
        """Apply revenge correction rules in place when threshold is breached."""
        if bias.get("revenge_risk", 0.0) <= 0.7:
            return
        corrected["confluence_score"] = max(corrected.get("confluence_score", 0.0), 0.92)
        corrected["reason"] += " | EMO_CORRECT: Revenge -> strict rules"

    def apply(self, main_dream: Dict[str, Any], bias: Dict[str, float]) -> Dict[str, Any]:
        """Return a corrected copy of the provided dream state."""
        corrected = main_dream.copy()
        corrected["reason"] = self._normalize_reason_seed(corrected.get("reason", ""))
        self._apply_fomo(corrected, bias)
        self._apply_tilt(corrected, bias)
        self._apply_boredom(corrected, bias)
        self._apply_revenge(corrected, bias)
        return corrected


class _CalibrationTrainer:
    """Train calibration sensitivities from memory, reflections and feedback."""

    def _count_from_memory(self, memory: deque[Dict[str, Any]]) -> Dict[str, int]:
        """Count bias events from memory records."""
        counts = {
            "neg_reflections": 0,
            "revenge_mentions": 0,
            "fomo_mentions": 0,
            "boredom_mentions": 0,
        }
        for item in list(memory):
            bias = item.get("bias", {}) if isinstance(item, dict) else {}
            if float(bias.get("tilt_score", 0.0)) > 0.6:
                counts["neg_reflections"] += 1
            if float(bias.get("revenge_risk", 0.0)) > 0.7:
                counts["revenge_mentions"] += 1
            if float(bias.get("fomo_score", 0.0)) > 0.7:
                counts["fomo_mentions"] += 1
            if float(bias.get("boredom_score", 0.0)) > 0.8:
                counts["boredom_mentions"] += 1
        return counts

    def _count_from_reflections(self, reflections: List[Dict[str, Any]], counts: Dict[str, int]) -> None:
        """Update event counts using historical trade reflections."""
        for item in reflections[-500:]:
            pnl = float(item.get("pnl", 0.0)) if isinstance(item, dict) else 0.0
            if pnl < 0:
                counts["neg_reflections"] += 1
            txt = str(item).lower()
            if "revenge" in txt:
                counts["revenge_mentions"] += 1
            if "fomo" in txt or "chase" in txt:
                counts["fomo_mentions"] += 1
            if "bored" in txt or "overtrade" in txt:
                counts["boredom_mentions"] += 1

    def _count_from_feedback(self, feedback_items: List[Any], counts: Dict[str, int]) -> None:
        """Update event counts using user feedback items."""
        for fb in feedback_items[-500:]:
            txt = str(fb).lower()
            if "revenge" in txt or "tilt" in txt:
                counts["revenge_mentions"] += 1
            if "fomo" in txt or "late entry" in txt:
                counts["fomo_mentions"] += 1
            if "bored" in txt or "forced trade" in txt:
                counts["boredom_mentions"] += 1

    def train(
        self,
        calibration: Dict[str, float],
        memory: deque[Dict[str, Any]],
        reflections: List[Dict[str, Any]],
        feedback_items: List[Any],
    ) -> Dict[str, float]:
        """Return updated calibration after counting emotional signal markers."""
        counts = self._count_from_memory(memory)
        self._count_from_reflections(reflections, counts)
        self._count_from_feedback(feedback_items, counts)

        total = max(1, len(memory) + len(reflections) + len(feedback_items))
        neg_ratio = counts["neg_reflections"] / max(1, len(memory) + len(reflections))

        calibration["tilt_sensitivity"] = max(0.6, min(2.0, 0.9 + neg_ratio * 1.2))
        calibration["revenge_sensitivity"] = max(0.6, min(2.0, 0.9 + counts["revenge_mentions"] / total * 6.0))
        calibration["fomo_sensitivity"] = max(0.6, min(2.0, 0.9 + counts["fomo_mentions"] / total * 6.0))
        calibration["boredom_sensitivity"] = max(0.6, min(2.0, 0.9 + counts["boredom_mentions"] / total * 6.0))
        return dict(calibration)
