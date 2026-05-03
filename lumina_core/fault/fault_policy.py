from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger(__name__)


class FaultDomain(StrEnum):
    AGENT_CONTRACT_MIRROR = "agent_contract_mirror"
    AGENT_DECISION_LOG = "agent_decision_log"
    AUDIT_LOGGER = "audit_logger"
    AUDIT_LOG_SERVICE = "audit_log_service"
    EVOLUTION_AUDIT = "evolution_audit"
    EVOLUTION_VETO = "evolution_veto"
    REASONING_DECISION_LOG = "reasoning_decision_log"


@dataclass(slots=True, frozen=True)
class LuminaFault(RuntimeError):
    domain: str
    operation: str
    fault_id: str
    message: str

    def __str__(self) -> str:
        return self.message


class FaultPolicy:
    """Central policy for typed faults across decision/audit paths."""

    @staticmethod
    def handle(
        *,
        domain: FaultDomain | str,
        operation: str,
        exc: BaseException,
        is_real_mode: bool,
        fault_cls: type[Exception] = LuminaFault,
        message: str | None = None,
        context: dict[str, Any] | None = None,
        logger_obj: logging.Logger | None = None,
        raise_in_sim: bool = False,
    ) -> None:
        fault_id = uuid4().hex[:12]
        domain_value = str(domain)
        op = str(operation).strip() or "unknown_operation"
        reason = str(message or f"{domain_value}::{op} failed")
        resolved_logger = logger_obj or logger

        payload: dict[str, Any] = {
            "fault_id": fault_id,
            "domain": domain_value,
            "operation": op,
            "is_real_mode": bool(is_real_mode),
            "cause_type": type(exc).__name__,
            "cause_message": str(exc),
        }
        if context:
            for key, value in context.items():
                if isinstance(value, Path):
                    payload[str(key)] = str(value)
                else:
                    payload[str(key)] = value

        code = FaultPolicy._fault_code(domain=domain_value, operation=op)
        severity = ErrorSeverity.FATAL_MODE_VIOLATION if is_real_mode else ErrorSeverity.RECOVERABLE_LEARNING
        log_structured(
            LuminaError(
                severity=severity,
                code=code,
                message=reason,
                context=payload,
            )
        )
        resolved_logger.exception("%s [fault_id=%s]", reason, fault_id)

        if not is_real_mode and not raise_in_sim:
            return
        raise FaultPolicy._to_exception(
            fault_cls=fault_cls,
            domain=domain_value,
            operation=op,
            fault_id=fault_id,
            message=reason,
        ) from exc

    @staticmethod
    def _to_exception(
        *,
        fault_cls: type[Exception],
        domain: str,
        operation: str,
        fault_id: str,
        message: str,
    ) -> Exception:
        if issubclass(fault_cls, LuminaFault):
            return fault_cls(domain=domain, operation=operation, fault_id=fault_id, message=message)
        try:
            return fault_cls(message)
        except TypeError:
            return RuntimeError(message)

    @staticmethod
    def _fault_code(*, domain: str, operation: str) -> str:
        combined = f"FAULT_{domain}_{operation}"
        normalized = re.sub(r"[^A-Z0-9]+", "_", combined.upper()).strip("_")
        return normalized or "FAULT_UNCLASSIFIED"
