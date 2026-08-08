"""Order / emergency / balance ops (M5 extract)."""
from __future__ import annotations

import logging
import os
import signal
import traceback
from datetime import datetime, timezone

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Order
from lumina_core.engine.errors import ErrorSeverity, LuminaError, format_error_code, log_structured
from lumina_core.logging_utils import get_logger, log_event, log_runtime_trace, runtime_trace_enabled
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.risk.policy_engine import PolicyEngine

logger = get_logger("lumina.engine.operations")


class OperationsOrdersMixin:
    def fetch_account_balance(self) -> bool:
        app = self._app()
        try:
            account: AccountInfo = self._broker().get_account_info()
            self.engine.account_balance = float(account.balance)
            self.engine.account_equity = float(account.equity)
            self.engine.realized_pnl_today = float(account.realized_pnl_today)
            log_event(
                app.logger,
                "ops.account_balance",
                mode=self.engine.config.trade_mode.upper(),
                equity=round(self.engine.account_equity, 2),
                realized_pnl=round(self.engine.realized_pnl_today, 2),
            )
            return True
        except Exception as exc:
            code = format_error_code("OPS_BALANCE", exc, fallback="FETCH_FAILED")
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code=code,
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"Balance fetch error [{code}]: {exc}")
        return False

    def place_order(self, action: str, qty: int) -> bool:
        """Submit a trade order.

        Mode semantics:
          paper  – no broker call; returns False immediately (fills tracked externally).
          sim    – live broker connection with unlimited sim funds; skips calendar/session
                   guards; HardRiskController runs in advisory mode (enforce_rules=False).
                    sim_real_guard – live broker connection on sim-account with REAL-equivalent
                                     session + risk enforcement for production-parity validation.
          real   – real money; full SessionGuard + HardRiskController enforcement.
        """
        app = self._app()
        trade_mode = self.engine.config.trade_mode

        # Paper mode: no broker submission — tracked internally by supervisor_loop.
        if trade_mode == "paper":
            if runtime_trace_enabled():
                log_runtime_trace(
                    app.logger,
                    "ops.place_order_skipped",
                    reason="paper_orders_via_supervisor_internal_sim",
                    action=str(action),
                    qty=int(qty),
                )
            return False

        _dream = self.engine.get_current_dream_snapshot()
        with self.engine.live_data_lock:
            _price = float(
                self.engine.live_quotes[-1]["last"]
                if self.engine.live_quotes
                else (self.engine.ohlc_1min["close"].iloc[-1] if len(self.engine.ohlc_1min) else 0.0)
            )
        _stop = float(_dream.get("stop", _price * 0.99 if action.upper() == "BUY" else _price * 1.01))
        _proposed_risk = abs(_price - _stop)
        _risk_ok, _risk_reason = enforce_pre_trade_gate(
            self.engine,
            symbol=str(self.engine.config.instrument),
            regime=str(_dream.get("regime", "NEUTRAL")),
            proposed_risk=float(_proposed_risk),
            order_side=str(action).upper(),
        )

        session_allowed = True
        if str(_risk_reason).startswith("Session guard blocked"):
            session_allowed = False
        broker = getattr(self.container, "broker", None) if self.container is not None else None
        policy_engine = PolicyEngine(engine=self.engine, broker=broker)
        gateway_result = policy_engine.evaluate_proposal(
            signal=str(action).upper(),
            confluence_score=float(_dream.get("confluence_score", 1.0) or 1.0),
            min_confluence=float(getattr(self.engine.config, "min_confluence", 0.0) or 0.0),
            hold_until_ts=float(_dream.get("hold_until_ts", 0.0) or 0.0),
            mode=str(trade_mode).strip().lower(),
            session_allowed=bool(session_allowed),
            risk_allowed=bool(_risk_ok),
            lineage={
                "model_identifier": str(_dream.get("chosen_strategy", "operations-service")),
                "prompt_version": "operations-service-v1",
                "prompt_hash": "operations-service",
                "policy_version": "agent-policy-gateway-v1",
                "provider_route": [
                    str(getattr(getattr(self.engine, "local_engine", None), "active_provider", "unknown-provider"))
                ],
                "calibration_factor": 1.0,
            },
        )
        if str(gateway_result.get("signal", "HOLD")) == "HOLD" and str(action).upper() in {"BUY", "SELL"}:
            app.logger.warning(
                "place_order blocked by AgentPolicyGateway [mode=%s]: %s",
                str(trade_mode).upper(),
                gateway_result.get("reason"),
            )
            return False

        if not _risk_ok:
            app.logger.warning(f"place_order blocked by gatekeeper [mode={str(trade_mode).upper()}]: {_risk_reason}")
            return False

        try:
            dream_snapshot = self.engine.get_current_dream_snapshot()
            order = Order(
                symbol=str(self.engine.config.instrument),
                side=str(action).upper(),
                quantity=int(qty),
                order_type="MARKET",
                stop_loss=float(dream_snapshot.get("stop", 0) or 0),
                take_profit=float(dream_snapshot.get("target", 0) or 0),
                metadata={
                    "reference_price": float(_price),
                    "proposed_risk": float(_proposed_risk),
                    "regime": str(dream_snapshot.get("regime", "NEUTRAL")),
                    "confluence_score": float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
                    "reason": str(dream_snapshot.get("reason", "") or ""),
                },
            )
            # Phase 1.3.2: B-001 hard removal complete. Parameter no longer exists.
            result = policy_engine.execute_order(order)
            if result.accepted:
                current_price = 0.0
                try:
                    with self.engine.live_data_lock:
                        current_price = float(
                            self.engine.live_quotes[-1]["last"]
                            if self.engine.live_quotes
                            else (self.engine.ohlc_1min["close"].iloc[-1] if len(self.engine.ohlc_1min) else 0.0)
                        )
                except Exception as _exc:
                    logging.exception(
                        "Unhandled broad exception fallback in lumina_core/engine/operations_service.py:315"
                    )
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                        code="OPS_PRICE_READ_003",
                        message=str(_exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    current_price = 0.0

                signed_qty = qty if action.upper() == "BUY" else -qty
                side = 1 if action.upper() == "BUY" else -1
                est_slip_ticks = self.valuation_engine.slippage_ticks(
                    volume=1.0,
                    avg_volume=1.0,
                    regime=str(self.engine.get_current_dream_snapshot().get("regime", "NEUTRAL")),
                    slippage_scale=1.0,
                )
                hypothetical_fill_obs = self.valuation_engine.apply_entry_fill(
                    symbol=self.engine.config.instrument,
                    price=float(current_price),
                    side=side,
                    slippage_ticks=est_slip_ticks,
                )
                est_latency_ms = self.valuation_engine.estimate_fill_latency_ms(
                    volume=1.0,
                    avg_volume=1.0,
                    pending_age=1,
                    regime=str(self.engine.get_current_dream_snapshot().get("regime", "NEUTRAL")),
                )
                fill_px = float(getattr(result, "fill_price", 0.0) or 0.0)
                fill_qty = int(getattr(result, "filled_qty", 0) or 0)
                brk = broker
                if fill_px <= 0.0:
                    lf_fn = getattr(brk, "last_fill_for_symbol", None)
                    lf = lf_fn(str(self.engine.config.instrument)) if callable(lf_fn) else None
                    if lf is not None:
                        fill_px = float(lf.price)
                        fill_qty = max(fill_qty, int(lf.quantity))
                # D2 sub-slice 8: thin delegation to LivePositionManager (shared live state).
                from lumina_core.engine.live_position_manager import LivePositionManager
                LivePositionManager(app=self, engine=self.engine).update_on_real_fill(
                    signed_qty=int(signed_qty),
                    fill_px=float(fill_px) if fill_px > 0.0 else 0.0,
                    action=action,
                    last_realized=float(self.engine.realized_pnl_today),
                )

                log_event(
                    app.logger,
                    "ops.order_success",
                    mode=trade_mode.upper(),
                    action=str(action).upper(),
                    qty=int(qty),
                    broker_fill_price=round(fill_px, 4) if fill_px > 0.0 else None,
                    filled_qty_reported=int(fill_qty),
                    hypothetical_fill_observability=round(float(hypothetical_fill_obs), 4),
                    est_latency_ms=round(est_latency_ms, 1),
                )
                try:
                    from lumina_core.maturity.milestone_hooks import try_record_milestone

                    workspace = getattr(self.engine.config, "workspace_root", None) or getattr(
                        self.app, "workspace_root", None
                    )
                    if workspace and str(trade_mode).lower() in {"sim", "sim_real_guard"}:
                        try_record_milestone(
                            workspace,
                            "first_sim_order_placed",
                            metadata={"action": action, "qty": int(qty), "mode": trade_mode},
                        )
                        try_record_milestone(
                            workspace,
                            "sim_mirror_api_ok",
                            metadata={"broker": type(brk).__name__},
                        )
                except Exception:
                    pass
                return True
            app.logger.error(f"Order failed {result.status} ({result.message})")
            return False
        except Exception as exc:
            code = format_error_code("OPS_PLACE_ORDER", exc, fallback="SUBMIT_FAILED")
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code=code,
                message=str(exc),
                context={"traceback": traceback.format_exc(), "mode": str(trade_mode)},
            )
            log_structured(err)
            app.logger.error(f"Place order error [{code}]: {exc}")
            return False

    def emergency_stop(self) -> None:
        """Gracefully stop the bot with proper cleanup."""
        app = self._app()
        log_event(
            app.logger,
            "ops.emergency_stop",
            ts=datetime.now().strftime("%H:%M:%S"),
            ts_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        try:
            live_chart_window = getattr(app, "live_chart_window", None)
            if live_chart_window is not None:
                try:
                    live_chart_window.after(0, live_chart_window.destroy)
                except Exception as _exc:
                    logging.exception(
                        "Unhandled broad exception fallback in lumina_core/engine/operations_service.py:383"
                    )
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="OPS_WINDOW_CLOSE_004",
                        message=str(_exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    live_chart_window.destroy()
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="OPS_EMERGENCY_STOP_005",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.warning(f"Emergency stop window close warning: {exc}")

        self.engine.save_state()

        # Clean shutdown via SIGTERM signal (replaces os._exit(0))
        logger.info("Sending SIGTERM for graceful shutdown")
        os.kill(os.getpid(), signal.SIGTERM)

