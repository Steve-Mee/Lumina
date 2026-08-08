"""LifecycleMixin methods for TradeReconciler."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.engine.trade_reconciler.schemas import PendingTradeClose

logger = logging.getLogger(__name__)


class LifecycleMixin:
    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("TradeReconciler requires a LuminaEngine")
        pending = []
        for item in getattr(self.engine, "pending_trade_reconciliations", []):
            if isinstance(item, dict):
                try:
                    pending.append(PendingTradeClose.from_dict(item))
                except Exception:
                    logging.exception("Unhandled broad exception fallback in lumina_core/engine/trade_reconciler.py:92")
                    continue
        self._set_pending_closes(pending)
        self._update_status(connection_state="idle", status="ready")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _get_pending_closes(self) -> list[PendingTradeClose]:
        return [
            PendingTradeClose.from_dict(item)
            for item in getattr(self.engine, "pending_trade_reconciliations", [])
            if isinstance(item, dict)
        ]

    def _set_pending_closes(self, items: list[PendingTradeClose]) -> None:
        self.engine.pending_trade_reconciliations = [item.to_dict() for item in items]

    def stop(self) -> None:
        self.stop_requested = True
        self._update_status(connection_state="stopped", status="stopped")

    def start(self) -> None:
        mode = str(self.engine.config.trade_mode or "paper").strip().lower()
        capabilities = resolve_mode_capabilities(mode)
        if not capabilities.reconcile_fills_enabled_default:
            self._update_status(connection_state="disabled", status="skipped_non_real")
            return
        if not bool(self.engine.config.reconcile_fills):
            # T4: capital-risk modes must not silently run without fill recon.
            from lumina_core.engine.trade_reconciler.real_recon_gate import (
                evaluate_real_broker_recon_gate,
            )

            gate = evaluate_real_broker_recon_gate(
                trade_mode=mode,
                reconcile_fills=False,
                reconciliation_method=getattr(
                    self.engine.config, "reconciliation_method", "websocket"
                ),
                reconciliation_timeout_seconds=getattr(
                    self.engine.config, "reconciliation_timeout_seconds", 15.0
                ),
            )
            if gate.get("recon_required") and not gate.get("ok"):
                logger.error(
                    "trade_reconciler.fail_closed_real_recon_disabled mode=%s failures=%s",
                    mode,
                    gate.get("failures"),
                )
                self._update_status(
                    connection_state="error",
                    status="fail_closed_recon_required",
                    last_error=str(gate.get("message") or "reconcile_fills required"),
                )
                return
            self._update_status(connection_state="disabled", status="disabled")
            return

        method = str(self.engine.config.reconciliation_method or "websocket").lower()
        if method == "polling":
            self._run_polling_loop()
            return
        self._run_websocket_loop()

    def mark_closing(
        self,
        *,
        symbol: str,
        signal: str,
        entry_price: float,
        detected_exit_price: float,
        quantity: int,
        expected_pnl: float,
        reflection: dict[str, Any] | None = None,
        chart_base64: str | None = None,
        detected_ts: datetime | None = None,
        # Phase 2 Slice 25: optional lineage for multi-leg netting hash chain
        decision_context_id: str | None = None,
        prev_hash: str | None = None,
    ) -> str:
        detected_at = detected_ts or datetime.now(timezone.utc)
        expected_close_side = "SELL" if str(signal).upper() == "BUY" else "BUY"
        reconciliation_id = f"{symbol}-{int(detected_at.timestamp() * 1000)}-{abs(int(quantity))}"
        pending = PendingTradeClose(
            reconciliation_id=reconciliation_id,
            symbol=str(symbol).strip().upper(),
            mode=self.engine.config.trade_mode,
            signal=str(signal).upper(),
            quantity=int(abs(quantity)),
            entry_price=float(entry_price),
            detected_exit_price=float(detected_exit_price),
            expected_pnl=float(expected_pnl),
            detected_ts=detected_at,
            reflection=dict(reflection or {}),
            chart_base64=chart_base64,
            expected_close_side=expected_close_side,
            # Phase 2 Slice 25: carry lineage for multi-leg netting hash chain
            decision_context_id=decision_context_id,
            prev_hash=prev_hash,
        )
        items = [
            item for item in self._get_pending_closes() if item.symbol != pending.symbol or item.status != "closing"
        ]
        items.append(pending)
        self._set_pending_closes(items)
        app = self._app()
        app.logger.info(
            "FILL_RECONCILE_PENDING,"
            f"id={reconciliation_id},symbol={pending.symbol},qty={pending.quantity},"
            f"snapshot_exit={pending.detected_exit_price:.2f},expected_pnl={pending.expected_pnl:.2f}"
        )
        self._append_audit_event(
            {
                "event": "pending_close",
                "reconciliation_id": reconciliation_id,
                "symbol": pending.symbol,
                "signal": pending.signal,
                "qty": pending.quantity,
                "entry_price": pending.entry_price,
                "detected_exit_price": pending.detected_exit_price,
                "expected_pnl": pending.expected_pnl,
                "detected_ts": pending.detected_ts.isoformat(),
            }
        )
        self._update_status(status="pending_close")
        self._try_match_recent_fills()
        return reconciliation_id
