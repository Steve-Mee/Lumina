# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import json
import hashlib
import numpy as np
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.agent_contracts import (
    EmotionalTwinInputSchema,
    EmotionalTwinOutputSchema,
    enforce_contract,
)


class EmotionalTwinAgent:
    """
    Shadow agent die FOMO, tilt, boredom en revenge simuleert.
    Trainbaar op trade_reflection_history + user_feedback.
    Geeft bias aan main DreamState -> bewuste correctie.
    """

    def __init__(self, context: RuntimeContext | Any = None, *, engine: Any | None = None):
        # Compatibel met zowel EmotionalTwinAgent(context=...) als EmotionalTwinAgent(engine=...)
        ctx = context if context is not None else engine
        if ctx is None:
            raise ValueError("EmotionalTwinAgent requires context or engine")
        self.context: Any = ctx

        self.logger = self.context.logger
        self.memory = deque(maxlen=50)  # laatste 50 trades + feedback
        self.model_path = Path("lumina_agents/emotional_twin_profile.json")
        self.calibration: Dict[str, float] = {
            "fomo_sensitivity": 1.0,
            "tilt_sensitivity": 1.0,
            "boredom_sensitivity": 1.0,
            "revenge_sensitivity": 1.0,
        }
        self.fomo_base = 0.0
        self.tilt_base = 0.0
        self.boredom_base = 0.0
        self.revenge_base = 0.0

        if self.model_path.exists():
            try:
                loaded = json.loads(self.model_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    for key in self.calibration:
                        if key in loaded:
                            self.calibration[key] = float(loaded[key])
            except Exception:
                pass

    def _model_hash(self) -> str:
        payload = json.dumps(self.calibration, sort_keys=True)
        return __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()

    def _log_decision(self, raw_input: Dict[str, Any], raw_output: Dict[str, Any], policy_outcome: str) -> None:
        decision_log = getattr(self.context, "decision_log", None)
        if decision_log is None:
            decision_log = getattr(getattr(self.context, "engine", None), "decision_log", None)
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
        try:
            decision_log.log_decision(
                agent_id="EmotionalTwinAgent",
                raw_input=raw_input,
                raw_output=raw_output,
                confidence=float(raw_output.get("confidence", raw_output.get("confluence_score", 0.0)) or 0.0),
                policy_outcome=policy_outcome,
                decision_context_id="emotional_twin_cycle",
                model_version=self._model_hash()[:16],
                prompt_hash=hashlib.sha256(
                    json.dumps(raw_input, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest(),
            )
        except Exception:
            return

    def _contract_input_payload(self) -> Dict[str, Any]:
        dream = self.context.get_current_dream_snapshot()
        obs = self._get_observation()
        return {
            "signal": str(dream.get("signal", "HOLD")),
            "confidence": float(dream.get("confidence", 0.5) or 0.5),
            "confluence_score": float(dream.get("confluence_score", 0.0) or 0.0),
            "regime": str(obs.get("regime", "NEUTRAL")),
            "timestamp": datetime.now().isoformat(),
        }

    def _get_observation(self) -> Dict[str, Any]:
        """Zelfde observatie als main DreamState."""
        dream = self.context.get_current_dream_snapshot()
        price = self.context.live_quotes[-1]["last"] if self.context.live_quotes else 5000.0
        regime = self.context.detect_market_regime(self.context.ohlc_1min.tail(60))
        recent_pnl = self.context.pnl_history[-15:] if hasattr(self.context, "pnl_history") else []

        last_trade_hours = 24.0
        if getattr(self.context, "trade_log", None):
            ts_raw = self.context.trade_log[-1].get("ts")
            try:
                ts_dt = ts_raw if isinstance(ts_raw, datetime) else datetime.fromisoformat(str(ts_raw))
                last_trade_hours = (datetime.now() - ts_dt).total_seconds() / 3600
            except Exception:
                last_trade_hours = 24.0

        equity_curve = list(getattr(self.context, "equity_curve", []))
        if len(equity_curve) >= 2:
            _peak = float(max(equity_curve))
            _cur = float(equity_curve[-1])
            drawdown = (_peak - _cur) / _peak if _peak > 0 else 0.0
        else:
            sim_peak = float(getattr(self.context, "sim_peak", 0.0) or 0.0)
            equity = float(getattr(self.context, "account_equity", 0.0) or 0.0)
            drawdown = ((sim_peak - equity) / sim_peak) if sim_peak > 0 else 0.0
        tape_delta = float(
            getattr(getattr(self.context, "market_data", None), "cumulative_delta_10", 0.0) or 0.0
        )

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

    def _calculate_bias(self, obs: Dict[str, Any]) -> Dict[str, float]:
        """Berekent emotional bias vector (0-1)."""
        bias = {
            "fomo_score": 0.0,
            "tilt_score": 0.0,
            "boredom_score": 0.0,
            "revenge_risk": 0.0,
        }

        # FOMO: hoge confidence + recente win + trending regime of hoge tape delta
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

        # Tilt: grote drawdown of recente verlies streak
        if obs["equity_drawdown"] > 0.04 or (
            obs["recent_pnl_mean"] < -50 and len(self.context.pnl_history) > 5
        ):
            bias["tilt_score"] = min(1.0, obs["equity_drawdown"] * 15 + 0.4)

        # Boredom: lange tijd zonder trade
        if obs["time_since_last_trade"] > 4:
            bias["boredom_score"] = min(1.0, (obs["time_since_last_trade"] - 4) / 12)

        # Revenge: na grote verlies + hoge confidence
        if obs["last_pnl"] < -300 and obs["confidence"] > 0.8:
            bias["revenge_risk"] = min(1.0, 0.7 + abs(obs["last_pnl"]) / 1000)

        # Calibratie-lagen uit nightly train.
        bias["fomo_score"] *= self.calibration["fomo_sensitivity"]
        bias["tilt_score"] *= self.calibration["tilt_sensitivity"]
        bias["boredom_score"] *= self.calibration["boredom_sensitivity"]
        bias["revenge_risk"] *= self.calibration["revenge_sensitivity"]

        regime_snapshot = getattr(self.context, "current_regime_snapshot", {}) or {}
        adaptive_policy = regime_snapshot.get("adaptive_policy", {}) if isinstance(regime_snapshot, dict) else {}
        regime_sensitivity = float(adaptive_policy.get("emotional_twin_sensitivity", 1.0) or 1.0)
        for key in bias:
            bias[key] *= regime_sensitivity

        # Baseline-aanpassingen behouden emotionele state-continuiteit.
        bias["fomo_score"] += self.fomo_base
        bias["tilt_score"] += self.tilt_base
        bias["boredom_score"] += self.boredom_base
        bias["revenge_risk"] += self.revenge_base

        # Kleine randomness voor menselijk gevoel
        for key in bias:
            bias[key] = min(1.0, max(0.0, bias[key] + float(np.random.normal(0, 0.08))))

        return bias

    def _counterfactual_human_decision(self, bias: Dict[str, float]) -> Dict[str, str]:
        """Wat zou een vermoeide trader doen?"""
        if bias["fomo_score"] > 0.7:
            return {"signal": "BUY", "reason": "FOMO - te agressief"}
        if bias["tilt_score"] > 0.6:
            return {"signal": "SELL", "reason": "Tilt - revenge trading"}
        if bias["boredom_score"] > 0.8:
            return {"signal": "HOLD", "reason": "Boredom - forced trade"}
        if bias["revenge_risk"] > 0.7:
            return {"signal": "BUY", "reason": "Revenge after big loss"}
        return {"signal": "HOLD", "reason": "Neutral"}

    def apply_correction(self, main_dream: Dict[str, Any]) -> Dict[str, Any]:
        """Hoofdmethode: main DreamState roept dit aan."""
        obs = self._get_observation()
        bias = self._calculate_bias(obs)
        human_decision = self._counterfactual_human_decision(bias)
        self._last_bias = bias

        corrected = main_dream.copy()
        corrected.setdefault("reason", "")

        # Bewuste correcties (dit is wat een goede trader doet)
        if bias["fomo_score"] > 0.7:
            corrected["confluence_score"] = max(corrected.get("confluence_score", 0.0), 0.88)
            min_conf = float(
                getattr(getattr(self.context, "config", None), "min_confluence", 0.7)
            )
            corrected["min_confluence_override"] = max(
                float(corrected.get("min_confluence_override", 0.0)), min_conf + 0.08
            )
            corrected["reason"] += " | EMO_CORRECT: FOMO -> higher confluence"
            if corrected.get("signal") == "BUY" and "target" in corrected:
                corrected["target"] = float(corrected["target"]) * 0.85  # smaller target

        if bias["tilt_score"] > 0.6:
            corrected["position_size_multiplier"] = 0.5
            corrected["stop_widen_multiplier"] = 1.3
            corrected["reason"] += " | EMO_CORRECT: Tilt -> halved size, wider stop"
            corrected["qty"] = float(corrected.get("qty", 1)) * 0.4  # backward compat

        if bias["boredom_score"] > 0.8:
            corrected["signal"] = "HOLD"
            corrected["hold_until_ts"] = (datetime.now() + timedelta(minutes=15)).timestamp()
            corrected["reason"] += " | EMO_CORRECT: Boredom -> no trade"

        if bias["revenge_risk"] > 0.7:
            corrected["confluence_score"] = max(corrected.get("confluence_score", 0.0), 0.92)
            corrected["reason"] += " | EMO_CORRECT: Revenge -> strict rules"

        # Log de bias
        self.logger.info(
            "EMOTIONAL_TWIN,"
            f"bias_fomo={bias['fomo_score']:.2f},"
            f"tilt={bias['tilt_score']:.2f},"
            f"boredom={bias['boredom_score']:.2f},"
            f"revenge={bias['revenge_risk']:.2f},"
            f"correction_applied={corrected.get('signal', 'HOLD')}"
        )

        # Sla op voor nightly training
        self.memory.append(
            {
                "obs": obs,
                "bias": bias,
                "human_decision": human_decision,
                "final_signal": corrected.get("signal", "HOLD"),
                "ts": datetime.now().isoformat(),
            }
        )

        return corrected

    # Compatibele hook voor bestaande runtime-workers.
    @enforce_contract(
        EmotionalTwinInputSchema,
        EmotionalTwinOutputSchema,
        prompt_version="emotional-twin-v1",
        model_hash_getter=lambda self: self._model_hash(),
        input_builder=lambda self, _args, _kwargs: self._contract_input_payload(),
    )
    def run_cycle(self) -> Dict[str, Any]:
        main_dream = self.context.get_current_dream_snapshot()
        corrected = self.apply_correction(main_dream)
        if hasattr(self.context, "set_current_dream_fields"):
            self.context.set_current_dream_fields(corrected)
        result = dict(corrected)
        result["emotional_bias"] = getattr(self, "_last_bias", {})
        result["confidence"] = float(max(0.0, min(1.0, result.get("confluence_score", 0.0) or 0.0)))
        self._log_decision(
            raw_input={"dream": main_dream, "observation": self._contract_input_payload()},
            raw_output=result,
            policy_outcome="correction_applied" if result.get("signal") != main_dream.get("signal") else "pass_through",
        )
        return result

    def nightly_train(
        self,
        trade_reflection_history: List[Dict[str, Any]] | None = None,
        user_feedback: List[Any] | None = None,
    ) -> Dict[str, float]:
        """Rule-based calibratie op memory + reflections + feedback."""
        reflections = trade_reflection_history or []
        feedback_items = user_feedback or []

        if len(self.memory) < 10 and not reflections and not feedback_items:
            return dict(self.calibration)

        neg_reflections = 0
        revenge_mentions = 0
        fomo_mentions = 0
        boredom_mentions = 0

        for item in list(self.memory):
            bias = item.get("bias", {}) if isinstance(item, dict) else {}
            if float(bias.get("tilt_score", 0.0)) > 0.6:
                neg_reflections += 1
            if float(bias.get("revenge_risk", 0.0)) > 0.7:
                revenge_mentions += 1
            if float(bias.get("fomo_score", 0.0)) > 0.7:
                fomo_mentions += 1
            if float(bias.get("boredom_score", 0.0)) > 0.8:
                boredom_mentions += 1

        for item in reflections[-500:]:
            pnl = float(item.get("pnl", 0.0)) if isinstance(item, dict) else 0.0
            if pnl < 0:
                neg_reflections += 1
            txt = str(item).lower()
            if "revenge" in txt:
                revenge_mentions += 1
            if "fomo" in txt or "chase" in txt:
                fomo_mentions += 1
            if "bored" in txt or "overtrade" in txt:
                boredom_mentions += 1

        for fb in feedback_items[-500:]:
            txt = str(fb).lower()
            if "revenge" in txt or "tilt" in txt:
                revenge_mentions += 1
            if "fomo" in txt or "late entry" in txt:
                fomo_mentions += 1
            if "bored" in txt or "forced trade" in txt:
                boredom_mentions += 1

        total = max(1, len(self.memory) + len(reflections) + len(feedback_items))
        neg_ratio = neg_reflections / max(1, len(self.memory) + len(reflections))

        self.calibration["tilt_sensitivity"] = max(0.6, min(2.0, 0.9 + neg_ratio * 1.2))
        self.calibration["revenge_sensitivity"] = max(
            0.6, min(2.0, 0.9 + revenge_mentions / total * 6.0)
        )
        self.calibration["fomo_sensitivity"] = max(0.6, min(2.0, 0.9 + fomo_mentions / total * 6.0))
        self.calibration["boredom_sensitivity"] = max(
            0.6, min(2.0, 0.9 + boredom_mentions / total * 6.0)
        )

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_path.write_text(json.dumps(self.calibration, indent=2), encoding="utf-8")
        self.logger.info(
            "EMOTIONAL_TWIN_TRAINED,"
            f"memories={len(self.memory)},"
            f"fomo={self.calibration['fomo_sensitivity']:.2f},"
            f"tilt={self.calibration['tilt_sensitivity']:.2f},"
            f"boredom={self.calibration['boredom_sensitivity']:.2f},"
            f"revenge={self.calibration['revenge_sensitivity']:.2f}"
        )
        return dict(self.calibration)

    # Compatibele alias voor bestaande codepaden.
    def train_nightly(self, trade_reflection_history: List[Dict[str, Any]], user_feedback: List[Any]) -> Dict[str, float]:
        return self.nightly_train(trade_reflection_history, user_feedback)

    # Public API aliases voor testbaarheid en externe integraties.
    def build_observation(self) -> Dict[str, Any]:
        """Publieke wrapper voor _get_observation."""
        return self._get_observation()

    def infer_emotional_bias(self, obs: Dict[str, Any]) -> Dict[str, float]:
        """Publieke wrapper voor _calculate_bias."""
        return self._calculate_bias(obs)

    def generate_counterfactual_human_decision(
        self, obs: Dict[str, Any], bias: Dict[str, float]
    ) -> Dict[str, str]:
        """Publieke wrapper voor _counterfactual_human_decision."""
        return self._counterfactual_human_decision(bias)

    def apply_to_dream(self, bias: Dict[str, float], decision: Dict[str, str]) -> Dict[str, Any]:
        """Pas emotionele bias-correcties toe op de huidige dreamstate en schrijf terug."""
        main_dream = self.context.get_current_dream_snapshot()
        corrected = main_dream.copy()
        corrected.setdefault("reason", "")

        if bias.get("fomo_score", 0.0) > 0.7:
            corrected["confluence_score"] = max(corrected.get("confluence_score", 0.0), 0.88)
            min_conf = float(
                getattr(getattr(self.context, "config", None), "min_confluence", 0.7)
            )
            corrected["min_confluence_override"] = max(
                float(corrected.get("min_confluence_override", 0.0)), min_conf + 0.08
            )
            corrected["reason"] += " | EMO_CORRECT: FOMO -> higher confluence"
            if corrected.get("signal") == "BUY" and "target" in corrected:
                corrected["target"] = float(corrected["target"]) * 0.85

        if bias.get("tilt_score", 0.0) > 0.6:
            corrected["position_size_multiplier"] = 0.5
            corrected["stop_widen_multiplier"] = 1.3
            corrected["reason"] += " | EMO_CORRECT: Tilt -> halved size, wider stop"
            corrected["qty"] = float(corrected.get("qty", 1)) * 0.4

        if bias.get("boredom_score", 0.0) > 0.8:
            corrected["signal"] = "HOLD"
            corrected["hold_until_ts"] = (datetime.now() + timedelta(minutes=15)).timestamp()
            corrected["reason"] += " | EMO_CORRECT: Boredom -> no trade"

        if bias.get("revenge_risk", 0.0) > 0.7:
            corrected["confluence_score"] = max(corrected.get("confluence_score", 0.0), 0.92)
            corrected["reason"] += " | EMO_CORRECT: Revenge -> strict rules"

        if hasattr(self.context, "set_current_dream_fields"):
            self.context.set_current_dream_fields(corrected)
        return corrected
