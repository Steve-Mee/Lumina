"""Evolution/twin structured log helpers (M5 extract)."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.logging_core import _safe_log

def log_evolution_event(logger: logging.Logger, event_type: str, dna_hash: str | None = None, **kwargs: Any) -> None:
    _safe_log(logger, logging.INFO, "evolution.event", event_type=event_type, dna_hash=dna_hash, **kwargs)


def log_twin_decision(
    logger: logging.Logger,
    dna_hash: str,
    score: float,
    recommendation: bool,
    risk_flags: list[str],
    explanation: str,
    **kwargs: Any,
) -> None:
    _safe_log(
        logger,
        logging.INFO,
        "twin.decision",
        dna_hash=dna_hash,
        score=float(score),
        recommendation=bool(recommendation),
        risk_flags=list(risk_flags),
        explanation=str(explanation),
        **kwargs,
    )


def log_shadow_verdict(logger: logging.Logger, dna_hash: str, verdict_dict: dict[str, Any], **kwargs: Any) -> None:
    _safe_log(logger, logging.INFO, "shadow.verdict", dna_hash=dna_hash, verdict=dict(verdict_dict), **kwargs)


def log_gate_rejection(
    logger: logging.Logger, gate_name: str, reason: str, current_value: Any, limit: Any, **kwargs: Any
) -> None:
    _safe_log(
        logger,
        logging.WARNING,
        "gate.rejection",
        gate_name=str(gate_name),
        reason=str(reason),
        current_value=current_value,
        limit=limit,
        **kwargs,
    )


def log_decision_flow(logger: logging.Logger, decision_context_id: str, step: str, **kwargs: Any) -> None:
    _safe_log(
        logger,
        logging.INFO,
        "decision.flow",
        decision_context_id=str(decision_context_id),
        step=str(step),
        **kwargs,
    )


