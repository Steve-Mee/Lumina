from __future__ import annotations

import json
import os
import queue
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class OperationsService:
    """Owns remaining runtime helper operations that should not route through legacy wrappers."""

    engine: LuminaEngine
    thought_queue: queue.Queue = field(default_factory=queue.Queue)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("OperationsService requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

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
            response = requests.get(
                f"https://app.crosstrade.io/v1/api/accounts/{self.engine.config.crosstrade_account}",
                headers={"Authorization": f"Bearer {self.engine.config.crosstrade_token or ''}"},
                timeout=8,
            )
            if response.status_code == 200:
                data = response.json()
                self.engine.account_balance = float(data.get("balance", 50000))
                self.engine.account_equity = float(data.get("equity", self.engine.account_balance))
                self.engine.realized_pnl_today = float(data.get("realizedPnlToday", 0))
                print(
                    f"💰 ACCOUNT [{self.engine.config.trade_mode.upper()}] -> "
                    f"Equity ${self.engine.account_equity:,.0f} | Realized PnL ${self.engine.realized_pnl_today:,.0f}"
                )
                return True
        except Exception as exc:
            app.logger.error(f"Balance fetch error: {exc}")
        return False

    def place_order(self, action: str, qty: int) -> bool:
        app = self._app()
        trade_mode = self.engine.config.trade_mode
        if trade_mode == "paper":
            return False

        try:
            dream_snapshot = self.engine.get_current_dream_snapshot()
            payload = {
                "instrument": self.engine.config.instrument,
                "action": action.upper(),
                "orderType": "MARKET",
                "quantity": qty,
                "stopLoss": dream_snapshot.get("stop", 0),
                "takeProfit": dream_snapshot.get("target", 0),
            }
            response = requests.post(
                f"https://app.crosstrade.io/v1/api/accounts/{self.engine.config.crosstrade_account}/orders/place",
                headers={"Authorization": f"Bearer {self.engine.config.crosstrade_token or ''}"},
                json=payload,
                timeout=10,
            )
            if response.status_code in (200, 201):
                print(f"✅ {trade_mode.upper()} ORDER -> {action} {qty}x @ MARKET")
                app.logger.info(f"{trade_mode.upper()}_ORDER_SUCCESS,action={action},qty={qty}")
                return True
            app.logger.error(f"Order failed {response.status_code}")
            return False
        except Exception as exc:
            app.logger.error(f"Place order error: {exc}")
            return False

    def emergency_stop(self) -> None:
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
        os._exit(0)

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
