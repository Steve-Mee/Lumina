"""Missed open minutes are filled from real bars. The live file and the book stay put."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from lumina_core.market.archive_repair import open_holes, repair_next_hole
from lumina_core.market.minute_bars import MinuteBar, append_minute, archive_path, load_minutes
from lumina_core.maturity.playground.sentence_window import MINUTE_NS

ET = ZoneInfo("America/New_York")


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000_000)


def _store(root: Path, moment: datetime, *, price: float = 5000.0) -> None:
    append_minute(
        root,
        "MES",
        ts_ns=_ns(moment),
        open_px=price,
        high_px=price + 0.25,
        low_px=price - 0.25,
        close_px=price,
        volume=1,
        market_open=True,
    )


def _bar(moment: datetime, *, close: int = 20_000) -> MinuteBar:
    return MinuteBar(ts_ns=_ns(moment), open_ticks=close, high_ticks=close + 4, low_ticks=close - 4, close_ticks=close, volume=2)


@pytest.mark.unit
def test_a_halt_and_a_weekend_are_not_holes() -> None:
    monday = datetime(2026, 10, 5, 16, 59, tzinfo=ET)
    halt_end = datetime(2026, 10, 5, 18, 0, tzinfo=ET)
    friday = datetime(2026, 10, 2, 16, 59, tzinfo=ET)
    sunday = datetime(2026, 10, 4, 18, 0, tzinfo=ET)
    assert open_holes((_bar(friday), _bar(sunday))) == []
    assert open_holes((_bar(monday), _bar(halt_end))) == []
    close = datetime(2026, 10, 5, 17, 0, tzinfo=ET)
    reopen = datetime(2026, 10, 5, 18, 1, tzinfo=ET)
    holes = open_holes((_bar(close), _bar(reopen)))
    assert holes == [(_ns(datetime(2026, 10, 5, 18, 0, tzinfo=ET)), _ns(reopen))]
    friday_close = datetime(2026, 10, 2, 17, 0, tzinfo=ET)
    sunday_late = datetime(2026, 10, 4, 18, 1, tzinfo=ET)
    weekend = open_holes((_bar(friday_close), _bar(sunday_late)))
    assert weekend == [(_ns(datetime(2026, 10, 4, 18, 0, tzinfo=ET)), _ns(sunday_late))]


@pytest.mark.unit
def test_recovered_minute_lands_beside_the_live_file(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=2))
    before = archive_path(tmp_path, "MES").read_bytes()
    missing = start + timedelta(minutes=1)
    pinned = (start + timedelta(minutes=2, seconds=30)).timestamp()
    result = repair_next_hole(tmp_path, symbol="MES", fetcher=lambda _start, _end: [_bar(missing)], now=pinned)
    assert result["reason"] == "filled"
    assert result["added"] == 1
    assert archive_path(tmp_path, "MES").read_bytes() == before
    loaded = load_minutes(tmp_path, "MES")
    assert [bar.ts_ns for bar in loaded] == [_ns(start), _ns(missing), _ns(start + timedelta(minutes=2))]


@pytest.mark.unit
def test_empty_source_writes_nothing_and_waits(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=2))
    calls = {"n": 0}

    def fetch(_start: int, _end: int) -> list[MinuteBar]:
        calls["n"] += 1
        return []

    first = repair_next_hole(tmp_path, symbol="MES", fetcher=fetch, now=1_000.0)
    second = repair_next_hole(tmp_path, symbol="MES", fetcher=fetch, now=1_100.0)
    assert first["reason"] == "source_empty"
    assert second["reason"] == "waiting"
    assert calls["n"] == 1
    assert len(load_minutes(tmp_path, "MES")) == 2


@pytest.mark.unit
def test_unreachable_source_does_not_invent(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=2))
    result = repair_next_hole(tmp_path, symbol="MES", fetcher=lambda _start, _end: None, now=1_000.0)
    assert result["reason"] == "nt_unreachable"
    assert len(load_minutes(tmp_path, "MES")) == 2


@pytest.mark.unit
def test_a_different_price_for_the_same_minute_is_refused(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=2))
    missing = start + timedelta(minutes=1)
    first = _bar(missing, close=20_000)
    clash = _bar(missing, close=20_040)
    pinned = (start + timedelta(minutes=2, seconds=30)).timestamp()
    result = repair_next_hole(
        tmp_path,
        symbol="MES",
        fetcher=lambda _start, _end: [first, clash],
        now=pinned,
    )
    assert result["reason"] == "filled"
    assert result["added"] == 1
    assert result["refused"] == 1
    assert load_minutes(tmp_path, "MES")[1].close_ticks == 20_000


@pytest.mark.unit
def test_a_halt_bar_and_a_bar_outside_the_hole_are_dropped(tmp_path: Path) -> None:
    left = datetime(2026, 10, 6, 18, 0, tzinfo=ET)
    right = datetime(2026, 10, 6, 18, 10, tzinfo=ET)
    _store(tmp_path, left)
    _store(tmp_path, right)
    halt = datetime(2026, 10, 6, 17, 30, tzinfo=ET)
    recovered = datetime(2026, 10, 6, 18, 5, tzinfo=ET)
    outside = right + timedelta(minutes=5)
    result = repair_next_hole(
        tmp_path,
        symbol="MES",
        fetcher=lambda _start, _end: [_bar(halt), _bar(recovered), _bar(outside)],
        now=(right + timedelta(seconds=30)).timestamp(),
    )
    assert result["added"] == 1
    stamps = [bar.ts_ns for bar in load_minutes(tmp_path, "MES")]
    assert _ns(recovered) in stamps
    assert _ns(halt) not in stamps
    assert _ns(outside) not in stamps


@pytest.mark.unit
def test_a_long_hole_is_asked_three_hours_at_a_time(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 14, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=200))
    seen: dict[str, int] = {}

    def fetch(begin: int, end: int) -> list[MinuteBar]:
        seen["span"] = end - begin
        return []

    repair_next_hole(tmp_path, symbol="MES", fetcher=fetch, now=1_000.0)
    assert seen["span"] == 180 * MINUTE_NS


@pytest.mark.unit
def test_synthetic_bars_are_not_a_market_hole(tmp_path: Path) -> None:
    append_minute(
        tmp_path,
        "MES",
        ts_ns=60 * 1_000_000_000,
        open_px=5000.0,
        high_px=5000.25,
        low_px=4999.75,
        close_px=5000.0,
        volume=1,
        market_open=True,
    )
    append_minute(
        tmp_path,
        "MES",
        ts_ns=180 * 1_000_000_000,
        open_px=5000.0,
        high_px=5000.25,
        low_px=4999.75,
        close_px=5000.0,
        volume=1,
        market_open=True,
    )

    def fetch(_start: int, _end: int) -> list[MinuteBar]:
        raise AssertionError("synthetic gap must not be fetched")

    result = repair_next_hole(tmp_path, symbol="MES", fetcher=fetch)
    assert result["reason"] == "no_hole"


@pytest.mark.unit
def test_an_unreachable_slice_does_not_block_the_next_hole(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=2))
    _store(tmp_path, start + timedelta(minutes=10))
    asked: list[int] = []

    def fetch(begin: int, _end: int) -> list[MinuteBar] | None:
        asked.append(begin)
        return None

    pinned = (start + timedelta(minutes=10, seconds=30)).timestamp()
    first = repair_next_hole(tmp_path, symbol="MES", fetcher=fetch, now=pinned)
    second = repair_next_hole(tmp_path, symbol="MES", fetcher=fetch, now=pinned + 10)
    assert first["reason"] == "nt_unreachable"
    assert second["reason"] == "nt_unreachable"
    assert asked[0] == _ns(start + timedelta(minutes=1))
    assert asked[1] == _ns(start + timedelta(minutes=3))


@pytest.mark.unit
def test_repair_does_not_touch_a_scored_name(tmp_path: Path) -> None:
    start = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
    _store(tmp_path, start)
    _store(tmp_path, start + timedelta(minutes=2))
    book = tmp_path / "reports" / "playground_learning_book"
    book.mkdir(parents=True)
    names = book / "names.jsonl"
    names.write_text('{"name":"kept","status":"buried"}\n', encoding="utf-8")
    before = names.read_bytes()
    repair_next_hole(
        tmp_path,
        symbol="MES",
        fetcher=lambda _s, _e: [_bar(start + timedelta(minutes=1))],
        now=(start + timedelta(minutes=2, seconds=30)).timestamp(),
    )
    assert names.read_bytes() == before
