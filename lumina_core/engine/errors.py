from __future__ import annotations

# ── Phase-1 Error Taxonomy ─────────────────────────────────────────────────
# Structured error types consumed by the meta-agent nightly reflection cycle.
# All existing exception classes below remain unchanged.
# ──────────────────────────────────────────────────────────────────────────

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    RECOVERABLE_TRANSIENT = auto()  # retry-able: broker/network blip
    RECOVERABLE_LEARNING = auto()  # informational: meta-agent learning opportunity
    FATAL_UNRECOVERABLE = auto()  # fail-closed: stop trading
    FATAL_MODE_VIOLATION = auto()  # mode-capability breach: stop trading


@dataclass
class LuminaError(Exception):
    severity: ErrorSeverity
    code: str
    message: str
    context: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    lineage_hash: str = ""  # blackboard lineage coupling

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_jsonl(self) -> str:
        return (
            json.dumps(
                {
                    "severity": self.severity.name,
                    "code": self.code,
                    "message": self.message,
                    "context": self.context,
                    "timestamp": self.timestamp.isoformat(),
                    "lineage_hash": self.lineage_hash,
                }
            )
            + "\n"
        )


def log_structured(error: "LuminaError", blackboard=None) -> None:
    """Write structured error to JSONL sink and optionally publish to blackboard."""
    try:
        Path("logs/structured_errors.jsonl").parent.mkdir(parents=True, exist_ok=True)
        with open("logs/structured_errors.jsonl", "a", encoding="utf-8") as _f:
            _f.write(error.to_jsonl())
    except OSError:
        logger.exception("log_structured failed to write structured_errors.jsonl")
    if blackboard is not None and hasattr(blackboard, "add_entry"):
        try:
            blackboard.add_entry("error_event", error.to_jsonl())
        except Exception:
            logger.exception("log_structured failed to publish error event to blackboard")


# ── Existing engine exception hierarchy (unchanged) ───────────────────────


class LuminaEngineError(RuntimeError):
    """Base class for engine-level operational errors."""


class BrokerBridgeError(LuminaEngineError):
    """Raised when broker bridge/configuration fails."""


class PolicyGateError(LuminaEngineError):
    """Raised when policy gate blocks a trade action."""


class SessionGuardError(LuminaEngineError):
    """Raised when SessionGuard is missing or unstable in critical paths."""


class ReconciliationError(LuminaEngineError):
    """Raised for trade reconciliation pipeline failures."""


class AnalysisPipelineError(LuminaEngineError):
    """Raised for deep-analysis and cache pipeline failures."""


def classify_error_code(exc: BaseException, *, fallback: str = "UNCLASSIFIED") -> str:
    """Map runtime exceptions to stable error codes for logs and audit trails."""
    if isinstance(exc, BrokerBridgeError):
        return "BROKER_BRIDGE_ERROR"
    if isinstance(exc, PolicyGateError):
        return "POLICY_GATE_BLOCKED"
    if isinstance(exc, SessionGuardError):
        return "SESSION_GUARD_ERROR"
    if isinstance(exc, ReconciliationError):
        return "RECONCILIATION_ERROR"
    if isinstance(exc, AnalysisPipelineError):
        return "ANALYSIS_PIPELINE_ERROR"
    if isinstance(exc, TimeoutError):
        return "TIMEOUT"
    if isinstance(exc, ValueError):
        return "VALUE_ERROR"
    if isinstance(exc, TypeError):
        return "TYPE_ERROR"
    if isinstance(exc, KeyError):
        return "KEY_ERROR"
    if isinstance(exc, ConnectionError):
        return "CONNECTION_ERROR"
    return str(fallback or "UNCLASSIFIED").strip().upper()


def format_error_code(prefix: str, exc: BaseException, *, fallback: str = "UNCLASSIFIED") -> str:
    lead = str(prefix or "ERR").strip().upper().replace(" ", "_")
    return f"{lead}_{classify_error_code(exc, fallback=fallback)}"
