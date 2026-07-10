"""Decision lineage fingerprints and audit payload builders."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.order_gatekeeper.engine_helpers import resolve_blackboard, resolve_event_bus

def agents_from_blackboard(engine: Any) -> list[dict[str, Any]]:
    board = resolve_blackboard(engine)
    if board is None or not hasattr(board, "latest"):
        return []

    topics = (
        "agent.rl.proposal",
        "agent.news.proposal",
        "agent.emotional_twin.proposal",
        "agent.swarm.proposal",
        "agent.tape.proposal",
    )
    agents: list[dict[str, Any]] = []
    for topic in topics:
        event = board.latest(topic)
        if event is None:
            continue

        try:
            from lumina_core.agent_orchestration.schemas import AgentProposalPayload, typed_payload_from_event

            proposal = typed_payload_from_event(event, AgentProposalPayload)
        except Exception:
            continue
        payload = proposal.model_dump(mode="json", exclude_none=False)
        producer = str(getattr(event, "producer", "") or "")
        agent_id = str(
            payload.get("agent_id") or payload.get("chosen_strategy") or producer or topic
        )
        confidence = float(
            proposal.confidence
            or payload.get("confluence_score", getattr(event, "confidence", 0.0))
            or 0.0
        )
        agents.append(
            {
                "agent_id": agent_id,
                "topic": topic,
                "producer": producer,
                "confidence": confidence,
                "signal": str(proposal.signal or payload.get("sentiment_signal", "") or ""),
                "reason": str(proposal.reason or payload.get("why_no_trade", "") or ""),
                "timestamp": str(getattr(event, "timestamp", "") or ""),
                "correlation_id": str(getattr(event, "correlation_id", "") or ""),
                "sequence": int(getattr(event, "sequence", 0) or 0),
                "lineage": {
                    "event_hash": str(getattr(event, "event_hash", "") or ""),
                    "prev_hash": str(getattr(event, "prev_hash", "") or ""),
                },
            }
        )
    return agents


def domain_event_fingerprint(event: Any) -> str:
    raw = event.to_dict() if hasattr(event, "to_dict") else {}
    body = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def execution_aggregate_lineage(engine: Any) -> dict[str, Any]:
    from lumina_core.agent_orchestration.schemas import (
        TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
        TradingEngineExecutionAggregate,
        typed_payload_from_event,
    )

    bus = resolve_event_bus(engine)
    if bus is None or not hasattr(bus, "latest"):
        return {}
    event = bus.latest(TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC)
    if event is None:
        return {}

    try:
        agg = typed_payload_from_event(event, TradingEngineExecutionAggregate)
    except Exception:
        return {}
    meta = getattr(event, "metadata", {}) or {}
    conf = float(agg.confidence or agg.confluence_score or 0.0)
    seq = int(meta.get("sequence", 0) or 0)
    fingerprint = domain_event_fingerprint(event)
    return {
        "topic": TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
        "producer": str(getattr(event, "producer", "") or ""),
        "confidence": conf,
        "timestamp": str(getattr(event, "timestamp", "") or ""),
        "correlation_id": str(meta.get("correlation_id", "") or ""),
        "sequence": seq,
        "lineage": {
            "event_hash": fingerprint,
            "prev_hash": "",
        },
        "signal": str(agg.signal or ""),
        "chosen_strategy": str(agg.chosen_strategy or ""),
    }


def agents_from_dream(engine: Any) -> list[dict[str, Any]]:
    blackboard_agents = agents_from_blackboard(engine)
    if not blackboard_agents:
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="BLACKBOARD_AGENT_PROPOSALS_MISSING",
            message="No agent proposals available on blackboard topics.",
        )
    return blackboard_agents


def build_audit_payload(
    engine: Any,
    *,
    symbol: str,
    regime: str,
    proposed_risk: float,
    mode: str,
    stage: str,
    final_decision: str,
    reason: str,
    var_payload: dict[str, Any] | None = None,
    mc_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not hasattr(engine, "get_current_dream_snapshot"):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="DREAM_SNAPSHOT_PROVIDER_MISSING",
            message="Engine must expose get_current_dream_snapshot for audit payloads.",
        )
    snapshot = engine.get_current_dream_snapshot() or {}
    if not isinstance(snapshot, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="DREAM_SNAPSHOT_INVALID",
            message="get_current_dream_snapshot must return a dict.",
        )

    probability = float(snapshot.get("confidence", snapshot.get("confluence_score", 0.0)) or 0.0)
    expected_value = float(snapshot.get("expected_value", snapshot.get("ev", 0.0)) or 0.0)
    decision_id = f"{symbol}-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:8]}"
    agents = agents_from_dream(engine)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision_id": decision_id,
        "stage": stage,
        "symbol": str(symbol),
        "regime": str(regime),
        "mode": str(mode),
        "proposed_risk": float(proposed_risk),
        "agents_involved": agents,
        "agent_lineage": agents,
        "execution_aggregate_lineage": execution_aggregate_lineage(engine),
        "probability": probability,
        "expected_value": expected_value,
        "var_impact": dict(var_payload or {}),
        "monte_carlo": dict(mc_payload or {}),
        "final_decision": str(final_decision),
        "reason": str(reason),
    }
