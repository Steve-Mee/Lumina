from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import requests
import websockets

from .tape_reading_agent import TapeReadingAgent
from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class MarketDataService:
    """Websocket and historical market-data ingestion backed by MarketDataManager."""

    engine: LuminaEngine
    tape_agent: TapeReadingAgent = field(default_factory=TapeReadingAgent)
    latency_sla_ms: float = 250.0
    latency_window: deque[float] = field(default_factory=lambda: deque(maxlen=50))
    _sla_breach_streak: int = 0
    _sla_recovery_streak: int = 0

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("MarketDataService requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    @staticmethod
    def _extract_numeric(payload: dict[str, Any], keys: tuple[str, ...], default: float = 0.0) -> float:
        for key in keys:
            value = payload.get(key)
            if key in payload and value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return float(default)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        return str(symbol).strip().upper()

    def _set_fast_path_only(self, enabled: bool, reason: str) -> None:
        app = self._app()
        current = bool(getattr(app, "FAST_PATH_ONLY", False))
        if current == enabled:
            return
        setattr(app, "FAST_PATH_ONLY", enabled)
        state = "enabled" if enabled else "disabled"
        app.logger.warning(f"FAST_PATH_ONLY {state} (market data): {reason}")

    def _record_latency(self, elapsed_ms: float, source: str) -> None:
        app = self._app()
        self.latency_window.append(float(elapsed_ms))

        if elapsed_ms > self.latency_sla_ms:
            self._sla_breach_streak += 1
            self._sla_recovery_streak = 0
            if self._sla_breach_streak >= 3:
                self._set_fast_path_only(
                    True,
                    f"{source} latency {elapsed_ms:.1f}ms above SLA {self.latency_sla_ms:.1f}ms",
                )
        else:
            self._sla_recovery_streak += 1
            self._sla_breach_streak = 0
            if self._sla_recovery_streak >= 5:
                self._set_fast_path_only(False, f"{source} latency recovered ({elapsed_ms:.1f}ms)")

        avg_latency = sum(self.latency_window) / max(1, len(self.latency_window))
        setattr(app, "MARKET_DATA_LATENCY_MS", round(avg_latency, 2))

    async def websocket_listener(self) -> None:
        app = self._app()
        last_tick_print = 0.0
        uri = "wss://app.crosstrade.io/ws/stream"
        headers = {"Authorization": f"Bearer {getattr(app, 'CROSSTRADE_TOKEN', self.engine.config.crosstrade_token or '')}"}
        instrument = self._normalize_symbol(getattr(app, "INSTRUMENT", self.engine.config.instrument))
        configured_swarm = [self._normalize_symbol(s) for s in getattr(app, "SWARM_SYMBOLS", self.engine.config.swarm_symbols)]
        if instrument not in configured_swarm:
            configured_swarm.insert(0, instrument)
        subscribed_symbols = [s for s in configured_swarm if s]
        try:
            async with websockets.connect(uri, additional_headers=headers, ping_interval=20, ping_timeout=20) as ws:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WS connected - 1-min candle builder active")
                await ws.send(json.dumps({"action": "subscribe", "instruments": subscribed_symbols}))

                async for message in ws:
                    tick_start = time.perf_counter()
                    try:
                        data = json.loads(message)
                        if data.get("type") != "marketData":
                            continue

                        for quote in data.get("quotes", []):
                            quote_symbol = self._normalize_symbol(str(quote.get("instrument", "")))
                            if quote_symbol not in subscribed_symbols:
                                continue

                            ts = datetime.now()
                            price = self._extract_numeric(quote, ("last", "lastPrice", "tradePrice"), 0.0)
                            bid = self._extract_numeric(quote, ("bid", "bidPrice", "bestBid"), price)
                            ask = self._extract_numeric(quote, ("ask", "askPrice", "bestAsk"), price)
                            vol_cum = int(self._extract_numeric(quote, ("volume", "totalVolume", "cumVolume"), 0.0))

                            swarm_manager = getattr(app, "swarm_manager", None)
                            if swarm_manager is not None and hasattr(swarm_manager, "process_quote_tick"):
                                swarm_manager.process_quote_tick(
                                    symbol=quote_symbol,
                                    ts=ts,
                                    price=price,
                                    bid=bid,
                                    ask=ask,
                                    volume_cumulative=vol_cum,
                                )

                            if quote_symbol != instrument:
                                continue

                            closed_candle = self.engine.market_data.process_quote_tick(
                                ts=ts,
                                price=price,
                                bid=bid,
                                ask=ask,
                                volume_cumulative=vol_cum,
                            )

                            tape_snapshot = self.engine.market_data.get_tape_snapshot()
                            tape_signal = self.tape_agent.score_momentum(tape_snapshot)
                            self.engine.market_data.last_tape_signal = tape_signal

                            if closed_candle is not None:
                                minute_start = ts.replace(second=0, microsecond=0)
                                print(
                                    f"[{minute_start.strftime('%H:%M')}] 1-min candle closed -> "
                                    f"O={closed_candle['open']:.2f} H={closed_candle['high']:.2f} "
                                    f"L={closed_candle['low']:.2f} C={closed_candle['close']:.2f} V={closed_candle['volume']}"
                                )

                            if time.time() - last_tick_print >= float(getattr(app, 'TICK_PRINT_INTERVAL_SEC', 2.0)):
                                tape_txt = (
                                    f"delta10={tape_signal.get('cumulative_delta_10', 0.0):.0f} "
                                    f"imb={tape_signal.get('bid_ask_imbalance', 1.0):.2f} "
                                    f"sig={tape_signal.get('signal', 'HOLD')}"
                                )
                                print(f"[{ts.strftime('%H:%M:%S')}] LIVE tick -> last={price:.2f} | {tape_txt}")
                                last_tick_print = time.time()
                        elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
                        self._record_latency(elapsed_ms, source="websocket")
                    except Exception as exc:
                        app.logger.error(f"WS parse error: {exc}")
        except Exception:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] WS failed -> REST fallback")

    def start_websocket(self) -> None:
        asyncio.run(self.websocket_listener())

    def fetch_quote(self) -> tuple[float, int]:
        app = self._app()
        account = getattr(app, "CROSSTRADE_ACCOUNT", self.engine.config.crosstrade_account)
        instrument = getattr(app, "INSTRUMENT", self.engine.config.instrument)
        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        request_start = time.perf_counter()
        try:
            response = requests.get(
                f"https://app.crosstrade.io/v1/api/accounts/{account}/quote?instrument={instrument}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8,
            )
            if response.status_code == 200:
                data = response.json()
                elapsed_ms = (time.perf_counter() - request_start) * 1000.0
                self._record_latency(elapsed_ms, source="fetch_quote")
                return float(data.get("last", 0)), int(data.get("volume", 0))
        except requests.RequestException as exc:
            app.logger.error(f"Fetch quote request error: {exc}")
        except (ValueError, TypeError) as exc:
            app.logger.error(f"Fetch quote parse error: {exc}")
        elapsed_ms = (time.perf_counter() - request_start) * 1000.0
        self._record_latency(elapsed_ms, source="fetch_quote")
        return 0.0, 0

    def load_historical_ohlc(self, days_back: int = 3, limit: int = 5000) -> bool:
        instrument = self._normalize_symbol(getattr(self._app(), "INSTRUMENT", self.engine.config.instrument))
        rows = self.load_historical_ohlc_for_symbol(instrument=instrument, days_back=days_back, limit=limit)
        if rows.empty:
            return False

        self.engine.market_data.append_ohlc_rows(rows)
        print(f"Loaded {len(rows)} historical 1-min candles -> ohlc_1min now {len(self.engine.ohlc_1min)} rows")
        return True

    def _fetch_historical_bars(self, instrument: str, days_back: int, limit: int) -> list[dict[str, Any]]:
        app = self._app()
        instrument = self._normalize_symbol(instrument)
        token = getattr(app, "CROSSTRADE_TOKEN", self.engine.config.crosstrade_token or "")
        print(f"[v21.6] Loading {limit} real 1-min OHLC bars for {instrument} (last {days_back} days)...")
        try:
            payload = {
                "instrument": instrument,
                "periodType": "minute",
                "period": 1,
                "daysBack": days_back,
                "limit": limit,
            }
            response = requests.post(
                "https://app.crosstrade.io/v1/api/market/bars",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=40,
            )
            if response.status_code != 200:
                print(f"API error {response.status_code}: {response.text[:400]}")
                return []

            data = response.json()
            bars = (
                data
                if isinstance(data, list)
                else data.get("bars") or data.get("data") or data.get("result") or data.get("ohlc") or []
            )

            if not isinstance(bars, list):
                return []
            return bars
        except Exception as exc:
            print(f"Historical load crash: {exc}")
            app.logger.error(f"Historical load error: {exc}")
            return []

    def load_historical_ohlc_for_symbol(self, instrument: str, days_back: int = 3, limit: int = 5000) -> pd.DataFrame:
        bars = self._fetch_historical_bars(instrument=instrument, days_back=days_back, limit=limit)
        rows: list[dict[str, Any]] = []
        for bar in bars:
            ts_str = bar.get("timestamp") or bar.get("time")
            if not ts_str:
                continue
            ts = pd.to_datetime(ts_str)
            if ts.tzinfo is not None:
                ts = ts.tz_convert(None)
            rows.append(
                {
                    "timestamp": ts,
                    "open": float(bar.get("open") or bar.get("last") or 0),
                    "high": float(bar.get("high") or bar.get("last") or 0),
                    "low": float(bar.get("low") or bar.get("last") or 0),
                    "close": float(bar.get("close") or bar.get("last") or 0),
                    "volume": int(bar.get("volume", 0)),
                }
            )

        if not rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(rows)

    def load_historical_ohlc_extended(
        self,
        days_back: int = 30,
        limit: int = 120000,
        ticks_per_bar: int = 4,
    ) -> list[dict[str, Any]]:
        """Load historical bars and expand each bar into pseudo ticks.

        Crosstrade historical endpoint is bar-based; this creates a deterministic
        tick stream (open/high/low/close path) for simulation workloads.
        """
        app = self._app()
        instrument = self._normalize_symbol(getattr(app, "INSTRUMENT", self.engine.config.instrument))
        try:
            bars = self._fetch_historical_bars(instrument=instrument, days_back=days_back, limit=limit)

            ticks: list[dict[str, Any]] = []
            for bar in bars:
                ts_str = bar.get("timestamp") or bar.get("time")
                if not ts_str:
                    continue
                bar_ts = pd.to_datetime(ts_str)
                if bar_ts.tzinfo is not None:
                    bar_ts = bar_ts.tz_convert(None)

                o = float(bar.get("open") or bar.get("last") or 0.0)
                h = float(bar.get("high") or bar.get("last") or 0.0)
                l = float(bar.get("low") or bar.get("last") or 0.0)
                c = float(bar.get("close") or bar.get("last") or 0.0)
                v = max(1, int(bar.get("volume", 1)))

                # Price path with directional bias from open->close.
                path = [o, h, l, c]
                if c < o:
                    path = [o, l, h, c]
                if ticks_per_bar > 4:
                    extra = [c + (h - l) * 0.25, c - (h - l) * 0.25]
                    path.extend(extra[: max(0, ticks_per_bar - 4)])

                per_tick_vol = max(1, int(v / max(1, len(path))))
                cum_vol = 0
                for idx, px in enumerate(path):
                    cum_vol += per_tick_vol
                    spread = max(0.25, abs(h - l) * 0.02)
                    ticks.append(
                        {
                            "timestamp": (bar_ts + pd.Timedelta(seconds=idx * (60 / max(1, len(path))))).isoformat(),
                            "last": float(px),
                            "bid": float(px - spread / 2.0),
                            "ask": float(px + spread / 2.0),
                            "volume": int(cum_vol),
                        }
                    )

            return ticks
        except Exception as exc:
            app.logger.error(f"Historical extended load error: {exc}")
            return []

    def gap_recovery_daemon(self) -> None:
        while True:
            time.sleep(300)
            try:
                with self.engine.live_data_lock:
                    if len(self.engine.ohlc_1min) < 50:
                        continue
                    df = self.engine.ohlc_1min[["timestamp"]].copy()
                    deltas = df["timestamp"].diff().dt.total_seconds()
                    max_gap = deltas.max() if len(deltas) > 1 else 0
                if max_gap > 120:
                    print(f"GAP DETECTED ({max_gap/60:.1f} min) -> recovery")
                    self.load_historical_ohlc(days_back=2, limit=2000)
            except Exception as exc:
                self._app().logger.error(f"Gap recovery error: {exc}")
