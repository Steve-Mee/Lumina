# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from lumina_core.runtime_context import RuntimeContext
from lumina_core.reasoning.agent_contracts import (
    EmotionalTwinInputSchema,
    EmotionalTwinOutputSchema,
    enforce_contract,
)
from lumina_core.engine.emotional_twin_components import (
    _BiasDetector,
    _CalibrationStore,
    _CalibrationTrainer,
    _DecisionCorrector,
    _ObservationBuilder,
)

logger = logging.getLogger(__name__)


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

        self._calibration_store = _CalibrationStore(self.model_path)
        self._observation_builder = _ObservationBuilder(self.context)
        self._bias_detector = _BiasDetector(self.context)
        self._decision_corrector = _DecisionCorrector(self.context)
        self._calibration_trainer = _CalibrationTrainer()

        self._calibration_store.load_into(self.calibration)

    def _model_hash(self) -> str:
        payload = json.dumps(self.calibration, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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
                is_real_mode=str(getattr(getattr(self.context, "config", None), "trade_mode", "paper")).strip().lower()
                == "real",
            )
        except Exception:
            logger.exception("EmotionalTwinAgent failed to write decision log")

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
        return self._observation_builder.build()

    def _calculate_bias(self, obs: Dict[str, Any]) -> Dict[str, float]:
        """Berekent emotional bias vector (0-1)."""
        baselines = {
            "fomo_base": self.fomo_base,
            "tilt_base": self.tilt_base,
            "boredom_base": self.boredom_base,
            "revenge_base": self.revenge_base,
        }
        pnl_len = len(getattr(self.context, "pnl_history", []))
        return self._bias_detector.compute(obs, self.calibration, baselines, pnl_len)

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

        corrected = self._decision_corrector.apply(main_dream, bias)

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
        blackboard = getattr(self.context, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "add_proposal"):
            blackboard.add_proposal(
                topic="agent.emotional_twin.proposal",
                producer="emotional_twin_agent",
                payload=corrected,
                confidence=float(max(0.0, min(1.0, corrected.get("confluence_score", 0.0) or 0.0))),
            )
        elif hasattr(self.context, "set_current_dream_fields"):
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

        self.calibration = self._calibration_trainer.train(
            self.calibration,
            self.memory,
            reflections,
            feedback_items,
        )
        self._calibration_store.save(self.calibration)
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
    def train_nightly(
        self, trade_reflection_history: List[Dict[str, Any]], user_feedback: List[Any]
    ) -> Dict[str, float]:
        return self.nightly_train(trade_reflection_history, user_feedback)

    # Public API aliases voor testbaarheid en externe integraties.
    def build_observation(self) -> Dict[str, Any]:
        """Publieke wrapper voor _get_observation."""
        return self._get_observation()

    def infer_emotional_bias(self, obs: Dict[str, Any]) -> Dict[str, float]:
        """Publieke wrapper voor _calculate_bias."""
        return self._calculate_bias(obs)

    def generate_counterfactual_human_decision(self, obs: Dict[str, Any], bias: Dict[str, float]) -> Dict[str, str]:
        """Publieke wrapper voor _counterfactual_human_decision."""
        return self._counterfactual_human_decision(bias)

    def apply_to_dream(self, bias: Dict[str, float], decision: Dict[str, str]) -> Dict[str, Any]:
        """Pas emotionele bias-correcties toe op de huidige dreamstate en schrijf terug."""
        _ = decision
        main_dream = self.context.get_current_dream_snapshot()
        corrected = self._decision_corrector.apply(main_dream, bias)

        if hasattr(self.context, "set_current_dream_fields"):
            self.context.set_current_dream_fields(corrected)
        return corrected
