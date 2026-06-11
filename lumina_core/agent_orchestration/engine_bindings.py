"""Engine bindings for event-driven agent orchestration."""

from __future__ import annotations
import logging

from typing import Any, Callable

from pydantic import ValidationError

from lumina_core.agent_orchestration.schemas import (
    AgentProposalPayload,
    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
    TradingEngineExecutionAggregate,
    typed_payload_from_event,
)


def bind_engine_event_bus(engine: Any, event_bus: Any) -> list[str]:
    """Subscribe execution aggregate (EventBus) to dream-state updates and optional blackboard policy mirror."""
    tokens: list[str] = []
    if event_bus is None or not hasattr(event_bus, "subscribe"):
        return tokens

    def _execution_handler(event: Any) -> None:
        try:
            agg = typed_payload_from_event(event, TradingEngineExecutionAggregate)
        except ValidationError:
            return
        confidence = float(agg.confidence or agg.confluence_score or 0.0)
        payload = agg.model_dump(mode="json", exclude_none=False)
        mode = str(getattr(engine.config, "trade_mode", "paper")).strip().lower()
        if mode == "real" and confidence < 0.8:
            safe_payload = dict(payload)
            safe_payload["signal"] = "HOLD"
            safe_payload["why_no_trade"] = "fail_closed_low_aggregate_confidence"
            safe_payload["confidence"] = confidence
            engine.set_current_dream_fields(safe_payload)
        else:
            engine.set_current_dream_fields(payload)
        blackboard = getattr(engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "mark_policy_decision"):
            meta = getattr(event, "metadata", {}) or {}
            approved = bool(meta.get("approved", agg.approved if agg.approved is not None else False))
            reason = str(meta.get("reason", agg.reason or "") or "")
            blackboard.mark_policy_decision(approved=approved, reason=reason)

    try:
        token = event_bus.subscribe(TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC, _execution_handler)
        tokens.append(str(token))
    except Exception:
        logging.exception(
            "Unhandled broad exception fallback in lumina_core/agent_orchestration/engine_bindings.py:bind_event_bus"
        )
    return tokens


def bind_engine_blackboard(engine: Any, blackboard: Any) -> list[str]:
    """Bind blackboard handlers to engine and return subscription tokens."""
    tokens: list[str] = []
    if blackboard is None or not hasattr(blackboard, "subscribe"):
        return tokens

    def _proposal_handler(event: Any) -> None:
        try:
            proposal = typed_payload_from_event(event, AgentProposalPayload)
        except ValidationError:
            return
        engine.set_current_dream_fields(proposal.model_dump(mode="json", exclude_none=False))

    topic_handlers: dict[str, Callable[[Any], None]] = {
        "agent.news.proposal": _proposal_handler,
        "agent.rl.proposal": _proposal_handler,
        "agent.emotional_twin.proposal": _proposal_handler,
        "agent.swarm.proposal": _proposal_handler,
        "agent.tape.proposal": _proposal_handler,
    }
    for topic, handler in topic_handlers.items():
        try:
            token = blackboard.subscribe(topic, handler)
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/agent_orchestration/engine_bindings.py:46"
            )
            continue
        tokens.append(str(token))
    return tokens
