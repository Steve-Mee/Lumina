from __future__ import annotations

from pathlib import Path

from lumina_core.audit.logger import AuditLogger, StreamRegistry

_REGISTRY = StreamRegistry(root=Path("state"))
_LOGGER = AuditLogger(registry=_REGISTRY)


def get_audit_logger() -> AuditLogger:
    return _LOGGER


def register_default_streams(
    *,
    trade_decision: Path | str,
    agent_decision: Path | str,
    evolution_meta: Path | str,
    security: Path | str,
    governance_real_promotion: Path | str,
    evolution_decisions: Path | str,
    agent_thought: Path | str,
    safety_constitution: Path | str,
    trade_reconciler: Path | str,
) -> None:
    _LOGGER.register_stream("trade_decision", trade_decision)
    _LOGGER.register_stream("agent_decision", agent_decision)
    _LOGGER.register_stream("evolution_meta", evolution_meta)
    _LOGGER.register_stream("security", security)
    _LOGGER.register_stream("governance.real_promotion", governance_real_promotion)
    _LOGGER.register_stream("evolution.decisions", evolution_decisions)
    _LOGGER.register_stream("agent_thought", agent_thought)
    _LOGGER.register_stream("safety.constitution", safety_constitution)
    _LOGGER.register_stream("trade_reconciler", trade_reconciler)
