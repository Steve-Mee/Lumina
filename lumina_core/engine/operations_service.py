from __future__ import annotations

import json
import logging
import os
import queue
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from .broker_bridge import AccountInfo, Order
from .lumina_engine import LuminaEngine
from .valuation_engine import ValuationEngine
from lumina_core.order_gatekeeper import enforce_pre_trade_gate

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

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def _broker(self):
        broker = getattr(self.container, "broker", None)
        if broker is None:
            raise RuntimeError("BrokerBridge is not configured on the container")
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
                    if event.get("impact") in ["high", "3"] or event.get("event", "").lower() in ["fomc", "nfp", "cpi", "ppi"]
                ]
                sentiment = "neutral"
                if any("rate" in event.get("event", "").lower() or "fomc" in event.get("event", "").lower() for event in high_impact):
                    sentiment = "bullish" if len([event for event in high_impact if "cut" in str(event).lower()]) > 0 else "bearish"
                return {"events": high_impact[:4], "overall_sentiment": sentiment, "impact": "high" if high_impact else "medium"}
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
            print(f"🔊 SPEAKING: {clean_text[:140]}...")
            app.tts_engine.say(clean_text)
            app.tts_engine.runAndWait()
        except Exception as exc:
            app.logger.error(f"TTS_ERROR: {exc}")

    def fetch_account_balance(self) -> bool:
        app = self._app()
        try:
            account: AccountInfo = self._broker().get_account_info()
            self.engine.account_balance = float(account.balance)
            self.engine.account_equity = float(account.equity)
            self.engine.realized_pnl_today = float(account.realized_pnl_today)
            print(
                f"💰 ACCOUNT [{self.engine.config.trade_mode.upper()}] -> "
                f"Equity ${self.engine.account_equity:,.0f} | Realized PnL ${self.engine.realized_pnl_today:,.0f}"
            )
            return True
        except Exception as exc:
            app.logger.error(f"Balance fetch error: {exc}")
        return False

    def place_order(self, action: str, qty: int) -> bool:
        """Submit a trade order.

        Mode semantics:
          paper  – no broker call; returns False immediately (fills tracked externally).
          sim    – live broker connection with unlimited sim funds; skips calendar/session
                   guards; HardRiskController runs in advisory mode (enforce_rules=False).
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
        if not _risk_ok:
            app.logger.warning(f"place_order blocked by gatekeeper: {_risk_reason}")
            return False

        try:
            dream_snapshot = self.engine.get_current_dream_snapshot()
            result = self.container.broker.submit_order(
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
                except Exception:
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

                print(f"✅ {trade_mode.upper()} ORDER -> {action} {qty}x @ MARKET")
                app.logger.info(
                    f"{trade_mode.upper()}_ORDER_SUCCESS,action={action},qty={qty},"
                    f"expected_fill={expected_fill:.4f},est_latency_ms={est_latency_ms:.1f}"
                )
                return True
            app.logger.error(f"Order failed {result.status} ({result.message})")
            return False
        except Exception as exc:
            app.logger.error(f"Place order error: {exc}")
            return False

    def emergency_stop(self) -> None:
        """Gracefully stop the bot with proper cleanup."""
        app = self._app()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 EMERGENCY STOP – bot wordt afgesloten")
        try:
            live_chart_window = getattr(app, "live_chart_window", None)
            if live_chart_window is not None:
                try:
                    live_chart_window.after(0, live_chart_window.destroy)
                except Exception:
                    live_chart_window.destroy()
        except Exception as exc:
            app.logger.warning(f"Emergency stop window close warning: {exc}")

        self.engine.save_state()
        
        # Clean shutdown via SIGTERM signal (replaces os._exit(0))
        logger.info("Sending SIGTERM for graceful shutdown")
        os.kill(os.getpid(), signal.SIGTERM)

    def is_market_open(self) -> bool:
        now = datetime.now()
        return 13 <= now.hour <= 21

    def run_forever_loop(self) -> None:
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n🛑 Graceful shutdown gestart...")
            self.engine.save_state()
            print("✅ Alle data veilig opgeslagen.")
        except SystemExit:
            self.engine.save_state()
