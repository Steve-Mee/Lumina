from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit import AuditChainError, get_audit_logger
from lumina_core.fault import FaultDomain, FaultPolicy

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class AuditLogService:
    """Central append-only JSONL audit sink for trade decision transparency."""

    path: Path
    enabled: bool = True
    fail_closed_real: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _prev_hash: str = field(default="GENESIS")

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        get_audit_logger().register_stream("trade_decision", self.path)
        self._prev_hash = self._load_prev_hash()

    def _load_prev_hash(self) -> str:
        try:
            if not self.path.exists():
                return "GENESIS"
            tail = self.path.read_text(encoding="utf-8").splitlines()[-1:]
            if not tail:
                return "GENESIS"
            payload = json.loads(tail[0])
            return str(payload.get("entry_hash") or "GENESIS")
        except (OSError, json.JSONDecodeError) as exc:
            FaultPolicy.handle(
                domain=FaultDomain.AUDIT_LOG_SERVICE,
                operation="load_previous_hash",
                exc=exc,
                is_real_mode=False,
                message=f"AuditLogService failed to load previous hash from {self.path}",
                context={"path": str(self.path)},
                logger_obj=logger,
            )
            return "GENESIS"

    @staticmethod
    def _validate_event(payload: dict[str, Any]) -> None:
        required = {"stage", "final_decision", "reason", "mode"}
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"Audit payload missing fields: {missing}")

    def log_decision(self, payload: dict[str, Any], *, is_real_mode: bool = False) -> bool:
        if not self.enabled:
            return True

        event = dict(payload)
        event.setdefault("timestamp", _utc_iso())
        event.setdefault("decision_schema_version", "trade_decision_audit_v1")

        try:
            self._validate_event(event)
            with self._lock:
                appended = get_audit_logger().append(
                    stream="trade_decision",
                    payload=event,
                    path=self.path,
                    mode="real" if is_real_mode else "sim",
                    actor_id="audit_log_service",
                    severity="info",
                    fail_closed_real=bool(self.fail_closed_real),
                )
                self._prev_hash = str(appended.get("entry_hash") or "GENESIS")
            return True
        except (AuditChainError, OSError, ValueError, TypeError) as exc:
            strict_real = bool(self.fail_closed_real and bool(is_real_mode))
            FaultPolicy.handle(
                domain=FaultDomain.AUDIT_LOG_SERVICE,
                operation="append_trade_decision",
                exc=exc,
                is_real_mode=strict_real,
                fault_cls=AuditChainError,
                message=f"AuditLogService failed to append decision event at {self.path}",
                context={"path": str(self.path), "is_real_mode": bool(is_real_mode)},
                logger_obj=logger,
            )
            return False
