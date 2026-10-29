"""S2.5: NT-PIT tape refuses forming bars and look-ahead."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lumina_research.cycles.holdout import HOLDOUT_PIN_UTC, HoldoutLocked, assert_holdout_pin_closed, holdout_pin_is_closed
from lumina_research.validation.nt_tape import (
    TapeRefused,
    closed_bars_from_rows,
    fixture_closed_mes_bars,
    materializer_from_rows,
    refuse_synthetic_as_nt_pit,
    refuse_vendor_csv_substitute,
    series_from_closed_bars,
)


@pytest.mark.unit
def test_closed_mes_fixture_is_nt_pit() -> None:
    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = fixture_closed_mes_bars(now=now)
    bars = closed_bars_from_rows(rows, now=now, purpose="gate")
    materializer = materializer_from_rows(rows, now=now, purpose="gate")
    assert materializer.tape_kind == "nt_pit"
    gross, positions, markets = materializer(None)  # type: ignore[arg-type]
    assert len(gross) == len(positions) == len(markets)
    assert all(item.timestamp <= now for item in bars)


@pytest.mark.unit
def test_forming_and_future_bars_refused() -> None:
    now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    rows = list(fixture_closed_mes_bars(n=241, now=now, start=datetime(2025, 6, 1, 8, 0, tzinfo=timezone.utc)))
    rows[-1] = {**rows[-1], "timestamp": now + timedelta(minutes=1)}
    with pytest.raises(TapeRefused, match="forming_bar_refused|lookahead_future_bar"):
        closed_bars_from_rows(rows, now=now, purpose="gate")


@pytest.mark.unit
def test_shuffled_timestamps_are_lookahead() -> None:
    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = list(fixture_closed_mes_bars(now=now))
    rows[10], rows[11] = rows[11], rows[10]
    with pytest.raises(TapeRefused, match="timestamps_not_increasing"):
        closed_bars_from_rows(rows, now=now, purpose="gate")


@pytest.mark.unit
def test_returns_use_only_past_closes() -> None:
    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = list(fixture_closed_mes_bars(now=now))
    rows[80] = {**rows[80], "open": 8000.0, "close": 8000.0, "high": 8000.5, "low": 7999.5}
    bars = closed_bars_from_rows(rows, now=now, purpose="gate")
    gross, _positions, _markets = series_from_closed_bars(bars)
    expected = tuple(
        (bars[i].close - bars[i - 1].close) / bars[i - 1].close for i in range(1, len(bars))
    )
    assert gross == expected
    # Using bar t+1 for the return at t would pull the 8000 spike one step earlier.
    lookahead_at_79 = (bars[80].close - bars[79].close) / bars[79].close
    assert gross[78] != pytest.approx(lookahead_at_79)
    assert gross[79] == pytest.approx((bars[80].close - bars[79].close) / bars[79].close)


@pytest.mark.unit
def test_holdout_pin_stays_closed() -> None:
    assert holdout_pin_is_closed() is True
    with pytest.raises(HoldoutLocked, match="2026-01-28"):
        assert_holdout_pin_closed(ts_ns=int(HOLDOUT_PIN_UTC.timestamp() * 1_000_000_000), purpose="gate")
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = [
        {
            "timestamp": HOLDOUT_PIN_UTC,
            "open": 5000.0,
            "high": 5001.0,
            "low": 4999.0,
            "close": 5000.5,
            "volume": 10,
            "bar_period": "1m",
        }
        for _ in range(241)
    ]
    with pytest.raises(TapeRefused, match="holdout_pin_closed"):
        closed_bars_from_rows(rows, now=now, purpose="gate")


@pytest.mark.unit
def test_synthetic_and_vendor_csv_refused() -> None:
    with pytest.raises(TapeRefused, match="synthetic_cannot_be_nt_pit"):
        refuse_synthetic_as_nt_pit("synthetic")
    with pytest.raises(TapeRefused, match="survivors_not_nt_pit"):
        refuse_synthetic_as_nt_pit("planted_edge")
    with pytest.raises(TapeRefused, match="vendor_csv_substitute"):
        refuse_vendor_csv_substitute("data/yahoo_mes.csv")
