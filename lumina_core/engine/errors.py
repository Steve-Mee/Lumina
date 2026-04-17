from __future__ import annotations


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
