"""AuditStatusMixin methods for TradeReconciler."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.risk.mode_capabilities import resolve_mode_capabilities

logger = logging.getLogger(__name__)


class AuditStatusMixin:
    def _append_audit_event(self, payload: dict[str, Any]) -> None:
        audit_path = Path(self.engine.config.trade_reconciler_audit_log)
        event = dict(payload)
        event["ts"] = datetime.now(timezone.utc).isoformat()
        mode = str(getattr(self.engine.config, "trade_mode", "paper") or "paper").strip().lower()
        capabilities = resolve_mode_capabilities(mode)
        event.setdefault("mode", mode)
        event.setdefault("account_mode_hint", capabilities.account_mode_hint)
        try:
            get_audit_logger().register_stream("trade_reconciler", audit_path)
            get_audit_logger().append(
                stream="trade_reconciler",
                payload=event,
                path=audit_path,
                mode=mode,
                actor_id="trade_reconciler",
                severity="info",
                fail_closed_real=mode == "real",
            )
        except Exception:
            logger.exception("TradeReconciler failed to append reconciliation audit event")

        audit_service = getattr(self.engine, "audit_log_service", None)
        if audit_service is not None and hasattr(audit_service, "log_decision"):
            decision_payload = {
                "timestamp": event.get("ts"),
                "stage": "reconciliation",
                "final_decision": "reconciled",
                "reason": str(event.get("event", "reconciliation_event")),
                "mode": mode,
                "symbol": str(event.get("symbol", self.engine.config.instrument)),
                "probability": 0.0,
                "expected_value": float(event.get("pnl", 0.0) or 0.0),
                "agents_involved": [{"agent_id": "trade_reconciler", "confidence": 1.0}],
                "var_impact": {},
                "monte_carlo": {},
                "reconciliation": event,
            }
            try:
                audit_service.log_decision(decision_payload, is_real_mode=mode == "real")
            except Exception:
                logger.exception("TradeReconciler failed to mirror reconciliation decision to audit log")

    def _update_status(self, **updates: Any) -> None:
        status = dict(getattr(self.engine, "trade_reconciler_status", {}) or {})
        status.setdefault("method", self.engine.config.reconciliation_method)
        status.setdefault("connection_state", "idle")
        status.setdefault("status", "ready")
        status.setdefault("last_error", None)
        status.setdefault("last_message_ts", None)
        status.setdefault("pending_count", 0)
        status.setdefault("pending_symbols", [])
        status.update({key: value for key, value in updates.items() if value is not None or key == "last_error"})
        pending = self._get_pending_closes()
        status["pending_count"] = len(pending)
        status["pending_symbols"] = sorted({item.symbol for item in pending})
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.engine.trade_reconciler_status = status

        status_path = Path(self.engine.config.trade_reconciler_status_file)
        try:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.exception("TradeReconciler failed to persist status file")
