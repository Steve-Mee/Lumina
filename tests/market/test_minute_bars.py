"""ADR-0056 bar archive. No drop, no mismatch, no append while shut."""
from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.market.minute_bars import BarArchiveError, MinuteBar, append_minute, load_minutes, stitch_front


def _bar(root: Path, ts: int, *, price: float = 5000.0, open_book: bool = True) -> None:
    append_minute(
        root,
        "MES",
        ts_ns=ts,
        open_px=price,
        high_px=price + 0.25,
        low_px=price - 0.25,
        close_px=price,
        volume=1,
        market_open=open_book,
    )


@pytest.mark.unit
def test_archive_keeps_every_minute(tmp_path: Path) -> None:
    for index in range(1, 50):
        _bar(tmp_path, index * 60 * 1_000_000_000, price=5000.0 + index * 0.25)
    assert len(load_minutes(tmp_path, "MES")) == 49


@pytest.mark.unit
def test_shut_book_appends_nothing(tmp_path: Path) -> None:
    with pytest.raises(BarArchiveError):
        _bar(tmp_path, 60 * 1_000_000_000, open_book=False)
    assert load_minutes(tmp_path, "MES") == ()


@pytest.mark.unit
def test_same_timestamp_must_match(tmp_path: Path) -> None:
    _bar(tmp_path, 60 * 1_000_000_000, price=5000.0)
    _bar(tmp_path, 60 * 1_000_000_000, price=5000.0)
    with pytest.raises(BarArchiveError):
        _bar(tmp_path, 60 * 1_000_000_000, price=5001.0)
    assert len(load_minutes(tmp_path, "MES")) == 1


@pytest.mark.unit
def test_stitch_keeps_every_row_and_refuses_a_mismatch(tmp_path: Path) -> None:
    _bar(tmp_path, 120 * 1_000_000_000, price=5000.0)
    older = MinuteBar(60 * 1_000_000_000, 20_000, 20_001, 19_999, 20_000, 1)
    assert stitch_front(tmp_path, "MES", (older,)) == 1
    assert len(load_minutes(tmp_path, "MES")) == 2
    clash = MinuteBar(120 * 1_000_000_000, 20_000, 20_001, 19_999, 20_004, 1)
    with pytest.raises(BarArchiveError):
        stitch_front(tmp_path, "MES", (clash,))
    assert len(load_minutes(tmp_path, "MES")) == 2
