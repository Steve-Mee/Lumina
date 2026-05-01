"""Engine bindings for event-driven agent orchestration."""

from __future__ import annotations

from typing import Any, Callable


def bind_engine_blackboard(engine: Any, blackboard: Any) -> list[str]:
    """Bind blackboard handlers to engine and return subscription tokens."""
    tokens: list[str] = []
    if blackboard is None or not hasattr(blackboard, "subscribe"):
        return tokens

    def _proposal_handler(event: Any) -> None:
        payload = getattr(event, "payload", {})
        if isinstance(payload, dict):
            engine.set_current_dream_fields(payload)

    def _execution_handler(event: Any) -> None:
        payload = getattr(event, "payload", {})
        confidence = float(getattr(event, "confidence", payload.get("confidence", 0.0)) or 0.0)
        if not isinstance(payload, dict):
            return

        mode = str(getattr(engine.config, "trade_mode", "paper")).strip().lower()
        if mode == "real" and confidence < 0.8:
            safe_payload = dict(payload)
            safe_payload["signal"] = "HOLD"
            safe_payload["why_no_trade"] = "fail_closed_low_blackboard_confidence"
            safe_payload["confidence"] = confidence
            engine.set_current_dream_fields(safe_payload)
            return
        engine.set_current_dream_fields(payload)

    topic_handlers: dict[str, Callable[[Any], None]] = {
        "agent.news.proposal": _proposal_handler,
        "agent.rl.proposal": _proposal_handler,
        "agent.emotional_twin.proposal": _proposal_handler,
        "agent.swarm.proposal": _proposal_handler,
        "agent.tape.proposal": _proposal_handler,
        "execution.aggregate": _execution_handler,
    }
    for topic, handler in topic_handlers.items():
        try:
            token = blackboard.subscribe(topic, handler)
        except Exception:
            continue
        tokens.append(str(token))
    return tokens
