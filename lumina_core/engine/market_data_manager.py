from __future__ import annotations

from collections import deque
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass(slots=True)
class MarketDataManager:
    """Single source of truth for quotes and 1-minute OHLC data."""

    ohlc_1min: pd.DataFrame = field(
        default_factory=lambda: pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    )
    live_quotes: list[dict[str, Any]] = field(default_factory=list)
    live_data_lock: threading.Lock = field(default_factory=threading.Lock)
    current_candle: dict[str, Any] | None = None
    candle_start_ts: datetime | None = None
    prev_volume_cum: float = 0.0
    prev_last_price: float | None = None
    rolling_tick_deltas: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    rolling_volume_deltas: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    rolling_bid_ask_imbalance: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    cumulative_delta_10: float = 0.0
    last_volume_delta: float = 0.0
    last_bid_ask_imbalance: float = 1.0
    last_tape_signal: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        expected = {"timestamp", "open", "high", "low", "close", "volume"}
        if not expected.issubset(set(self.ohlc_1min.columns)):
            raise ValueError("ohlc_1min must contain timestamp/open/high/low/close/volume columns")

    def append_quote(self, quote: dict[str, Any], max_quotes: int = 3000) -> None:
        with self.live_data_lock:
            self.live_quotes.append(quote)
            if len(self.live_quotes) > max_quotes:
                self.live_quotes.pop(0)

    def append_ohlc_rows(self, rows: pd.DataFrame) -> None:
        with self.live_data_lock:
            self.ohlc_1min = (
                pd.concat([self.ohlc_1min, rows])
                .drop_duplicates("timestamp")
                .sort_values("timestamp")
                .tail(20000)
                .reset_index(drop=True)
            )

    def process_quote_tick(
        self,
        *,
        ts: datetime,
        price: float,
        bid: float,
        ask: float,
        volume_cumulative: int,
    ) -> dict[str, Any] | None:
        """Append quote and update the active 1-minute candle.

        Returns the candle that was just closed when a new minute starts.
        """
        closed_candle: dict[str, Any] | None = None
        minute_start = ts.replace(second=0, microsecond=0)

        with self.live_data_lock:
            self.live_quotes.append(
                {
                    "timestamp": ts.isoformat(),
                    "last": price,
                    "bid": bid,
                    "ask": ask,
                    "volume": volume_cumulative,
                }
            )
            if len(self.live_quotes) > 3000:
                self.live_quotes.pop(0)

            if self.current_candle is None or self.candle_start_ts != minute_start:
                if self.current_candle is not None:
                    closed_candle = dict(self.current_candle)
                    self.ohlc_1min = (
                        pd.concat([self.ohlc_1min, pd.DataFrame([closed_candle])])
                        .drop_duplicates("timestamp")
                        .sort_values("timestamp")
                        .tail(20000)
                        .reset_index(drop=True)
                    )

                self.current_candle = {
                    "timestamp": minute_start,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 0,
                }
                self.candle_start_ts = minute_start
            else:
                self.current_candle["high"] = max(self.current_candle["high"], price)
                self.current_candle["low"] = min(self.current_candle["low"], price)
                self.current_candle["close"] = price

            delta_vol = max(0, volume_cumulative - self.prev_volume_cum)
            if self.current_candle is not None:
                self.current_candle["volume"] += delta_vol

            signed_delta = self._classify_signed_delta(price, bid, ask, float(delta_vol))
            imbalance = self._compute_bid_ask_imbalance(price, bid, ask)
            self.rolling_tick_deltas.append(signed_delta)
            self.rolling_volume_deltas.append(float(delta_vol))
            self.rolling_bid_ask_imbalance.append(imbalance)
            self.cumulative_delta_10 = float(sum(self.rolling_tick_deltas))
            self.last_volume_delta = float(delta_vol)
            self.last_bid_ask_imbalance = float(imbalance)

            self.prev_last_price = float(price)
            self.prev_volume_cum = volume_cumulative

        return closed_candle

    def _compute_bid_ask_imbalance(self, last: float, bid: float, ask: float) -> float:
        eps = 1e-6
        if ask <= bid:
            return 1.0

        # Last near ask implies stronger buying pressure; near bid implies selling pressure.
        buy_dist = max(eps, ask - last)
        sell_dist = max(eps, last - bid)
        ratio = sell_dist / buy_dist
        return max(0.01, min(100.0, float(ratio)))

    def _classify_signed_delta(self, last: float, bid: float, ask: float, volume_delta: float) -> float:
        if volume_delta <= 0:
            return 0.0

        prev_last = self.prev_last_price
        if prev_last is not None:
            if last > prev_last:
                return float(volume_delta)
            if last < prev_last:
                return -float(volume_delta)

        mid = (bid + ask) / 2.0 if ask >= bid else last
        if last > mid:
            return float(volume_delta)
        if last < mid:
            return -float(volume_delta)
        return 0.0

    def get_tape_snapshot(self) -> dict[str, float]:
        with self.live_data_lock:
            avg_volume_delta = (
                float(sum(self.rolling_volume_deltas) / len(self.rolling_volume_deltas))
                if self.rolling_volume_deltas
                else 0.0
            )
            avg_imbalance = (
                float(sum(self.rolling_bid_ask_imbalance) / len(self.rolling_bid_ask_imbalance))
                if self.rolling_bid_ask_imbalance
                else 1.0
            )
            return {
                "volume_delta": float(self.last_volume_delta),
                "avg_volume_delta_10": avg_volume_delta,
                "bid_ask_imbalance": float(self.last_bid_ask_imbalance),
                "avg_bid_ask_imbalance_10": avg_imbalance,
                "cumulative_delta_10": float(self.cumulative_delta_10),
            }

    def copy_ohlc(self) -> pd.DataFrame:
        with self.live_data_lock:
            return self.ohlc_1min.copy()

    def latest_price(self) -> float:
        with self.live_data_lock:
            if self.live_quotes:
                return float(self.live_quotes[-1].get("last", 0.0))
            if len(self.ohlc_1min):
                return float(self.ohlc_1min["close"].iloc[-1])
        return 0.0
