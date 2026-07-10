"""FinalizeMixin methods for TradeReconciler."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from lumina_core.engine.economic_pnl_service import EconomicPnLService
from lumina_core.engine.errors import format_error_code
from lumina_core.engine.trade_reconciler.schemas import FillEvent, PendingTradeClose

logger = logging.getLogger(__name__)


class FinalizeMixin:
    def _finalize_pending_close_observability_only(self, pending: PendingTradeClose, *, status: str) -> None:
        """Timeout or other path with no broker fill: audit only — no economic PnL or external trade publish."""
        app = self._app()
        app.logger.warning(
            "FILL_RECONCILE_OBSERVABILITY,"
            f"id={pending.reconciliation_id},symbol={pending.symbol},status={status},"
            "reason=no_broker_confirmed_fill_economic_ledger_not_updated"
        )
        self._append_audit_event(
            {
                "event": "reconciliation_no_broker_fill",
                "reconciliation_id": pending.reconciliation_id,
                "symbol": pending.symbol,
                "status": status,
                "expected_pnl_non_authoritative": float(pending.expected_pnl),
                "detected_exit_price": float(pending.detected_exit_price),
                "entry_price": float(pending.entry_price),
                "quantity": int(pending.quantity),
                "note": "Pending snapshot fields are observability only; no league push without fill.",
            }
        )
        self._update_status(
            status="timeout_awaiting_broker_fill",
            last_reconciled_trade={
                "symbol": pending.symbol,
                "status": status,
                "economic_ledger_applied": False,
            },
        )

    def _finalize_pending_close(self, pending: PendingTradeClose, fill: FillEvent | None, status: str) -> None:
        if fill is None:
            self._finalize_pending_close_observability_only(pending, status=status)
            return

        app = self._app()
        final_exit = float(fill.price)
        fill_qty = int(getattr(fill, "quantity", 0) or 0)
        quantity = fill_qty if fill_qty > 0 else int(pending.quantity)
        commission = float(fill.commission)
        symbol = str(pending.symbol or self.engine.config.instrument)

        # Phase 2 Slice 24/25: Best-effort lineage from the (aggregate) exit fill or pending (for multi-leg).
        # first-class fields preferred, raw fallback. This allows the hash chain to continue
        # through multi-leg netting for the same decision_context_id.
        dcid = getattr(fill, "decision_context_id", None) or pending.decision_context_id
        ph = getattr(fill, "prev_hash", None) or pending.prev_hash
        if not dcid and isinstance(getattr(fill, "raw", None), dict):
            dcid = fill.raw.get("decision_context_id")
        if not ph and isinstance(getattr(fill, "raw", None), dict):
            ph = fill.raw.get("prev_hash")

        ledger = EconomicPnLService(self.valuation_engine).realized_close_from_broker_fill(
            symbol=symbol,
            entry_price=float(pending.entry_price),
            exit_fill_price=final_exit,
            position_signal=str(pending.signal),
            quantity=quantity,
            exit_commission=commission,
            reference_price_for_slippage_ticks=float(pending.detected_exit_price),
            decision_context_id=dcid,
            prev_hash=ph,
        )
        final_pnl = float(ledger.realized_net)
        slippage_points = float(ledger.slippage_points_vs_reference)
        observed_latency_ms = max(0.0, (datetime.now(timezone.utc) - pending.detected_ts).total_seconds() * 1000.0)
        est_latency_ms = self.valuation_engine.estimate_fill_latency_ms(
            volume=max(1.0, float(quantity)),
            avg_volume=max(1.0, float(quantity)),
            pending_age=1,
            regime=str(pending.reflection.get("regime", "NEUTRAL"))
            if isinstance(pending.reflection, dict)
            else "NEUTRAL",
        )
        fill_latency_ms = max(observed_latency_ms, est_latency_ms)

        reconciliation_meta = {
            "status": status,
            "broker_fill_id": fill.fill_id,
            "commission": round(commission, 4),
            "slippage_points": round(slippage_points, 4),
            "fill_latency_ms": round(fill_latency_ms, 2),
            "economic_ledger_source": "broker_confirmed_fill",
            "detected_exit_price": round(float(pending.detected_exit_price), 4),
            "final_exit_price": round(float(final_exit), 4),
        }
        reflection_payload = dict(pending.reflection)
        reflection_payload["reconciliation"] = reconciliation_meta

        push_fn = getattr(app, "push_traderleague_trade", None)
        if callable(push_fn):
            push_fn(
                mode=pending.mode,
                symbol=pending.symbol,
                signal=pending.signal,
                entry_price=float(pending.entry_price),
                exit_price=float(final_exit),
                qty=int(quantity),
                pnl_dollars=float(final_pnl),
                reflection=reflection_payload,
                chart_base64=pending.chart_base64,
                broker_fill_id=reconciliation_meta["broker_fill_id"],
                commission=float(commission),
                slippage_points=float(slippage_points),
                fill_latency_ms=float(fill_latency_ms),
                reconciliation_status=status,
            )

        publish_fn = getattr(app, "publish_traderleague_trade_close", None)
        if callable(publish_fn):
            try:
                summary = (
                    f"reconciliation={status}; slippage_points={slippage_points:.4f}; "
                    f"fill_latency_ms={fill_latency_ms:.0f}; commission={commission:.2f}"
                )
                publish_fn(
                    symbol=pending.symbol,
                    entry_price=float(pending.entry_price),
                    exit_price=float(final_exit),
                    quantity=int(quantity),
                    pnl=float(final_pnl),
                    reflection=summary,
                    chart_snapshot_url=str(pending.reflection.get("chart_snapshot_url", "") or ""),
                    broker_fill_id=reconciliation_meta["broker_fill_id"],
                    commission=float(commission),
                    slippage_points=float(slippage_points),
                    fill_latency_ms=float(fill_latency_ms),
                    reconciliation_status=status,
                )
            except Exception as exc:
                code = format_error_code("RECONCILE_PUBLISH", exc, fallback="PUBLISH_FAILED")
                app.logger.error(f"TradeReconciler final publish error [{code}]: {exc}")

        app.logger.info(
            "FILL_RECONCILED,"
            f"id={pending.reconciliation_id},symbol={pending.symbol},status={status},"
            f"exit={final_exit:.2f},snapshot_exit={pending.detected_exit_price:.2f},"
            f"slippage={slippage_points:.4f},commission={commission:.2f},latency_ms={fill_latency_ms:.0f},"
            f"pnl={final_pnl:.2f}"
        )
        obs = getattr(self.engine, "observability_service", None)
        if obs is not None and hasattr(obs, "record_regime_performance"):
            try:
                regime = str((pending.reflection or {}).get("regime", "NEUTRAL"))
                obs.record_regime_performance(regime=regime, pnl=float(final_pnl), won=float(final_pnl) > 0.0)
            except Exception:
                logger.exception("TradeReconciler failed to record regime performance metric")
        if (
            str(pending.mode).strip().lower() == "sim_real_guard"
            and obs is not None
            and hasattr(obs, "record_mode_parity_drift")
        ):
            try:
                obs.record_mode_parity_drift(
                    baseline="real",
                    candidate="sim_real_guard",
                    delta=float(abs(slippage_points)),
                )
            except Exception:
                logger.exception("TradeReconciler failed to record mode parity drift metric")
        log_thought = getattr(app, "log_thought", None)
        if callable(log_thought):
            log_thought(
                {
                    "type": "trade_fill_reconciled",
                    "symbol": pending.symbol,
                    "status": status,
                    "entry_price": float(pending.entry_price),
                    "detected_exit_price": float(pending.detected_exit_price),
                    "final_exit_price": float(final_exit),
                    "pnl": float(final_pnl),
                    "commission": float(commission),
                    "slippage_points": float(slippage_points),
                    "fill_latency_ms": float(fill_latency_ms),
                }
            )
        self._update_status(
            status="reconciled",
            last_reconciled_trade={
                "symbol": pending.symbol,
                "status": status,
                "broker_fill_id": reconciliation_meta["broker_fill_id"],
                "final_exit_price": float(final_exit),
                "pnl": float(final_pnl),
            },
        )
        self._append_audit_event(
            {
                "event": "reconciled",
                "reconciliation_id": pending.reconciliation_id,
                "symbol": pending.symbol,
                "status": status,
                "broker_fill_id": reconciliation_meta["broker_fill_id"],
                "entry_price": float(pending.entry_price),
                "detected_exit_price": float(pending.detected_exit_price),
                "final_exit_price": float(final_exit),
                "quantity": int(quantity),
                "pnl": float(final_pnl),
                "commission": float(commission),
                "slippage_points": float(slippage_points),
                "fill_latency_ms": float(fill_latency_ms),
            }
        )
