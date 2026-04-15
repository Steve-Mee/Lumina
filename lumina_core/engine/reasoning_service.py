from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass
from typing import Any

from .broker_bridge import Order, OrderResult
from .agent_contracts import apply_agent_policy_gateway
from .local_inference_engine import LocalInferenceEngine
from .lumina_engine import LuminaEngine
from .regime_detector import RegimeDetector, RegimeSnapshot
from lumina_core.order_gatekeeper import enforce_pre_trade_gate


@dataclass(slots=True)
class ReasoningService:
    """Owns XAI interaction and higher-order reasoning workflows."""

    engine: LuminaEngine
    container: Any | None = None
    inference_engine: LocalInferenceEngine | None = None
    regime_detector: RegimeDetector | None = None
    latency_sla_ms: float = 300.0
    _sla_breach_streak: int = 0
    _sla_recovery_streak: int = 0

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("ReasoningService requires a LuminaEngine")
        if self.inference_engine is None:
            self.inference_engine = LocalInferenceEngine(engine=self.engine)
        if self.regime_detector is None:
            self.regime_detector = getattr(self.engine, "regime_detector", None)

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _set_fast_path_only(self, enabled: bool, reason: str) -> None:
        app = self._app()
        current = bool(getattr(app, "FAST_PATH_ONLY", False))
        if current == enabled:
            return
        setattr(app, "FAST_PATH_ONLY", enabled)
        state = "enabled" if enabled else "disabled"
        app.logger.warning(f"FAST_PATH_ONLY {state} (reasoning): {reason}")

    def _record_latency(self, elapsed_ms: float, source: str) -> None:
        app = self._app()
        if elapsed_ms > self.latency_sla_ms:
            self._sla_breach_streak += 1
            self._sla_recovery_streak = 0
            if self._sla_breach_streak >= 2:
                self._set_fast_path_only(
                    True,
                    f"{source} latency {elapsed_ms:.1f}ms above SLA {self.latency_sla_ms:.1f}ms",
                )
        else:
            self._sla_recovery_streak += 1
            self._sla_breach_streak = 0
            if self._sla_recovery_streak >= 4:
                self._set_fast_path_only(False, f"{source} latency recovered ({elapsed_ms:.1f}ms)")

        setattr(app, "REASONING_LATENCY_MS", round(float(elapsed_ms), 2))

    def _fast_path_only_enabled(self) -> bool:
        app = self._app()
        return bool(getattr(app, "FAST_PATH_ONLY", False))

    def _session_trading_allowed(self) -> tuple[bool, str]:
        session_guard = getattr(self.engine, "session_guard", None)
        if session_guard is None:
            return True, "Session guard unavailable"

        risk_controller = getattr(self.engine, "risk_controller", None)
        active_limits = getattr(risk_controller, "_active_limits", None)
        enforce_guard = bool(getattr(active_limits, "enforce_session_guard", True))
        if not enforce_guard:
            return True, "Session guard disabled"

        if session_guard.is_rollover_window():
            return False, "rollover window"
        if not session_guard.is_trading_session():
            return False, "outside trading session"
        return True, "ok"

    def _observability_service(self):
        return getattr(self.engine, "observability_service", None)

    def _decision_log(self):
        return getattr(self.engine, "decision_log", None)

    def _log_decision(
        self,
        *,
        agent_id: str,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        model_version: str,
    ) -> None:
        decision_log = self._decision_log()
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
        try:
            decision_log.log_decision(
                agent_id=agent_id,
                raw_input=raw_input,
                raw_output=raw_output,
                confidence=float(confidence),
                policy_outcome=policy_outcome,
                decision_context_id=decision_context_id,
                model_version=model_version,
                prompt_hash=hashlib.sha256(
                    json.dumps(raw_input, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest(),
                prompt_version="reasoning-service-v1",
                policy_version="reasoning-policy-v1",
                provider_route=[str(getattr(self.inference_engine, "active_provider", "unknown-provider"))],
                calibration_factor=1.0,
            )
        except Exception:
            return

    def submit_order(self, order: Order) -> OrderResult:
        if self.container is None or getattr(self.container, "broker", None) is None:
            raise RuntimeError("BrokerBridge is not configured on ReasoningService")

        mode = str(getattr(self.engine.config, "trade_mode", "paper")).strip().lower()
        dream = self.engine.get_current_dream_snapshot()
        price = float(getattr(order, "metadata", {}).get("reference_price", 0.0) if isinstance(getattr(order, "metadata", {}), dict) else 0.0)
        stop = float(getattr(order, "stop_loss", 0.0) or 0.0)
        proposed_risk = abs(price - stop) if price > 0.0 and stop > 0.0 else 0.0

        gate_allowed, gate_reason = enforce_pre_trade_gate(
            self.engine,
            symbol=str(getattr(order, "symbol", getattr(self.engine.config, "instrument", "UNKNOWN"))),
            regime=str(dream.get("regime", "NEUTRAL")),
            proposed_risk=float(proposed_risk),
        )

        session_allowed = not str(gate_reason).lower().startswith("session guard blocked")
        gateway_result = apply_agent_policy_gateway(
            signal=str(getattr(order, "side", "HOLD")).upper(),
            confluence_score=float(dream.get("confluence_score", 1.0) or 1.0),
            min_confluence=float(getattr(self.engine.config, "min_confluence", 0.0) or 0.0),
            hold_until_ts=float(dream.get("hold_until_ts", 0.0) or 0.0),
            mode=mode,
            session_allowed=bool(session_allowed),
            risk_allowed=bool(gate_allowed),
            lineage={
                "model_identifier": "reasoning-service-submit-order",
                "prompt_version": "reasoning-service-v1",
                "prompt_hash": "reasoning-service-submit-order",
                "policy_version": "agent-policy-gateway-v1",
                "provider_route": [str(getattr(self.inference_engine, "active_provider", "unknown-provider"))],
                "calibration_factor": 1.0,
            },
        )
        if str(gateway_result.get("signal", "HOLD")) == "HOLD" and str(getattr(order, "side", "HOLD")).upper() in {"BUY", "SELL"}:
            raise RuntimeError(f"ReasoningService policy gate blocked order: {gateway_result.get('reason')}")

        return self.container.broker.submit_order(order)

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
                pass
        return snapshot

    @staticmethod
    def _route_agent_styles(agent_styles: dict[str, str], snapshot: RegimeSnapshot) -> dict[str, str]:
        ordered_names = [name for name in snapshot.adaptive_policy.agent_route if name in agent_styles]
        if not ordered_names:
            ordered_names = list(agent_styles.keys())
        if snapshot.adaptive_policy.high_risk and "risk" in agent_styles and "risk" not in ordered_names:
            ordered_names.insert(0, "risk")
        if snapshot.adaptive_policy.high_risk:
            ordered_names = ordered_names[: max(1, min(2, len(ordered_names)))]
        return {name: agent_styles[name] for name in ordered_names}

    def infer_json(
        self,
        payload: dict[str, Any],
        timeout: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
    ) -> dict[str, Any] | None:
        assert self.inference_engine is not None
        started = time.perf_counter()
        result = self.inference_engine.infer_json(
            payload,
            timeout=timeout,
            context=context,
            max_retries=max_retries,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self._record_latency(elapsed_ms, source=context)
        self._log_decision(
            agent_id="ReasoningService",
            raw_input=payload,
            raw_output=result if isinstance(result, dict) else {"result": result},
            confidence=float((result or {}).get("confidence", 0.0) if isinstance(result, dict) else 0.0),
            policy_outcome="inference_success" if isinstance(result, dict) else "inference_empty",
            decision_context_id=context,
            model_version=str(payload.get("model", "unknown")),
        )
        return result

    async def multi_agent_consensus(
        self,
        price: float,
        mtf_data: str,
        pa_summary: str,
        structure: dict[str, Any],
        fib_levels: dict[str, Any],
    ) -> dict[str, Any]:
        app = self._app()
        session_allowed, session_reason = self._session_trading_allowed()
        if not session_allowed:
            self._set_fast_path_only(True, f"session_guard: {session_reason}")
            blocked = {
                "signal": "HOLD",
                "confidence": 0.35,
                "reason": f"Fast-path mode active: {session_reason}",
                "agent_votes": {},
                "regime": {"label": "SESSION_BLOCKED", "risk_state": "HIGH_RISK"},
            }
            self._log_decision(
                agent_id="ReasoningService",
                raw_input={"price": price, "mtf_data": mtf_data, "pa_summary": pa_summary, "structure": structure, "fib_levels": fib_levels},
                raw_output=blocked,
                confidence=float(blocked.get("confidence", 0.0)),
                policy_outcome="session_blocked",
                decision_context_id="multi_agent_consensus",
                model_version="reasoning-consensus-v1",
            )
            return blocked

        regime_snapshot = self.refresh_regime_snapshot(structure=structure)
        if self._fast_path_only_enabled():
            app.logger.info("MULTI_AGENT_CONSENSUS_SKIPPED,mode=fast_path_only")
            fast_path = {
                "signal": "HOLD",
                "confidence": 0.4,
                "reason": "Fast-path mode active due to latency SLA breach",
                "agent_votes": {},
                "regime": regime_snapshot.to_dict(),
            }
            self._log_decision(
                agent_id="ReasoningService",
                raw_input={"price": price, "mtf_data": mtf_data, "pa_summary": pa_summary, "structure": structure, "fib_levels": fib_levels},
                raw_output=fast_path,
                confidence=float(fast_path.get("confidence", 0.0)),
                policy_outcome="fast_path_only",
                decision_context_id="multi_agent_consensus",
                model_version="reasoning-consensus-v1",
            )
            return fast_path

        get_dream = getattr(self.engine, "get_current_dream_snapshot", None)
        if callable(get_dream):
            current_confluence = float(get_dream().get("confluence_score", 0.0) or 0.0)
        else:
            current_confluence = 0.0
        if regime_snapshot.adaptive_policy.high_risk and current_confluence < 0.88:
            app.logger.warning(
                "REGIME_CONSERVATIVE_HOLD,regime=%s,confluence=%.2f",
                regime_snapshot.label,
                current_confluence,
            )
            conservative = {
                "signal": "HOLD",
                "confidence": round(max(0.35, regime_snapshot.confidence * 0.7), 2),
                "reason": f"High-risk regime {regime_snapshot.label} forced conservative hold",
                "agent_votes": {},
                "regime": regime_snapshot.to_dict(),
            }
            self._log_decision(
                agent_id="ReasoningService",
                raw_input={"price": price, "mtf_data": mtf_data, "pa_summary": pa_summary, "structure": structure, "fib_levels": fib_levels},
                raw_output=conservative,
                confidence=float(conservative.get("confidence", 0.0)),
                policy_outcome="high_risk_hold",
                decision_context_id="multi_agent_consensus",
                model_version="reasoning-consensus-v1",
            )
            return conservative

        agent_styles = self._route_agent_styles(self.engine.config.agent_styles, regime_snapshot)
        agent_votes: dict[str, Any] = {}
        weighted_signals: dict[str, float] = {}
        weighted_confidence = 0.0
        total_weight = 0.0

        for idx, (agent_name, style) in enumerate(agent_styles.items()):
            weight = max(0.55, 1.0 - (idx * 0.12))
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {
                        "role": "system",
                        "content": f"{style}\nGeef ALLEEN JSON met: signal (BUY/SELL/HOLD), confidence (0-1), reason (max 80 chars)",
                    },
                    {
                        "role": "user",
                        "content": f"""Huidige prijs: {price:.2f}
MTF: {mtf_data}
Price Action: {pa_summary}
Structure: BOS={structure.get('bos')}, CHOCH={structure.get('choch')}
Fibs: {fib_levels}
Wat is jouw trade-besluit?""",
                    },
                ],
                "max_tokens": 150,
                "temperature": 0.1,
            }

            try:
                vote = self.infer_json(payload, timeout=12, context=f"multi_agent_{agent_name}")
                if vote is not None:
                    agent_votes[agent_name] = vote
                    signal = str(vote.get("signal", "HOLD") or "HOLD").upper()
                    confidence = float(vote.get("confidence", 0.5) or 0.5)
                    weighted_signals[signal] = weighted_signals.get(signal, 0.0) + weight
                    weighted_confidence += confidence * weight
                    total_weight += weight
            except (json.JSONDecodeError, KeyError, TypeError, TimeoutError, RuntimeError, ValueError) as exc:
                app.logger.error(f"Multi-agent parse error ({agent_name}): {exc}")
                agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "API error"}

            if agent_name not in agent_votes:
                agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "Inference unavailable"}
                weighted_signals["HOLD"] = weighted_signals.get("HOLD", 0.0) + weight * 0.7
                weighted_confidence += 0.3 * weight
                total_weight += weight

        most_common_signal = max(weighted_signals, key=weighted_signals.get) if weighted_signals else "HOLD"
        top_weight = weighted_signals.get(most_common_signal, 0.0)
        consistency = top_weight / max(total_weight, 1e-9)
        avg_confidence = weighted_confidence / max(total_weight, 1e-9)
        consensus = {
            "signal": most_common_signal if consistency >= 0.67 else "HOLD",
            "confidence": round(avg_confidence * consistency, 2),
            "reason": f"Consensus van {list(agent_votes.keys())} | Consistency {consistency:.2f}",
            "agent_votes": agent_votes,
            "regime": regime_snapshot.to_dict(),
        }
        app.logger.info(
            "MULTI_AGENT_CONSENSUS,signal=%s,consistency=%.2f,regime=%s",
            consensus["signal"],
            consistency,
            regime_snapshot.label,
        )
        self._log_decision(
            agent_id="ReasoningService",
            raw_input={"price": price, "mtf_data": mtf_data, "pa_summary": pa_summary, "structure": structure, "fib_levels": fib_levels},
            raw_output=consensus,
            confidence=float(consensus.get("confidence", 0.0)),
            policy_outcome="consensus_generated",
            decision_context_id="multi_agent_consensus",
            model_version="reasoning-consensus-v1",
        )
        return consensus

    async def meta_reasoning_and_counterfactuals(
        self,
        consensus: dict[str, Any],
        price: float,
        pa_summary: str,
        past_experiences: str,
    ) -> dict[str, Any]:
        app = self._app()
        if self._fast_path_only_enabled():
            return {
                "meta_score": 0.5,
                "meta_reasoning": "Skipped: fast-path mode active",
                "counterfactuals": [],
            }
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {
                    "role": "system",
                    "content": """Je bent een strenge meta-trading coach. Geen emoties, alleen logica.
Voer de volgende twee stappen uit:
1. Meta-reasoning: Hoe goed was de huidige consensus? Wat zou een top-trader anders hebben gedaan?
2. Counter-factuals: Simuleer 3 alternatieven (geen trade, 2x groter, stop dichterbij) en geef de verwachte uitkomst.
Geef ALLEEN JSON met: meta_score (0-1), meta_reasoning (max 120 chars), counterfactuals (lijst van dicts)""",
                },
                {
                    "role": "user",
                    "content": f"""Huidige consensus: {consensus['signal']} (conf {consensus['confidence']:.2f})
Price Action: {pa_summary}
Relevante eerdere ervaringen: {past_experiences}
Prijs: {price:.2f}
Voer meta-reasoning + counter-factuals uit.""",
                },
            ],
            "max_tokens": 400,
            "temperature": 0.1,
        }

        try:
            meta = self.infer_json(payload, timeout=15, context="meta_reasoning")
            if meta is not None:
                app.logger.info(f"META_REASONING_COMPLETE,meta_score={meta.get('meta_score', 0.5):.2f}")
                self._log_decision(
                    agent_id="ReasoningService",
                    raw_input={"consensus": consensus, "price": price, "pa_summary": pa_summary, "past_experiences": past_experiences},
                    raw_output=meta,
                    confidence=float(meta.get("meta_score", 0.0)),
                    policy_outcome="meta_reasoning_success",
                    decision_context_id="meta_reasoning",
                    model_version="grok-4.20-0309-reasoning",
                )
                return meta
        except Exception as exc:
            app.logger.error(f"Meta-reasoning error: {exc}")

        fallback = {"meta_score": 0.6, "meta_reasoning": "Meta-reasoning niet gelukt", "counterfactuals": []}
        self._log_decision(
            agent_id="ReasoningService",
            raw_input={"consensus": consensus, "price": price, "pa_summary": pa_summary, "past_experiences": past_experiences},
            raw_output=fallback,
            confidence=float(fallback.get("meta_score", 0.0)),
            policy_outcome="meta_reasoning_fallback",
            decision_context_id="meta_reasoning",
            model_version="grok-4.20-0309-reasoning",
        )
        return fallback
