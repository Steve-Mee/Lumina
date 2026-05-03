from __future__ import annotations

from lumina_core.inference.llm_client import LLMCallPath, LLMCallResult
from lumina_core.inference.llm_router import LLMDecisionRouter
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.risk.schemas import ArbitrationState


def _real_policy() -> RiskPolicy:
    return RiskPolicy(
        daily_loss_cap=-1000.0,
        max_consecutive_losses=3,
        max_open_risk_per_instrument=500.0,
        max_total_open_risk=3000.0,
        max_exposure_per_regime=2000.0,
        cooldown_after_streak=30,
        session_cooldown_minutes=15,
        enforce_session_guard=True,
        kelly_fraction=0.25,
        kelly_min_confidence=0.65,
        var_95_limit_usd=1200.0,
        var_99_limit_usd=1800.0,
        es_95_limit_usd=1500.0,
        es_99_limit_usd=2200.0,
        margin_min_confidence=0.6,
        runtime_mode="real",
    )


def _base_real_state() -> ArbitrationState:
    return ArbitrationState(
        runtime_mode="real",
        daily_pnl=250.0,
        account_equity=50_000.0,
        drawdown_pct=1.0,
        drawdown_kill_percent=25.0,
        used_margin=1000.0,
        free_margin=5000.0,
        equity_snapshot_ok=True,
        equity_snapshot_reason="ok",
        open_risk_by_symbol={},
        total_open_risk=0.0,
        var_95_usd=100.0,
        var_99_usd=150.0,
        es_95_usd=200.0,
        es_99_usd=250.0,
        live_position_qty=0,
    )


def _llm_result(*, payload: dict[str, object], path: LLMCallPath, fallback: bool = False) -> LLMCallResult:
    return LLMCallResult(
        payload_out=dict(payload),
        fallback=fallback,
        latency_ms=12.0,
        model_version="test-model",
        prompt_hash="prompt-hash",
        response_hash="response-hash",
        temperature=0.35,
        provider="test-provider",
        decision_context_id="ctx-llm-router",
        path=path,
        error="timeout" if fallback else None,
    )


def test_after_llm_call_preserves_creative_output_and_confidence() -> None:
    # gegeven
    router = LLMDecisionRouter()
    result = _llm_result(
        payload={
            "signal": "HOLD",
            "confidence": 0.91,
            "reason": "Counterfactual dream mutation suggests delayed momentum re-entry",
        },
        path="llm_reasoning",
    )

    # wanneer
    routed = router.after_llm_call(result, context="creative_reasoning")

    # dan
    assert routed.routing_path == "llm_reasoning"
    assert routed.llm_confidence == 0.91
    assert routed.payload["reason"].startswith("Counterfactual dream mutation")
    assert routed.payload["signal"] == "HOLD"


def test_after_llm_call_maps_fallback_to_rule_based_hold() -> None:
    # gegeven
    router = LLMDecisionRouter()
    result = _llm_result(
        payload={"signal": "BUY", "confidence": 0.99, "reason": "model timeout"},
        path="fast_rule",
        fallback=True,
    )

    # wanneer
    routed = router.after_llm_call(result, context="consensus")

    # dan
    assert routed.routing_path == "rule_based_fallback"
    assert routed.fallback is True
    assert routed.payload["signal"] == "HOLD"
    assert routed.rule_based_rationale == "timeout"


def test_real_mode_low_confidence_is_rejected_before_order_execution() -> None:
    # gegeven
    router = LLMDecisionRouter(low_confidence_threshold_real=0.65)
    final_arbitration = FinalArbitration(_real_policy())
    routed = router.after_llm_call(
        _llm_result(payload={"signal": "BUY", "confidence": 0.32, "quantity": 1}, path="llm_reasoning"),
        context="order",
    )

    # wanneer
    decision = router.propose_order_from_llm(
        routed_output=routed,
        symbol="MES",
        runtime_mode="real",
        current_state=_base_real_state(),
        final_arbitration=final_arbitration,
    )

    # dan
    assert decision.executable_approved is False
    assert decision.weighted_by_rules is True
    assert decision.arbitration.reason == "llm_confidence_below_real_threshold"


