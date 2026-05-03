"""Audit utilities (hash-chain, integrity checks)."""

from lumina_core.audit.hash_chain import append_hash_chained_jsonl, validate_hash_chain
from lumina_core.audit.logger import AuditChainError, AuditLogger, ChainValidationReport, StreamRegistry
from lumina_core.audit.streams import get_audit_logger, register_default_streams

__all__ = [
    "append_hash_chained_jsonl",
    "validate_hash_chain",
    "AuditChainError",
    "AuditLogger",
    "ChainValidationReport",
    "StreamRegistry",
    "get_audit_logger",
    "register_default_streams",
]
