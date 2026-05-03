from __future__ import annotations

from pathlib import Path

from lumina_core.audit.audit_logger import AuditLogger, StreamRegistry

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
    lumina_bible: Path | str | None = None,
) -> None:
    stream_paths = {
        "trade_decision": Path(trade_decision),
        "agent_decision": Path(agent_decision),
        "evolution_meta": Path(evolution_meta),
        "security": Path(security),
        "governance.real_promotion": Path(governance_real_promotion),
        "evolution.decisions": Path(evolution_decisions),
        "agent_thought": Path(agent_thought),
        "safety.constitution": Path(safety_constitution),
        "trade_reconciler": Path(trade_reconciler),
    }
    if lumina_bible is not None:
        stream_paths["lumina_bible"] = Path(lumina_bible)

    for stream_name, stream_path in stream_paths.items():
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        _LOGGER.register_stream(stream_name, stream_path)