def test_real_mode_never_executes_on_llm_only_when_arbitration_blocks() -> None:
    # gegeven
    router = LLMDecisionRouter(low_confidence_threshold_real=0.2)
    final_arbitration = FinalArbitration(_real_policy())
    routed = router.after_llm_call(
        _llm_result(
            payload={
                "signal": "BUY",
                "confidence": 0.93,
                "quantity": 1,
                "reference_price": 5000.0,
                "stop": 4999.0,
                "proposed_risk": 1.0,
            },
            path="llm_reasoning",
        ),
        context="order",
    )
    state = _base_real_state().model_copy(
        update={"equity_snapshot_ok": False, "equity_snapshot_reason": "provider_unavailable"}
    )

    # wanneer
    decision = router.propose_order_from_llm(
        routed_output=routed,
        symbol="MES",
        runtime_mode="real",
        current_state=state,
        final_arbitration=final_arbitration,
    )

    # dan
    assert decision.real_never_llm_only is True
    assert decision.executable_approved is False
    assert decision.arbitration.status == "REJECTED"
    assert decision.arbitration.reason == "provider_unavailable"


def test_sim_mode_keeps_creative_order_path_executable_with_arbitration() -> None:
    # gegeven
    router = LLMDecisionRouter(low_confidence_threshold_real=0.95)
    final_arbitration = FinalArbitration(_real_policy())
    routed = router.after_llm_call(
        _llm_result(
            payload={
                "signal": "BUY",
                "confidence": 0.88,
                "quantity": 1,
                "reference_price": 5000.0,
                "stop": 4990.0,
                "target": 5020.0,
                "proposed_risk": 10.0,
                "reason": "radical counterfactual scenario in SIM",
            },
            path="llm_reasoning",
        ),
        context="creative_sim",
    )
    state = _base_real_state().model_copy(
        update={"runtime_mode": "sim", "equity_snapshot_ok": False, "equity_snapshot_reason": "not_required_non_real"}
    )

    # wanneer
    decision = router.propose_order_from_llm(
        routed_output=routed,
        symbol="MES",
        runtime_mode="sim",
        current_state=state,
        final_arbitration=final_arbitration,
    )

    # dan
    assert decision.routed.routing_path == "llm_reasoning"
    assert decision.executable_approved is True
    assert decision.arbitration.status == "APPROVED"


def test_real_execution_gate_blocks_but_creative_payload_remains_intact() -> None:
    # gegeven
    router = LLMDecisionRouter(low_confidence_threshold_real=0.2)
    final_arbitration = FinalArbitration(_real_policy())
    creative_reason = "radical DNA mutation hypothesis for counterfactual momentum reversal"
    routed = router.after_llm_call(
        _llm_result(
            payload={
                "signal": "BUY",
                "confidence": 0.97,
                "quantity": 1,
                "reference_price": 5000.0,
                "stop": 4995.0,
                "target": 5030.0,
                "proposed_risk": 5.0,
                "reason": creative_reason,
                "mutation_depth": "radical",
                "evolution_mode": "radical",
            },
            path="llm_reasoning",
        ),
        context="creative_real_hypothesis",
    )
    state = _base_real_state().model_copy(
        update={"equity_snapshot_ok": False, "equity_snapshot_reason": "provider_unavailable"}
    )

    # wanneer
    decision = router.propose_order_from_llm(
        routed_output=routed,
        symbol="MES",
        runtime_mode="real",
        current_state=state,
        final_arbitration=final_arbitration,
    )

    # dan
    assert decision.executable_approved is False
    assert decision.arbitration.reason == "provider_unavailable"
    assert decision.routed.payload["reason"] == creative_reason
    assert decision.routed.payload["mutation_depth"] == "radical"
    assert decision.routed.payload["evolution_mode"] == "radical"
