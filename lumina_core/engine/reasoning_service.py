"""ReasoningService façade — public import path for XAI / higher-order reasoning.

Bounded modules: ``reasoning_decision_log`` (decision logging), ``reasoning_paths``
(fast-path / SLA / consensus). Public symbols remain importable from this module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from lumina_core.inference import LLMDecisionRouter, LlmClient
from lumina_core.broker.broker_bridge import Order, OrderResult
from .errors import BrokerBridgeError, PolicyGateError
from lumina_core.reasoning.local_inference_engine import LocalInferenceEngine
from .lumina_engine import LuminaEngine
from lumina_core.risk.policy_engine import PolicyEngine
from lumina_core.risk.regime_detector import RegimeDetector, RegimeSnapshot
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.sla_config import reasoning_latency_sla_ms
from lumina_core.logging_utils import correlation_id, get_logger, log_decision_flow
from .reasoning_decision_log import ReasoningDecisionLogError, ReasoningDecisionLogMixin
from .reasoning_paths import ReasoningPathsMixin

logger = get_logger("lumina.reasoning.service")


@dataclass(slots=True)
class ReasoningService(ReasoningPathsMixin, ReasoningDecisionLogMixin):
    """Owns XAI interaction and higher-order reasoning workflows."""

    engine: LuminaEngine
    container: Any | None = None
    inference_engine: LocalInferenceEngine | None = None
    llm_client: LlmClient | None = None
    llm_router: LLMDecisionRouter | None = None
    regime_detector: RegimeDetector | None = None
    latency_sla_ms: float = 300.0
    _sla_breach_streak: int = 0
    _sla_recovery_streak: int = 0

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("ReasoningService requires a LuminaEngine")
        self.latency_sla_ms = float(reasoning_latency_sla_ms())
        if self.inference_engine is None:
            self.inference_engine = LocalInferenceEngine(engine=self.engine)
        if self.llm_client is None:
            self.llm_client = LlmClient(inference_engine=self.inference_engine, engine=self.engine)
        if self.llm_router is None:
            self.llm_router = LLMDecisionRouter()
        if self.regime_detector is None:
            self.regime_detector = getattr(self.engine, "regime_detector", None)

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _observability_service(self):
        return getattr(self.engine, "observability_service", None)

    def submit_order(self, order: Order) -> OrderResult:
        if self.container is None or getattr(self.container, "broker", None) is None:
            raise BrokerBridgeError("BrokerBridge is not configured on ReasoningService")

        mode = str(getattr(self.engine.config, "trade_mode", "paper")).strip().lower()
        dream = self.engine.get_current_dream_snapshot()
        decision_context_id = self._new_decision_context_id("submit_order")
        with correlation_id(decision_context_id):
            try:
                log_decision_flow(logger, decision_context_id, "submit_order.start", mode=mode)
            except Exception:
                pass
            price = float(
                getattr(order, "metadata", {}).get("reference_price", 0.0)
                if isinstance(getattr(order, "metadata", {}), dict)
                else 0.0
            )
            stop = float(getattr(order, "stop_loss", 0.0) or 0.0)
            proposed_risk = abs(price - stop) if price > 0.0 and stop > 0.0 else 0.0

            gate_allowed, gate_reason = enforce_pre_trade_gate(
                self.engine,
                symbol=str(getattr(order, "symbol", getattr(self.engine.config, "instrument", "UNKNOWN"))),
                regime=str(dream.get("regime", "NEUTRAL")),
                proposed_risk=float(proposed_risk),
                order_side=str(getattr(order, "side", "HOLD")).upper(),
            )

            session_allowed = not str(gate_reason).lower().startswith("session guard blocked")
            policy_engine = PolicyEngine(engine=self.engine, broker=self.container.broker)
            gateway_result = policy_engine.evaluate_proposal(
                signal=str(getattr(order, "side", "HOLD")).upper(),
                confluence_score=float(dream.get("confluence_score", 1.0) or 1.0),
                min_confluence=float(getattr(self.engine.config, "min_confluence", 0.0) or 0.0),
                hold_until_ts=float(dream.get("hold_until_ts", 0.0) or 0.0),
                mode=mode,
                session_allowed=bool(session_allowed),
                risk_allowed=bool(gate_allowed),
                lineage={
                    "decision_context_id": decision_context_id,
                    "model_identifier": "reasoning-service-submit-order",
                    "prompt_version": "reasoning-service-v1",
                    "prompt_hash": "reasoning-service-submit-order",
                    "policy_version": "agent-policy-gateway-v1",
                    "provider_route": [str(getattr(self.inference_engine, "active_provider", "unknown-provider"))],
                    "calibration_factor": 1.0,
                },
            )
            if str(gateway_result.get("signal", "HOLD")) == "HOLD" and str(getattr(order, "side", "HOLD")).upper() in {
                "BUY",
                "SELL",
            }:
                raise PolicyGateError(f"ReasoningService policy gate blocked order: {gateway_result.get('reason')}")

            self._safe_structured_log(
                logger,
                logging.INFO,
                "reasoning.submit_order.final_decision",
                decision_context_id=decision_context_id,
                signal=str(getattr(order, "side", "HOLD")).upper(),
                confidence=float(dream.get("confidence", dream.get("confluence_score", 0.0)) or 0.0),
                chosen_strategy=str(dream.get("chosen_strategy", "unknown")),
                stop=float(getattr(order, "stop_loss", 0.0) or 0.0),
                target=float(getattr(order, "take_profit", 0.0) or 0.0),
                explanation=str(gateway_result.get("reason", "")),
                model_used=str(getattr(self.inference_engine, "active_provider", "local")),
            )

            # Phase 1.3.2: B-001 hard removal complete. Parameter no longer exists.
            return policy_engine.execute_order(order)

    def refresh_regime_snapshot(
        self,
        *,
        structure: dict[str, Any] | None = None,
        confluence_score: float | None = None,
    ) -> RegimeSnapshot:
        if self.regime_detector is None:
            label = str(getattr(self.engine, "market_regime", "NEUTRAL") or "NEUTRAL")
            fallback = RegimeSnapshot(label=label, confidence=0.5, risk_state="NORMAL")
            self.engine.current_regime_snapshot = fallback.to_dict()
            return fallback

        df = getattr(self.engine, "ohlc_1min", None)
        if df is None or len(df) < 20:
            fallback = RegimeSnapshot(label="NEUTRAL", confidence=0.35, risk_state="NORMAL")
            self.engine.current_regime_snapshot = fallback.to_dict()
            return fallback

        snapshot = self.regime_detector.detect(
            df,
            instrument=str(getattr(self.engine.config, "instrument", "MES JUN26")),
            confluence_score=float(
                confluence_score
                if confluence_score is not None
                else self.engine.get_current_dream_snapshot().get("confluence_score", 0.0)
            ),
            structure=structure,
        )
        self.engine.current_regime_snapshot = snapshot.to_dict()

        app = self._app()
        setattr(app, "CURRENT_REGIME", snapshot.label)
        setattr(app, "CURRENT_REGIME_RISK_STATE", snapshot.risk_state)
        setattr(app, "REASONING_FAST_PATH_WEIGHT", snapshot.adaptive_policy.fast_path_weight)
        setattr(app, "REASONING_AGENT_ROUTE", list(snapshot.adaptive_policy.agent_route))

        if self.engine.risk_controller is not None:
            self.engine.risk_controller.apply_regime_override(
                regime=snapshot.label,
                risk_state=snapshot.risk_state,
                risk_multiplier=snapshot.adaptive_policy.risk_multiplier,
                cooldown_after_streak=snapshot.adaptive_policy.cooldown_minutes,
            )
        obs = self._observability_service()
        if obs is not None and hasattr(obs, "record_regime_state"):
            try:
                obs.record_regime_state(
                    regime=snapshot.label,
                    confidence=snapshot.confidence,
                    risk_state=snapshot.risk_state,
                    fast_path_weight=snapshot.adaptive_policy.fast_path_weight,
                    high_risk_override=bool(snapshot.adaptive_policy.high_risk),
                )
            except Exception:
                logger.exception("ReasoningService failed to record regime_state metric")
        return snapshot


__all__ = ["ReasoningDecisionLogError", "ReasoningService"]
