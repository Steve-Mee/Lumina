from __future__ import annotations

from collections import deque
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from lumina_core.engine.bar_integrity import BarBookStatus
from lumina_core.engine.nt_bar_ssot import is_forming_bar, validate_nt_bar
from lumina_core.engine.nt_ohlc_frames import concat_forming, empty_ohlc
from lumina_core.engine.ohlc_clock import utc_from_any

_OHLC_COLS = ["timestamp", "open", "high", "low", "close", "volume"]


def partition_closed_and_forming(
    rows: pd.DataFrame,
    *,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    """Split NT history into closed rows and the latest still-forming bar.

    NT stamps the close time. A timestamp still in the future is forming and
    must not enter the closed book (ADR-0053 / ADR-0054). Extra future rows
    besides the latest are dropped, never treated as closed.
    """
    empty = pd.DataFrame(columns=_OHLC_COLS)
    if rows is None or rows.empty:
        return empty, None
    if "timestamp" not in rows.columns:
        raise ValueError("OHLC rows require a timestamp column")
    now_utc = utc_from_any(now) or datetime.now(timezone.utc)
    work = rows.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    flags = work["timestamp"].map(lambda ts: bool(is_forming_bar(ts, now_utc)))
    closed = work.loc[~flags].copy()
    forming = work.loc[flags]
    if forming.empty:
        return closed, None
    last = forming.sort_values("timestamp").iloc[-1]
    period_raw = last["bar_period"] if "bar_period" in forming.columns else "1m"
    if period_raw is None or (isinstance(period_raw, float) and period_raw != period_raw):
        period_raw = "1m"
    payload: dict[str, Any] = {
        "timestamp": last["timestamp"],
        "open": last["open"],
        "high": last["high"],
        "low": last["low"],
        "close": last["close"],
        "volume": last["volume"] if "volume" in forming.columns else 0,
        "bar_period": str(period_raw) if period_raw else "1m",
    }
    return closed, payload


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
    on_quote_tick: Any | None = None
    ohlc_by_period: dict[str, pd.DataFrame] = field(default_factory=dict)
    current_by_period: dict[str, dict[str, Any]] = field(default_factory=dict)
    integrity: BarBookStatus | None = None

    def __post_init__(self) -> None:
        expected = {"timestamp", "open", "high", "low", "close", "volume"}
        if not expected.issubset(set(self.ohlc_1min.columns)):
            raise ValueError("ohlc_1min must contain timestamp/open/high/low/close/volume columns")

    def append_quote(self, quote: dict[str, Any], max_quotes: int = 3000) -> None:
        with self.live_data_lock:
            self.live_quotes.append(quote)
            if len(self.live_quotes) > max_quotes:
                self.live_quotes.pop(0)

    def append_ohlc_rows(self, rows: pd.DataFrame, *, now: datetime | None = None) -> None:
        """Append closed NT 1m rows. A still-forming last bar goes to current_candle."""
        if rows is None or rows.empty:
            return
        closed, forming = partition_closed_and_forming(rows, now=now)
        if not closed.empty:
            with self.live_data_lock:
                left = self.ohlc_1min
                parts: list[pd.DataFrame] = [df for df in (left, closed) if df is not None and not df.empty]
                if parts:
                    merged = parts[0] if len(parts) == 1 else pd.concat(parts, sort=False)
                    self.ohlc_1min = self._finalize_ohlc(merged)
                    self.ohlc_by_period["1m"] = self.ohlc_1min
        if forming is not None:
            self.apply_nt_bar(forming, now=now)

    @staticmethod
    def _finalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        out = df.copy()
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
        return (
            out.drop_duplicates("timestamp", keep="last")
            .sort_values("timestamp")
            .tail(20000)
            .reset_index(drop=True)
        )

    def apply_nt_bar(self, raw: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any] | None:
        """Apply one native NT Last bar. Returns a bar the first time it is closed.

        NT stamps the close time. A timestamp still in the future stays forming
        and is not written to the closed book. A timestamp already past is closed
        and is upserted (keep last) so hydrate/reconcile match NT's closed set.
        """
        bar = validate_nt_bar(raw)
        ts = bar["timestamp"]
        period = str(bar.get("bar_period") or "1m")
        now_utc = utc_from_any(now) or datetime.now(timezone.utc)
        still_forming = is_forming_bar(ts, now_utc)
        closed: dict[str, Any] | None = None
        with self.live_data_lock:
            book = self.ohlc_by_period.get(period)
            if book is None or book.empty:
                book = empty_ohlc()

            def _set_current(row: dict[str, Any]) -> None:
                self.current_by_period[period] = dict(row)
                if period == "1m":
                    self.current_candle = dict(row)
                    self.candle_start_ts = row["timestamp"]

            def _upsert_book(row: dict[str, Any]) -> None:
                nonlocal book
                book = self._finalize_ohlc(pd.concat([book, pd.DataFrame([dict(row)])]))
                self.ohlc_by_period[period] = book
                if period == "1m":
                    self.ohlc_1min = book

            def _in_book(stamp: datetime) -> bool:
                if book is None or book.empty or "timestamp" not in book.columns:
                    return False
                want = utc_from_any(stamp)
                if want is None:
                    return False
                for value in book["timestamp"]:
                    parsed = utc_from_any(value)
                    if parsed is not None and parsed == want:
                        return True
                return False

            current = self.current_by_period.get(period)
            if current is None:
                _set_current(bar)
                if not still_forming:
                    _upsert_book(bar)
                else:
                    self.ohlc_by_period[period] = book
                return None
            current_ts = current["timestamp"]
            if current_ts == ts:
                already = _in_book(ts)
                _set_current(bar)
                if not still_forming:
                    _upsert_book(bar)
                    if not already:
                        closed = dict(bar)
                return closed
            if current_ts < ts:
                closed = dict(current)
                _upsert_book(closed)
                _set_current(bar)
                if not still_forming:
                    _upsert_book(bar)
                return closed
            _upsert_book(bar)
        return None

    def copy_ohlc_period(self, period: str, *, forming: bool = False) -> pd.DataFrame:
        with self.live_data_lock:
            closed = self.ohlc_by_period.get(period)
            if closed is None or closed.empty:
                closed = self.ohlc_1min if period == "1m" else empty_ohlc()
            if not forming:
                return closed.copy()
            live = self.current_by_period.get(period)
            if period == "1m" and live is None:
                live = self.current_candle
            return concat_forming(closed, live)

    def copy_ohlc_with_forming(self) -> pd.DataFrame:
        return self.copy_ohlc_period("1m", forming=True)

    def process_quote_tick(
        self,
        *,
        ts: datetime,
        price: float,
        bid: float,
        ask: float,
        volume_cumulative: int,
    ) -> dict[str, Any] | None:
        """Tape only. Quotes never write ``ohlc_1min`` (ADR-0053)."""
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

            delta_vol = max(0, volume_cumulative - self.prev_volume_cum)
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

        listener = self.on_quote_tick
        if listener is not None:
            try:
                listener(
                    {
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "last": float(price),
                        "bid": float(bid),
                        "ask": float(ask),
                        "volume": int(volume_cumulative),
                    }
                )
            except Exception:
                pass
        return None

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
