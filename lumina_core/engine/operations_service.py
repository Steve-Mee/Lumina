from __future__ import annotations

import json
import logging
import os
import queue
import signal
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from .broker_bridge import AccountInfo, Order
from .errors import BrokerBridgeError, ErrorSeverity, LuminaError, format_error_code, log_structured
from .lumina_engine import LuminaEngine
from .policy_engine import PolicyEngine
from .valuation_engine import ValuationEngine
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.logging_utils import log_event

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OperationsService:
    """Owns remaining runtime helper operations that should not route through legacy wrappers."""

    engine: LuminaEngine
    container: Any | None = None
    thought_queue: queue.Queue = field(default_factory=queue.Queue)
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("OperationsService requires a LuminaEngine")
        self.valuation_engine.load_calibration_file("state/validation/fill_calibration.json")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _broker(self):
        broker = getattr(self.container, "broker", None)
        if broker is None:
            raise BrokerBridgeError("BrokerBridge is not configured on the container")
        return broker

    def thought_logger_thread(self) -> None:
        app = self._app()
        while True:
            try:
                entry = self.thought_queue.get()
                self.engine.config.thought_log.parent.mkdir(parents=True, exist_ok=True)
                with self.engine.config.thought_log.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self.thought_queue.task_done()
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="OPS_THOUGHT_LOG_001",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                app.logger.error(f"Thought log error: {exc}")

    def log_thought(self, data: dict[str, Any]) -> None:
        payload = dict(data)
        payload["timestamp"] = datetime.now().isoformat()
        self.thought_queue.put(payload)

    def detect_swing_and_fibs(self) -> tuple[float, float, dict[str, float]]:
        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 50:
                return 0.0, 0.0, {}
            recent = self.engine.ohlc_1min.iloc[-60:]

        swing_low = float(recent["low"].min())
        swing_high = float(recent["high"].max())
        diff = swing_high - swing_low
        fib_levels: dict[str, float] = {}
        for ratio in [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]:
            fib_levels[str(ratio)] = round(swing_high - diff * ratio, 2)
        return swing_high, swing_low, fib_levels

    def get_mtf_snapshots(self) -> str:
        timeframes = self.engine.config.timeframes
        with self.engine.live_data_lock:
            if len(self.engine.ohlc_1min) < 60:
                return "PARTIAL_DATA_ONLY"
            df = self.engine.ohlc_1min.copy()

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        snapshots: dict[str, Any] = {}
        for tf_name, seconds in timeframes.items():
            resampled = (
                df.set_index("timestamp")
                .resample(f"{seconds // 60}min")
                .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                .dropna()
            )
            if len(resampled) > 0:
                row = resampled.iloc[-1]
                snapshots[tf_name] = {
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                }
            else:
                snapshots[tf_name] = {"open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0}
        return json.dumps(snapshots, ensure_ascii=False)

    def get_high_impact_news(self) -> dict[str, Any]:
        app = self._app()
        api_key = self.engine.config.finnhub_api_key
        if not api_key:
            return {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

        try:
            today = datetime.now().strftime("%Y-%m-%d")
            response = requests.get(
                f"https://finnhub.io/api/v1/calendar/economic?from={today}&to={today}",
                headers={"X-Finnhub-Token": api_key},
                timeout=15,
            )
            if response.status_code == 200:
                events = response.json().get("economicCalendar", [])
                high_impact = [
                    event
                    for event in events
                    if event.get("impact") in ["high", "3"]
                    or event.get("event", "").lower() in ["fomc", "nfp", "cpi", "ppi"]
                ]
                sentiment = "neutral"
                if any(
                    "rate" in event.get("event", "").lower() or "fomc" in event.get("event", "").lower()
                    for event in high_impact
                ):
                    sentiment = (
                        "bullish"
                        if len([event for event in high_impact if "cut" in str(event).lower()]) > 0
                        else "bearish"
                    )
                return {
                    "events": high_impact[:4],
                    "overall_sentiment": sentiment,
                    "impact": "high" if high_impact else "medium",
                }
        except requests.RequestException as exc:
            app.logger.error(f"Finnhub request error: {exc}")
        except (ValueError, TypeError) as exc:
            app.logger.error(f"Finnhub parse error: {exc}")
        return {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

    def speak(self, text: str) -> None:
        app = self._app()
        if not bool(getattr(app, "VOICE_ENABLED", False)) or not getattr(app, "tts_engine", None):
            return
        try:
            clean_text = text.replace("...", ". ").replace(" – ", ", ")
            log_event(app.logger, "ops.speak", preview=clean_text[:140])
            app.tts_engine.say(clean_text)
            app.tts_engine.runAndWait()
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="OPS_TTS_002",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            app.logger.error(f"TTS_ERROR: {exc}")

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
        )

        session_allowed = True
        if str(_risk_reason).startswith("Session guard blocked"):
            session_allowed = False
        policy_engine = PolicyEngine(engine=self.engine, broker=self.container.broker)
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
            result = policy_engine.execute_order(
                Order(
                    symbol=str(self.engine.config.instrument),
                    side=str(action).upper(),
                    quantity=int(qty),
                    order_type="MARKET",
                    stop_loss=float(dream_snapshot.get("stop", 0) or 0),
                    take_profit=float(dream_snapshot.get("target", 0) or 0),
                )
            )
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
                expected_fill = self.valuation_engine.apply_entry_fill(
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
                self.engine.live_position_qty = int(signed_qty)
                self.engine.last_entry_price = float(expected_fill)
                self.engine.live_trade_signal = action.upper()
                self.engine.last_realized_pnl_snapshot = float(self.engine.realized_pnl_today)

                log_event(
                    app.logger,
                    "ops.order_success",
                    mode=trade_mode.upper(),
                    action=str(action).upper(),
                    qty=int(qty),
                    expected_fill=round(expected_fill, 4),
                    est_latency_ms=round(est_latency_ms, 1),
                )
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
        log_event(app.logger, "ops.emergency_stop", ts=datetime.now().strftime("%H:%M:%S"))
        try:
            live_chart_window = getattr(app, "live_chart_window", None)
            if live_chart_window is not None:
                try:
                    live_chart_window.after(0, live_chart_window.destroy)
                except Exception as _exc:
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

    def is_market_open(self) -> bool:
        session_guard = getattr(self.engine, "session_guard", None)
        if session_guard is None:
            self._app().logger.warning("OPS_MARKET_OPEN_FAIL_CLOSED,error_code=SESSION_GUARD_UNAVAILABLE")
            return False
        try:
            return bool(session_guard.is_trading_session())
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="OPS_SESSION_GUARD_006",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            self._app().logger.warning(
                "OPS_MARKET_OPEN_FAIL_CLOSED,error_code=SESSION_GUARD_ERROR,detail=%s",
                exc,
            )
            return False

    def run_forever_loop(self) -> None:
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="\n🛑 Graceful shutdown gestart...",
                    context={},
                )
            )
            self.engine.save_state()
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="\u2705 Alle data veilig opgeslagen.",
                    context={},
                )
            )
        except SystemExit:
            self.engine.save_state()
