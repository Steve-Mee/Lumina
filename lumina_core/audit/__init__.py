"""Audit utilities (hash-chain, integrity checks)."""

from typing import TYPE_CHECKING

from lumina_core.audit.hash_chain import append_hash_chained_jsonl, validate_hash_chain
from lumina_core.audit.audit_logger import AuditChainError, AuditLogger, ChainValidationReport, StreamRegistry
from lumina_core.audit.streams import get_audit_logger, register_default_streams

if TYPE_CHECKING:
    from lumina_core.audit.agent_decision_log import AgentDecisionLog, AgentDecisionLogChainError
    from lumina_core.audit.audit_log_service import AuditLogService
    from lumina_core.audit.replay_validator import DecisionReplayValidator

__all__ = [
    "append_hash_chained_jsonl",
    "validate_hash_chain",
    "AuditChainError",
    "AuditLogger",
    "ChainValidationReport",
    "StreamRegistry",
    "AgentDecisionLog",
    "AgentDecisionLogChainError",
    "AuditLogService",
    "DecisionReplayValidator",
    "get_audit_logger",
    "register_default_streams",
]


def __getattr__(name: str):
    if name in {"AgentDecisionLog", "AgentDecisionLogChainError"}:
        from lumina_core.audit.agent_decision_log import AgentDecisionLog, AgentDecisionLogChainError

        return {
            "AgentDecisionLog": AgentDecisionLog,
            "AgentDecisionLogChainError": AgentDecisionLogChainError,
        }[name]
    if name == "AuditLogService":
        from lumina_core.audit.audit_log_service import AuditLogService

        return AuditLogService
    if name == "DecisionReplayValidator":
        from lumina_core.audit.replay_validator import DecisionReplayValidator

        return DecisionReplayValidator
    raise AttributeError(name)
