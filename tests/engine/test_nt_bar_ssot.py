"""ADR-0053: NT 1-minute Last bars are the only decision OHLC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from lumina_core.engine.market_data_history import MarketDataHistoryMixin
from lumina_core.engine.market_data_manager import MarketDataManager, partition_closed_and_forming
from lumina_core.engine.nt_bar_ssot import (
    BarRejected,
    accept_source_bars,
    is_forming_bar,
    is_recent_closed_bar,
    skip_ratio_fail,
    validate_nt_bar,
)
from lumina_core.engine.ohlc_clock import utc_from_any, utc_from_unix_ms


def _bar(ts: datetime, *, opened: float = 10.0, high: float = 11.0, low: float = 9.0, close: float = 10.5) -> dict:
    return {
        "timestamp": ts,
        "open": opened,
        "high": high,
        "low": low,
        "close": close,
        "volume": 4,
    }


def test_validate_nt_bar_rejects_unsupported_period() -> None:
    ts = datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc)
    with pytest.raises(BarRejected) as caught:
        validate_nt_bar({**_bar(ts), "bar_period": "1d"})
    assert caught.value.code == "bar_period_unsupported"


def test_validate_nt_bar_rejects_missing_high() -> None:
    ts = datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc)
    with pytest.raises(BarRejected) as caught:
        validate_nt_bar({"timestamp": ts, "open": 10.0, "low": 9.0, "close": 10.0, "volume": 1})
    assert caught.value.code == "ohlc_missing"


def test_validate_nt_bar_rejects_zero_and_inconsistent() -> None:
    ts = datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc)
    with pytest.raises(BarRejected) as zero:
        validate_nt_bar(_bar(ts, high=0.0))
    assert zero.value.code == "ohlc_non_positive"
    with pytest.raises(BarRejected) as bad:
        validate_nt_bar(_bar(ts, high=10.0, opened=10.5, close=10.6, low=10.2))
    assert bad.value.code == "ohlc_inconsistent"


def test_validate_nt_bar_unix_ms_is_utc() -> None:
    bar = validate_nt_bar(
        {
            "timestamp_unix_ms": 1_700_000_000_000,
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.5,
            "volume": 3,
        }
    )
    assert bar["timestamp"].tzinfo is not None
    assert utc_from_unix_ms(1_700_000_000_000) == bar["timestamp"]


def test_accept_source_bars_does_not_last_fill() -> None:
    ts = datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc)
    accepted, rejected = accept_source_bars(
        [
            _bar(ts),
            {"timestamp": ts, "last": 10.0, "volume": 1},
        ]
    )
    assert len(accepted) == 1
    assert rejected == 1


def test_skip_ratio_fail() -> None:
    assert skip_ratio_fail(0, 0) is True
    assert skip_ratio_fail(19, 1) is False
    assert skip_ratio_fail(18, 2) is True


def test_apply_nt_bar_updates_forming_then_closes() -> None:
    md = MarketDataManager()
    t0 = datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 2, 14, 32, tzinfo=timezone.utc)
    now = t0 - timedelta(seconds=1)
    assert md.apply_nt_bar(_bar(t0, high=10.5), now=now) is None
    assert md.apply_nt_bar(_bar(t0, high=12.0), now=now) is None
    assert md.current_candle is not None
    assert float(md.current_candle["high"]) == 12.0
    assert md.ohlc_1min.empty
    closed = md.apply_nt_bar(_bar(t1, opened=12.0, high=12.5, low=11.8, close=12.2), now=now)
    assert closed is not None
    assert float(closed["high"]) == 12.0
    assert float(closed["close"]) == 10.5
    assert len(md.ohlc_1min) == 1
    assert md.ohlc_1min["timestamp"].dt.tz is not None


def test_apply_nt_bar_commits_already_closed() -> None:
    md = MarketDataManager()
    t0 = datetime(2026, 1, 2, 14, 31, tzinfo=timezone.utc)
    forming = t0 + timedelta(minutes=1)
    now = t0 + timedelta(seconds=5)
    assert md.apply_nt_bar(_bar(t0, high=12.0), now=now) is None
    assert len(md.ohlc_1min) == 1
    closed = md.apply_nt_bar(
        _bar(forming, opened=12.0, high=12.5, low=11.8, close=12.2), now=now
    )
    assert closed is not None
    assert md.current_candle is not None
    assert float(md.current_candle["close"]) == 12.2
    assert len(md.ohlc_1min) == 1


def test_process_quote_tick_is_tape_only() -> None:
    md = MarketDataManager()
    ts = datetime(2026, 1, 2, 14, 31, 5, tzinfo=timezone.utc)
    assert md.process_quote_tick(ts=ts, price=10.0, bid=9.9, ask=10.1, volume_cumulative=8) is None
    assert md.process_quote_tick(
        ts=ts + timedelta(seconds=70),
        price=11.0,
        bid=10.9,
        ask=11.1,
        volume_cumulative=12,
    ) is None
    assert md.ohlc_1min.empty
    assert md.current_candle is None
    assert md.live_quotes[-1]["last"] == 11.0


def test_load_historical_ohlc_rejects_last_only_rows() -> None:
    class _H(MarketDataHistoryMixin):
        def _fetch_historical_bars(self, **_kwargs: object) -> list[dict]:
            return [{"timestamp": "2026-01-02T14:31:00Z", "last": 10.0, "volume": 1}]

    df = _H().load_historical_ohlc_for_symbol("MES SEP26", days_back=1, limit=10)
    assert df.empty


def test_load_historical_ohlc_keeps_utc() -> None:
    class _H(MarketDataHistoryMixin):
        def _fetch_historical_bars(self, **_kwargs: object) -> list[dict]:
            return [
                {
                    "timestamp": "2026-01-02T14:31:00Z",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "volume": 4,
                }
            ]

    now = datetime(2026, 1, 2, 14, 32, tzinfo=timezone.utc)
    df = _H().load_historical_ohlc_for_symbol("MES SEP26", days_back=1, limit=10, now=now)
    assert len(df) == 1
    assert df["timestamp"].dt.tz is not None
    assert float(df["high"].iloc[0]) == 11.0


def _history_loader(bars: list[dict]) -> MarketDataHistoryMixin:
    class _H(MarketDataHistoryMixin):
        def __init__(self) -> None:
            self.engine = SimpleNamespace(
                market_data=MarketDataManager(),
                config=SimpleNamespace(instrument="MES"),
            )

        def _normalize_symbol(self, symbol: str) -> str:
            return str(symbol).strip().upper()

        def _app(self) -> SimpleNamespace:
            return SimpleNamespace(INSTRUMENT="MES")

        def _fetch_historical_bars(self, **_kwargs: object) -> list[dict]:
            return bars

    return _H()


def test_load_historical_ohlc_for_symbol_drops_forming() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    closed_ts = datetime(2026, 10, 2, 14, 31, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)

    class _H(MarketDataHistoryMixin):
        def _fetch_historical_bars(self, **_kwargs: object) -> list[dict]:
            return [
                _bar(closed_ts, high=11.0, close=10.5),
                _bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5),
            ]

    df = _H().load_historical_ohlc_for_symbol("MES", days_back=1, limit=10, now=now)
    assert len(df) == 1
    assert utc_from_any(df["timestamp"].iloc[0]) == closed_ts
    assert float(df["high"].iloc[0]) == 11.0


def test_load_historical_ohlc_for_symbol_empty_when_only_forming() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)

    class _H(MarketDataHistoryMixin):
        def _fetch_historical_bars(self, **_kwargs: object) -> list[dict]:
            return [_bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5)]

    df = _H().load_historical_ohlc_for_symbol("MES", days_back=1, limit=10, now=now)
    assert df.empty


def test_load_historical_ohlc_hydrates_forming_when_closed_empty() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    loader = _history_loader(
        [_bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5)]
    )
    assert loader.load_historical_ohlc(days_back=1, limit=10, now=now) is True
    md = loader.engine.market_data
    assert md.ohlc_1min.empty
    assert md.current_candle is not None
    assert utc_from_any(md.current_candle["timestamp"]) == forming_ts
    assert float(md.current_candle["high"]) == 12.0


def test_load_historical_ohlc_extended_skips_forming() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    closed_ts = datetime(2026, 10, 2, 14, 31, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    loader = _history_loader(
        [
            _bar(closed_ts, high=11.0, close=10.5),
            _bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5),
        ]
    )
    ticks = loader.load_historical_ohlc_extended(days_back=1, limit=10, ticks_per_bar=4, now=now)
    assert len(ticks) == 4
    last_ts = utc_from_any(ticks[-1]["timestamp"])
    assert last_ts is not None
    assert last_ts < forming_ts
    assert last_ts >= closed_ts


def test_load_historical_ohlc_extended_empty_when_only_forming() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    loader = _history_loader(
        [_bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5)]
    )
    assert loader.load_historical_ohlc_extended(days_back=1, limit=10, ticks_per_bar=4, now=now) == []


def test_load_historical_ohlc_keeps_forming_off_closed_book() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    closed_ts = datetime(2026, 10, 2, 14, 31, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    loader = _history_loader(
        [
            _bar(closed_ts, high=11.0, close=10.5),
            _bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5),
        ]
    )
    assert loader.load_historical_ohlc(days_back=1, limit=10, now=now) is True
    md = loader.engine.market_data
    assert len(md.ohlc_1min) == 1
    assert utc_from_any(md.ohlc_1min["timestamp"].iloc[0]) == closed_ts
    assert float(md.ohlc_1min["high"].iloc[0]) == 11.0
    assert md.current_candle is not None
    assert utc_from_any(md.current_candle["timestamp"]) == forming_ts
    assert float(md.current_candle["high"]) == 12.0


def test_append_ohlc_rows_keeps_forming_off_closed_book() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    closed_ts = datetime(2026, 10, 2, 14, 31, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    md = MarketDataManager()
    md.append_ohlc_rows(
        pd.DataFrame(
            [
                _bar(closed_ts, high=11.0, close=10.5),
                _bar(forming_ts, opened=10.5, high=12.0, low=10.4, close=11.5),
            ]
        ),
        now=now,
    )
    assert len(md.ohlc_1min) == 1
    assert utc_from_any(md.ohlc_1min["timestamp"].iloc[0]) == closed_ts
    assert md.current_candle is not None
    assert utc_from_any(md.current_candle["timestamp"]) == forming_ts
    assert float(md.current_candle["high"]) == 12.0


def test_load_historical_then_live_forming_does_not_freeze_closed() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    closed_ts = datetime(2026, 10, 2, 14, 31, tzinfo=timezone.utc)
    forming_ts = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    loader = _history_loader(
        [
            _bar(closed_ts, high=11.0, close=10.5),
            _bar(forming_ts, opened=10.5, high=11.2, low=10.4, close=11.0),
        ]
    )
    loader.load_historical_ohlc(days_back=1, limit=10, now=now)
    md = loader.engine.market_data
    later = now + timedelta(seconds=20)
    assert md.apply_nt_bar(_bar(forming_ts, opened=10.5, high=13.0, low=10.3, close=12.4), now=later) is None
    assert len(md.ohlc_1min) == 1
    assert utc_from_any(md.ohlc_1min["timestamp"].iloc[0]) == closed_ts
    assert float(md.ohlc_1min["high"].iloc[0]) == 11.0
    assert md.current_candle is not None
    assert float(md.current_candle["high"]) == 13.0
    assert float(md.current_candle["close"]) == 12.4


def test_partition_drops_extra_future_bars() -> None:
    now = datetime(2026, 10, 2, 14, 31, 30, tzinfo=timezone.utc)
    closed_ts = datetime(2026, 10, 2, 14, 31, tzinfo=timezone.utc)
    first_future = datetime(2026, 10, 2, 14, 32, tzinfo=timezone.utc)
    last_future = datetime(2026, 10, 2, 14, 33, tzinfo=timezone.utc)
    closed, forming = partition_closed_and_forming(
        pd.DataFrame(
            [
                _bar(closed_ts),
                _bar(first_future, high=12.0, close=11.0),
                _bar(last_future, high=13.0, close=12.0),
            ]
        ),
        now=now,
    )
    assert len(closed) == 1
    assert utc_from_any(closed["timestamp"].iloc[0]) == closed_ts
    assert forming is not None
    assert utc_from_any(forming["timestamp"]) == last_future
    assert float(forming["high"]) == 13.0


def test_drain_nt_bars_closes_recent_from_queue(tmp_path: Path) -> None:
    from lumina_core.engine.market_data_ingest import MarketDataIngestCore

    md = MarketDataManager()
    engine = SimpleNamespace(market_data=md, config=SimpleNamespace(trade_mode="sim"))
    core = MarketDataIngestCore(engine=engine)  # type: ignore[arg-type]
    t0 = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    t1 = t0 + timedelta(minutes=1)
    queued = [
        _bar(t0, high=11.0, close=10.5),
        _bar(t1, opened=10.5, high=12.0, low=10.4, close=11.0),
    ]
    client = SimpleNamespace(take_bar=lambda: queued.pop(0) if queued else None)
    app = SimpleNamespace(logger=MagicMock(), swarm_manager=None)
    core._drain_nt_bars(app, client, tmp_path)
    assert len(md.ohlc_1min) == 1
    assert float(md.ohlc_1min["high"].iloc[0]) == 11.0
    assert md.current_candle is not None
    assert float(md.current_candle["close"]) == 11.0


def test_is_recent_closed_bar_window() -> None:
    now = datetime(2026, 1, 2, 14, 32, tzinfo=timezone.utc)
    assert is_recent_closed_bar(now - timedelta(seconds=30), now=now) is True
    assert is_recent_closed_bar(now - timedelta(seconds=121), now=now) is False
    assert is_recent_closed_bar(None, now=now) is False
    assert is_recent_closed_bar(now + timedelta(seconds=30), now=now) is False
    assert is_forming_bar(now + timedelta(seconds=30), now) is True
    assert is_forming_bar(now - timedelta(seconds=1), now) is False
