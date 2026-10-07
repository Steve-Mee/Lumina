"""School path. Honest archive, no hole, no invented baseline, no overnight, no flat green day."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.market.birth_minute_archive import split_search_and_tail, write_birth_minutes
from lumina_core.market.minute_bars import MinuteBar, append_minute
from lumina_core.maturity.playground.learning_book import append_name, load_names
from lumina_core.maturity.playground.research_kit import (
    advance_waiting,
    freeze_forward_span,
    hand_order,
    measured_plant_mean_r,
    note_forward_outcome,
    score_period,
    write_period,
)
from lumina_core.maturity.playground.rule_exam import attach_flat_days
from lumina_core.maturity.playground.school_days import green_day_streak
from lumina_core.maturity.playground.sentence_window import clock_open, has_open_hole, signal_on
from lumina_core.maturity.playground.session_flat import hold_crosses_halt
from lumina_core.maturity.playground.tape import append_tape_row


def _minute(hour: int, minute: int, *, day: int = 6) -> int:
    moment = datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)
    return int(moment.timestamp() * 1_000_000_000)


def _bar(ts_ns: int, close: int = 20_000) -> MinuteBar:
    return MinuteBar(ts_ns=ts_ns, open_ticks=close, high_ticks=close + 4, low_ticks=close - 4, close_ticks=close, volume=1)


@pytest.mark.unit
def test_silent_minutes_are_not_invented_and_search_stops_before_the_holdout(tmp_path: Path) -> None:
    first = "2026-07-20T14:00:00+00:00"
    second = "2026-07-20T14:01:00+00:00"
    holdout = "2026-07-26T22:01:00+00:00"
    ticks = [
        {"timestamp": first, "last": 5000.0, "volume": 3},
        {"timestamp": second, "last": 5000.25, "volume": 1},
        {"timestamp": holdout, "last": 5001.0, "volume": 2},
        {"last": 5002.0, "volume": 9},
    ]
    start = int(datetime.fromisoformat(holdout).timestamp() * 1_000_000_000)
    fact = write_birth_minutes(tmp_path, ticks, symbol="MES", holdout_start_ns=start)
    assert fact["tape_count"] == 4
    assert fact["minute_count"] == 3
    assert fact["search_minutes"] == 2
    assert fact["tail_minutes"] == 1
    from lumina_core.market.minute_bars import load_minutes

    search, tail = split_search_and_tail(load_minutes(tmp_path, "MES"), holdout_start_ns=start)
    assert all(bar.ts_ns < start for bar in search)
    assert tail and tail[0].ts_ns >= start


@pytest.mark.unit
def test_an_open_minute_hole_is_not_a_signal() -> None:
    first = _minute(15, 0)
    later = _minute(15, 2)
    bars = (_bar(first, 20_000), _bar(later, 20_008))
    assert has_open_hole(bars) is True
    sentence = {
        "bar_minutes": 1,
        "window": 2,
        "window_unit": "bars",
        "compare": "return",
        "side": 1,
        "quarter": "top",
        "vol_min": 0.001,
    }
    assert signal_on(sentence, bars, tick_size=0.25) is False


@pytest.mark.unit
def test_a_clock_can_name_a_month() -> None:
    march = int(datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    april = int(datetime(2026, 4, 10, 15, 0, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    clock = {"months": [3], "start_min": 10 * 60, "end_min": 12 * 60}
    assert clock_open(march, clock) is True
    assert clock_open(april, clock) is False


@pytest.mark.unit
def test_a_blind_observation_is_not_a_plant_mean() -> None:
    from lumina_core.maturity.playground.research_kit import replay_from_observation

    assert replay_from_observation({"drawdown": 0, "trend_slope_5": 0, "mean_r": 0.2}) is None
    assert replay_from_observation(
        {"drawdown": 1.0, "drawdown_measured": True, "trend_slope_5": 0.1, "trend_slope_measured": True, "mean_r": -0.2}
    ) == -0.2


@pytest.mark.unit
def test_a_missing_plant_book_is_not_a_zero_baseline(tmp_path: Path) -> None:
    assert measured_plant_mean_r(tmp_path) is None
    write_period(
        tmp_path,
        period_id="2026-W40",
        budget=1,
        seed=3,
        cutoff_ns=10_000,
        tape_count=4,
        tail_start_ns=8_000,
        tail_end_ns=9_000,
        now=datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc),
    )
    from lumina_core.maturity.playground.research_kit import draw_first_sentences

    draw_first_sentences(tmp_path, "2026-W40", symbol="MES", now=datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc))
    scored = score_period(
        tmp_path,
        "2026-W40",
        tuple(_bar(index) for index in range(1, 30)),
        symbol="MES",
        policy_replay_mean_r=None,
    )
    assert scored["admitted"] == []
    assert load_names(tmp_path)[-1]["status"] == "lab"


@pytest.mark.unit
def test_a_window_longer_than_the_slice_is_buried(tmp_path: Path) -> None:
    write_period(
        tmp_path,
        period_id="2026-W41",
        budget=1,
        seed=1,
        cutoff_ns=50,
        tape_count=10,
        tail_start_ns=20,
        tail_end_ns=40,
        now=datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc),
    )
    append_name(
        tmp_path,
        {
            "name": "wide",
            "parent": "",
            "status": "lab",
            "budget_id": "2026-W41",
            "cutoff_ns": 50,
            "sentence": {
                "bar_minutes": 10,
                "window": 5,
                "window_unit": "bars",
                "compare": "return",
                "side": 1,
                "stop_pct": 0.001,
                "target_pct": 0.001,
                "hold": 2,
            },
        },
    )
    bars = tuple(_bar(index) for index in range(1, 45))
    scored = score_period(tmp_path, "2026-W41", bars, symbol="MES", policy_replay_mean_r=-0.1)
    assert "wide" in scored["buried"]
    assert load_names(tmp_path)[-1]["bury_reason"] == "window_longer_than_slice"


@pytest.mark.unit
def test_a_silent_holdout_day_is_flat_zero_not_a_plant_trade() -> None:
    parent = [{"plant": False, "trade_r": 0.2, "ts_iso": "2026-07-26T15:00:00+00:00"}]
    days = {"2026-07-26", "2026-07-27"}
    booked = attach_flat_days(parent, days)
    silent = [row for row in booked if row.get("flat_day") is True]
    assert len(silent) == 1
    assert silent[0]["trade_r"] == 0.0
    assert silent[0]["plant"] is False
    assert "2026-07-27" in silent[0]["ts_iso"]


@pytest.mark.unit
def test_forward_span_cannot_move_after_the_first_result(tmp_path: Path) -> None:
    append_name(
        tmp_path,
        {
            "name": "P",
            "status": "forward",
            "forward_bar": 30,
            "sentence": {"side": 1},
        },
    )
    freeze_forward_span(tmp_path, "P", 40)
    assert load_names(tmp_path)[-1]["forward_bar"] == 40
    note_forward_outcome(tmp_path, name="P", signal_close_ns=10, fill_ns=11, net_r=0.1, reason="target")
    with pytest.raises(Exception):
        freeze_forward_span(tmp_path, "P", 80)
    assert any(row.get("name") == "P" for row in load_names(tmp_path))


@pytest.mark.unit
def test_a_hold_into_the_halt_is_refused() -> None:
    moment = datetime(2026, 10, 6, 20, 40, tzinfo=timezone.utc)
    now_ns = int(moment.timestamp() * 1_000_000_000)
    assert hold_crosses_halt(now_ns, 30) is True
    earlier = moment - timedelta(hours=5)
    assert hold_crosses_halt(int(earlier.timestamp() * 1_000_000_000), 30) is False


@pytest.mark.unit
def test_a_flat_session_is_not_green_and_a_higher_close_is(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.fills import record_policy_close

    append_name(
        tmp_path,
        {
            "name": "school",
            "status": "hand",
            "hand_since_ns": 1,
            "freeze_stamp": "2026-10-02T00:00:00+00:00",
            "forward_bar": 30,
            "sentence": {"side": 1, "stop_pct": 0.002, "target_pct": 0.004, "hold": 30},
        },
    )
    record_policy_close(
        tmp_path,
        order_id="FLAT",
        entry_px=5000.0,
        exit_px=5010.0,
        stop_px=4990.0,
        target_px=5030.0,
        side=1,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        ts="2026-10-06T15:00:00+00:00",
        rule_name="school",
    )
    row = {
        "kind": "close",
        "order_id": "MARK",
        "policy": True,
        "rule_name": "school",
        "instrument": "MES",
        "qty": 1,
        "entry_px": 5000.0,
        "exit_px": 5000.0,
        "side": 1,
        "mode": "sim",
        "source": "orderpath",
        "ts": "2026-10-06T15:05:00+00:00",
        "session_open_equity": 1000.0,
        "session_close_equity": 1000.0,
    }
    append_tape_row(tmp_path, row)
    assert green_day_streak(tmp_path) == 0


def _stamp(day: int, hour: int, minute: int, *, month: int = 6) -> int:
    moment = datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)
    return int(moment.timestamp() * 1_000_000_000)


@pytest.mark.unit
def test_a_sentence_the_tail_cannot_hold_waits(tmp_path: Path) -> None:
    cutoff = _stamp(31, 20, 0, month=7)
    tail_start = _stamp(26, 22, 0, month=7)
    write_period(
        tmp_path,
        period_id="birth-holdout",
        budget=1,
        seed=1,
        cutoff_ns=cutoff,
        tape_count=20,
        tail_start_ns=tail_start,
        tail_end_ns=cutoff,
        now=datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc),
    )
    append_name(
        tmp_path,
        {
            "name": "january-only",
            "parent": "",
            "status": "lab",
            "budget_id": "birth-holdout",
            "cutoff_ns": cutoff,
            "search_end_ns": tail_start,
            "sentence": {
                "bar_minutes": 1,
                "window": 2,
                "window_unit": "bars",
                "compare": "return",
                "side": 1,
                "stop_pct": 0.001,
                "target_pct": 0.001,
                "hold": 2,
                "clock": {"months": [1]},
            },
        },
    )
    search = tuple(_bar(_stamp(10, 15, index)) for index in range(6))
    tail = tuple(_bar(_stamp(27, 15, index, month=7)) for index in range(6))
    scored = score_period(
        tmp_path,
        "birth-holdout",
        search + tail,
        symbol="MES",
        policy_replay_mean_r=-0.1,
    )
    assert scored["waiting"] == ["january-only"]
    assert scored["buried"] == []
    assert load_names(tmp_path)[-1]["status"] == "waiting_tail"
    assert "bury_reason" not in load_names(tmp_path)[-1]


@pytest.mark.unit
def test_the_later_tail_is_sealed_once_from_the_calendar(tmp_path: Path) -> None:
    cutoff = _stamp(6, 17, 44, month=10)
    append_name(
        tmp_path,
        {
            "name": "january-only",
            "parent": "",
            "status": "waiting_tail",
            "wait_reason": "tail_cannot_hold",
            "cutoff_ns": cutoff,
            "search_end_ns": _stamp(26, 22, 1, month=7),
            "sentence": {
                "bar_minutes": 1,
                "window": 2,
                "window_unit": "bars",
                "compare": "return",
                "side": 1,
                "stop_pct": 0.001,
                "target_pct": 0.001,
                "hold": 2,
                "clock": {"months": [1]},
            },
        },
    )
    early = tuple(_bar(_stamp(6, 18, index, month=10)) for index in range(4))
    first = advance_waiting(tmp_path, early, symbol="MES")
    assert first["scored"] == 0
    sealed = load_names(tmp_path)[-1]
    assert sealed["wait_sealed"] is True
    assert int(sealed["wait_tail_start_ns"]) == cutoff
    end = int(sealed["wait_tail_end_ns"])
    later = early + (_bar(_stamp(6, 19, 0, month=10)),)
    second = advance_waiting(tmp_path, later, symbol="MES")
    assert second["scored"] == 0
    again = load_names(tmp_path)[-1]
    assert int(again["wait_tail_end_ns"]) == end
    assert [row["name"] for row in load_names(tmp_path)] == ["january-only", "january-only"]


@pytest.mark.unit
def test_the_order_uses_the_same_closed_minute(tmp_path: Path) -> None:
    first = _stamp(6, 15, 0, month=10)
    second = _stamp(6, 15, 1, month=10)
    fill = _stamp(6, 15, 2, month=10)
    append_minute(tmp_path, "MES", ts_ns=first, open_px=5000.0, high_px=5000.25, low_px=4999.75, close_px=5000.0, volume=1, market_open=True)
    append_minute(tmp_path, "MES", ts_ns=second, open_px=5001.0, high_px=5001.25, low_px=5000.75, close_px=5001.0, volume=1, market_open=True)
    append_minute(tmp_path, "MES", ts_ns=fill, open_px=5002.0, high_px=5002.25, low_px=5001.75, close_px=5002.0, volume=1, market_open=True)
    append_name(
        tmp_path,
        {
            "name": "hand-a",
            "parent": "",
            "status": "hand",
            "hand_since_ns": first,
            "sentence": {
                "bar_minutes": 1,
                "window": 2,
                "window_unit": "bars",
                "compare": "return",
                "side": 1,
                "stop_pct": 0.001,
                "target_pct": 0.001,
                "hold": 2,
            },
        },
    )
    order = hand_order(tmp_path, symbol="MES", price=5002.0, equity=50_000.0, now_ns=fill)
    assert order is not None and order.side == 1
    assert hand_order(tmp_path, symbol="MES", price=5100.0, equity=50_000.0, now_ns=fill) is None


@pytest.mark.unit
def test_a_touched_stop_fills_at_the_stop_not_the_close() -> None:
    from lumina_core.maturity.playground.research_kit import _trade_exit

    entry = _bar(_stamp(6, 15, 0, month=10), 20_000)
    touched = MinuteBar(
        ts_ns=_stamp(6, 15, 1, month=10),
        open_ticks=20_000,
        high_ticks=20_004,
        low_ticks=19_960,
        close_ticks=20_000,
        volume=1,
    )
    sentence = {
        "bar_minutes": 1,
        "window": 1,
        "side": 1,
        "stop_pct": 0.001,
        "target_pct": 0.01,
        "hold": 2,
    }
    exit_px, reason = _trade_exit(sentence, (entry, touched), 0, 0.25)
    assert reason == "stop"
    assert exit_px == pytest.approx(4995.0)
    assert exit_px != 5000.0


@pytest.mark.unit
def test_an_unasked_open_hole_is_not_scored(tmp_path: Path) -> None:
    cutoff = _stamp(31, 20, 0, month=7)
    tail_start = _stamp(26, 22, 0, month=7)
    write_period(
        tmp_path,
        period_id="birth-holdout",
        budget=1,
        seed=1,
        cutoff_ns=cutoff,
        tape_count=8,
        tail_start_ns=tail_start,
        tail_end_ns=cutoff,
        now=datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc),
    )
    append_name(
        tmp_path,
        {
            "name": "gapped",
            "parent": "",
            "status": "lab",
            "budget_id": "birth-holdout",
            "cutoff_ns": cutoff,
            "search_end_ns": tail_start,
            "sentence": {
                "bar_minutes": 1,
                "window": 2,
                "window_unit": "bars",
                "compare": "return",
                "side": 1,
                "stop_pct": 0.001,
                "target_pct": 0.001,
                "hold": 2,
            },
        },
    )
    search = (
        _bar(_stamp(10, 15, 0)),
        _bar(_stamp(10, 15, 2)),
    )
    tail = tuple(_bar(_stamp(27, 15, index, month=7)) for index in range(4))
    scored = score_period(tmp_path, "birth-holdout", search + tail, symbol="MES", policy_replay_mean_r=-0.1)
    assert scored["reason"] == "scored"
    assert scored["buried"] == []
    assert load_names(tmp_path)[-1]["status"] == "lab"
    assert load_names(tmp_path)[-1]["hole_wait"]


@pytest.mark.unit
def test_a_wait_tail_exam_does_not_borrow_the_birth_days(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.rule_exam import _sealed_tail_exam

    start = _stamp(6, 15, 0, month=10)
    bars = []
    for index in range(6):
        stamp = _stamp(6, 15, index, month=10)
        price = 5000.0 + index * 0.25
        append_minute(
            tmp_path,
            "MES",
            ts_ns=stamp,
            open_px=price,
            high_px=price + 0.25,
            low_px=price - 0.25,
            close_px=price,
            volume=1,
            market_open=True,
        )
        bars.append(stamp)
    row = {
        "wait_sealed": True,
        "wait_tail_start_ns": start,
        "wait_tail_end_ns": bars[-1] + 60_000_000_000,
    }
    sentence = {
        "bar_minutes": 1,
        "window": 2,
        "window_unit": "bars",
        "compare": "return",
        "side": 1,
        "stop_pct": 0.001,
        "target_pct": 0.001,
        "hold": 2,
    }
    assert _sealed_tail_exam(tmp_path, "january-only", sentence, "MES", row) is False
    payload = json.loads((tmp_path / "reports" / "playground_rule_exams" / "january-only.json").read_text(encoding="utf-8"))
    assert payload["exam_slice"] == "sealed_wait_tail"
    assert any(str(item).startswith("n_B=") for item in payload["reasons"])
    assert not any("paired" in str(item) for item in payload["reasons"])


@pytest.mark.unit
def test_a_shut_market_does_not_append_a_minute(tmp_path: Path) -> None:
    stamp = int(datetime(2026, 10, 6, 21, 30, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    with pytest.raises(Exception):
        append_minute(
            tmp_path,
            "MES",
            ts_ns=stamp,
            open_px=5000.0,
            high_px=5000.25,
            low_px=4999.75,
            close_px=5000.0,
            volume=1,
            market_open=False,
        )
