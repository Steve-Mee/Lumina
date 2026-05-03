"""Engine bindings for event-driven agent orchestration."""

from __future__ import annotations
import logging

from typing import Any, Callable

from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC


def bind_engine_event_bus(engine: Any, event_bus: Any) -> list[str]:
    """Subscribe execution aggregate (EventBus) to dream-state updates and optional blackboard policy mirror."""
    tokens: list[str] = []
    if event_bus is None or not hasattr(event_bus, "subscribe"):
        return tokens

    def _execution_handler(event: Any) -> None:
        payload = getattr(event, "payload", {})
        if not isinstance(payload, dict):
            return
        confidence = float(payload.get("confidence", payload.get("confluence_score", 0.0)) or 0.0)
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
            if "approved" in meta or "approved" in payload:
                approved = bool(meta.get("approved", payload.get("approved", False)))
                reason = str(meta.get("reason", payload.get("reason", "")) or "")
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
        payload = getattr(event, "payload", {})
        if isinstance(payload, dict):
            engine.set_current_dream_fields(payload)

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
