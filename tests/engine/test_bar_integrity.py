"""ADR-0054: NT is SSOT for missing 1m bars. Never invent OHLC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from lumina_core.engine.bar_integrity import (
    BarBookStatus,
    entries_blocked,
    reconcile_against_nt,
    tape_is_live,
)
from lumina_core.engine.nt_bar_ssot import is_forming_bar
from lumina_core.engine.market_data_manager import MarketDataManager
from lumina_core.engine.nt_bar_periods import canonicalize_period
from lumina_core.engine.nt_ohlc_frames import concat_forming, operator_listing, snapshot_native


def _ts(minute: int) -> datetime:
    return datetime(2026, 10, 2, 14, minute, tzinfo=timezone.utc)


def _bar(ts: datetime, *, close: float = 10.0) -> dict:
    return {
        "timestamp": ts,
        "open": close,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": 4,
        "bar_period": "1m",
    }


def test_canonicalize_period_aliases() -> None:
    assert canonicalize_period("240min") == "240m"
    assert canonicalize_period("4h") == "240m"
    assert canonicalize_period("1d") is None


def test_reconcile_fills_nt_bars_luminas_missed() -> None:
    local = [_ts(31)]
    nt = [_bar(_ts(31)), _bar(_ts(32), close=11.0)]
    status, missing = reconcile_against_nt(
        local_closed=local,
        nt_rows=nt,
        nt_ok=True,
        now=_ts(32) + timedelta(seconds=5),
        quotes_live=True,
    )
    assert status.reason == "filling"
    assert status.lock_new_entries is True
    assert len(missing) == 1
    assert float(missing[0]["close"]) == 11.0


def test_reconcile_session_when_tape_quiet_and_nt_stale() -> None:
    local = [_ts(31)]
    nt = [_bar(_ts(31))]
    status, missing = reconcile_against_nt(
        local_closed=local,
        nt_rows=nt,
        nt_ok=True,
        now=_ts(31) + timedelta(minutes=40),
        quotes_live=False,
    )
    assert missing == []
    assert status.complete is True
    assert status.reason == "session_hole"
    assert status.lock_new_entries is False


def test_reconcile_unexplained_when_tape_live_and_nt_stale() -> None:
    local = [_ts(31)]
    nt = [_bar(_ts(31))]
    status, missing = reconcile_against_nt(
        local_closed=local,
        nt_rows=nt,
        nt_ok=True,
        now=_ts(31) + timedelta(minutes=5),
        quotes_live=True,
    )
    assert missing == []
    assert status.complete is False
    assert status.reason == "unexplained_hole"
    assert status.lock_new_entries is True


def test_reconcile_nt_unreachable_locks() -> None:
    status, missing = reconcile_against_nt(
        local_closed=[_ts(31)],
        nt_rows=None,
        nt_ok=False,
        now=_ts(32),
        quotes_live=True,
    )
    assert missing == []
    assert status.reason == "nt_unreachable"
    assert status.lock_new_entries is True


def test_never_invents_ohlc_on_empty_nt() -> None:
    status, missing = reconcile_against_nt(
        local_closed=[],
        nt_rows=[],
        nt_ok=True,
        now=_ts(32),
        quotes_live=False,
    )
    assert missing == []
    assert status.reason == "empty"
    assert status.lock_new_entries is True


def test_entries_blocked_real_empty_book() -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real"),
        market_data=MarketDataManager(),
    )
    blocked, reason = entries_blocked(engine)
    assert blocked is True
    assert "empty" in reason.lower() or "missing" in reason.lower()


def test_entries_blocked_uses_integrity_lock() -> None:
    md = MarketDataManager()
    md.integrity = BarBookStatus(
        complete=False,
        reason="filling",
        missing_count=1,
        filled_count=0,
        session_holes=0,
        lock_new_entries=True,
        last_closed=_ts(31),
        message="filling",
    )
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="sim"), market_data=md)
    blocked, _reason = entries_blocked(engine)
    assert blocked is True


def test_apply_nt_bar_keeps_15m_off_1m_book() -> None:
    md = MarketDataManager()
    t0 = _ts(0)
    t1 = _ts(15)
    now = t0 - timedelta(seconds=1)
    assert md.apply_nt_bar({**_bar(t0), "bar_period": "15m"}, now=now) is None
    closed = md.apply_nt_bar({**_bar(t1, close=12.0), "bar_period": "15m"}, now=now)
    assert closed is not None
    assert md.ohlc_1min.empty
    fifteen = md.copy_ohlc_period("15m", forming=False)
    assert len(fifteen) == 1
    assert float(fifteen["close"].iloc[0]) == 10.0


def test_copy_ohlc_with_forming_appends_live_candle() -> None:
    md = MarketDataManager()
    t0 = _ts(31)
    t1 = _ts(32)
    now = t0 - timedelta(seconds=1)
    md.apply_nt_bar(_bar(t0), now=now)
    md.apply_nt_bar(_bar(t1, close=11.0), now=now)
    frame = md.copy_ohlc_with_forming()
    assert len(frame) == 2
    assert float(frame["close"].iloc[-1]) == 11.0


def test_forming_bar_is_not_a_missed_closed_bar() -> None:
    local = [_ts(31)]
    nt = [_bar(_ts(31)), _bar(_ts(33), close=11.0)]
    status, missing = reconcile_against_nt(
        local_closed=local,
        nt_rows=nt,
        nt_ok=True,
        now=_ts(32) + timedelta(seconds=5),
        quotes_live=True,
    )
    assert missing == []
    assert status.reason == "complete"
    assert status.lock_new_entries is False
    assert is_forming_bar(_ts(33), _ts(32) + timedelta(seconds=5)) is True


def test_reconcile_window_ignores_older_local_bars() -> None:
    local = [_ts(1), _ts(31)]
    nt = [_bar(_ts(31))]
    status, missing = reconcile_against_nt(
        local_closed=local,
        nt_rows=nt,
        nt_ok=True,
        now=_ts(31) + timedelta(seconds=5),
        quotes_live=True,
    )
    assert missing == []
    assert status.reason == "complete"
    assert status.lock_new_entries is False


def test_tape_is_live_ignores_stale_quotes() -> None:
    now = _ts(32)
    stale = [{"timestamp": (_ts(31) - timedelta(minutes=10)).isoformat()}]
    fresh = [{"timestamp": (now - timedelta(seconds=2)).isoformat()}]
    assert tape_is_live(stale, now) is False
    assert tape_is_live(fresh, now) is True
    assert tape_is_live([], now) is False


def test_concat_forming_does_not_duplicate_timestamp() -> None:
    import pandas as pd

    ts = _ts(31)
    closed = pd.DataFrame(
        [{"timestamp": ts, "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 1}]
    )
    forming = {"timestamp": ts, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 2}
    out = concat_forming(closed, forming)
    assert len(out) == 1
    assert float(out["high"].iloc[0]) == 12.0


def test_snapshot_native_marks_forming() -> None:
    import pandas as pd

    forming_ts = datetime.now(timezone.utc) + timedelta(seconds=30)
    closed_ts = datetime.now(timezone.utc) - timedelta(minutes=1)
    frame = pd.DataFrame(
        [
            {
                "timestamp": closed_ts,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 1,
            },
            {
                "timestamp": forming_ts,
                "open": 10.5,
                "high": 12.0,
                "low": 10.4,
                "close": 11.0,
                "volume": 2,
            },
        ]
    )

    class _Md:
        def copy_ohlc_period(self, period: str, forming: bool = True) -> pd.DataFrame:
            del period
            return frame if forming else frame.iloc[:1]

    snap = snapshot_native(_Md(), {"1min": 60, "1d": 86400})
    assert snap["1min"]["source"] == "nt:1m"
    assert snap["1min"]["forming"] is True
    assert snap["1min"]["high"] == 12.0
    assert snap["1d"]["source"] == "missing"
    assert snap["1d"]["forming"] is False
    assert snap["1d"]["close"] == 0.0


def test_operator_listing_names_a_blank_instrument() -> None:
    assert operator_listing(SimpleNamespace()) == "listing onbekend"
    assert (
        operator_listing(SimpleNamespace(), SimpleNamespace(config=SimpleNamespace(instrument="")))
        == "listing onbekend"
    )
    assert operator_listing(SimpleNamespace(INSTRUMENT="MES DEC26")) == "MES DEC26"
    assert (
        operator_listing(SimpleNamespace(), SimpleNamespace(config=SimpleNamespace(instrument="MES SEP26")))
        == "MES SEP26"
    )
