"""ADR-0056 research kit. Budget, first sentences, one hand, no policy order."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.market.minute_bars import MinuteBar
from lumina_core.maturity.playground.learning_book import LearningBookError, load_names
from lumina_core.maturity.playground.research_kit import (
    coloring_hand,
    draw_first_sentences,
    hand_order,
    note_forward_outcome,
    score_period,
    select_hand,
    sim_qty,
    write_period,
)
from lumina_core.maturity.playground.school_days import green_day_streak
from lumina_core.maturity.playground.shadow_promote import living_override_side, promote_if_proven


def _now() -> datetime:
    return datetime(2026, 10, 4, 21, 0, tzinfo=timezone.utc)


def _period(root: Path, budget: int = 2) -> None:
    write_period(
        root,
        period_id="2026-W40",
        budget=budget,
        seed=7,
        cutoff_ns=10_000,
        tape_count=100,
        tail_start_ns=8_000,
        tail_end_ns=9_000,
        now=_now(),
    )


def _bars(n: int, start: int = 1) -> tuple[MinuteBar, ...]:
    return tuple(
        MinuteBar(ts_ns=index, open_ticks=20_000, high_ticks=20_010, low_ticks=19_990, close_ticks=20_000 + (index % 5), volume=1)
        for index in range(start, start + n)
    )


@pytest.mark.unit
def test_weekend_draws_and_the_halt_does_not(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.research_kit import on_school_clock

    from lumina_core.maturity.playground.progress import save_playground_progress

    save_playground_progress(tmp_path, {"chart_listing": "MES DEC26"})
    _period(tmp_path, 1)
    halt = datetime(2026, 10, 5, 21, 30, tzinfo=timezone.utc)  # Monday 17:30 ET
    closed = on_school_clock(tmp_path, now=halt)
    assert closed["reason"] == "closed_draw"
    names = load_names(tmp_path)
    lengths = {int(row["sentence"]["bar_minutes"]) for row in names if isinstance(row.get("sentence"), dict)}
    assert 1 in lengths and 1440 in lengths
    assert len(names) == 1440 * 3
    compares = {row["sentence"]["compare"] for row in names}
    assert compares == {"return", "range_pos", "volatility"}
    assert all(row["status"] == "lab" for row in names)
    weekend = datetime(2026, 10, 4, 16, 0, tzinfo=timezone.utc)  # Sunday 12:00 ET
    again = on_school_clock(tmp_path, now=weekend)
    assert again["reason"] == "weekend_draw"
    assert again["drawn"] == 0
    assert len(load_names(tmp_path)) == 1440 * 3


@pytest.mark.unit
def test_budget_above_one_keeps_a_slot_for_a_child(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.research_kit import mutate_children

    _period(tmp_path, 2)
    first = draw_first_sentences(tmp_path, "2026-W40", symbol="MES", now=_now())
    children = mutate_children(tmp_path, "2026-W40", symbol="MES", now=_now())
    assert len(first) == 1
    assert len(children) == 1
    assert children[0]["parent"] == first[0]["name"]
    assert children[0]["sentence"] != first[0]["sentence"]


def test_missing_budget_does_not_draw(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        draw_first_sentences(tmp_path, "2026-W40", symbol="MES", now=_now())


@pytest.mark.unit
def test_budget_cannot_change_after_a_program(tmp_path: Path) -> None:
    _period(tmp_path, 1)
    draw_first_sentences(tmp_path, "2026-W40", symbol="MES", now=_now())
    with pytest.raises(LearningBookError):
        write_period(
            tmp_path,
            period_id="2026-W40",
            budget=5,
            seed=7,
            cutoff_ns=10_000,
            tape_count=100,
            tail_start_ns=8_000,
            tail_end_ns=9_000,
            now=_now(),
        )


@pytest.mark.unit
def test_first_sentences_are_seeded_and_have_no_template(tmp_path: Path) -> None:
    _period(tmp_path, 2)
    first = draw_first_sentences(tmp_path, "2026-W40", symbol="MES", now=_now())
    again_root = tmp_path / "other"
    _period(again_root, 2)
    second = draw_first_sentences(again_root, "2026-W40", symbol="MES", now=_now())
    assert [row["sentence"] for row in first] == [row["sentence"] for row in second]
    assert all(row["parent"] == "" for row in first)
    blob = str(first).lower()
    assert "fibonacci" not in blob
    assert "'h1'" not in blob


@pytest.mark.unit
def test_policy_override_does_not_choose_a_side(tmp_path: Path) -> None:
    assert living_override_side(tmp_path) is None
    assert promote_if_proven(tmp_path)["reason"] == "search_retired"


@pytest.mark.unit
def test_no_hand_means_no_order_and_no_green_day(tmp_path: Path) -> None:
    assert hand_order(tmp_path, symbol="MES", price=5000.0, equity=50_000.0, now_ns=10) is None
    assert coloring_hand(tmp_path) is None
    assert green_day_streak(tmp_path) == 0
    assert sim_qty("MES", price=5000.0, stop_pct=0.002, equity=None) is None


@pytest.mark.unit
def test_fill_on_the_signal_bar_is_refused(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        note_forward_outcome(tmp_path, name="P", signal_close_ns=10, fill_ns=10, net_r=0.1, reason="target")


@pytest.mark.unit
def test_score_without_policy_baseline_does_not_bury(tmp_path: Path) -> None:
    _period(tmp_path, 1)
    draw_first_sentences(tmp_path, "2026-W40", symbol="MES", now=_now())
    scored = score_period(
        tmp_path,
        "2026-W40",
        _bars(40, start=1) + _bars(40, start=8000),
        symbol="MES",
        policy_replay_mean_r=None,
    )
    assert scored["reason"] == "policy_baseline_missing"
    assert load_names(tmp_path)[-1]["status"] == "lab"


@pytest.mark.unit
def test_one_hand_uses_the_earliest_freeze(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.learning_book import append_name, append_outcome

    append_name(
        tmp_path,
        {
            "name": "b",
            "parent": "a",
            "freeze_stamp": "2026-10-04T22:00:00+00:00",
            "status": "forward",
            "forward_bar": 30,
            "sentence": {"side": 1, "stop_pct": 0.001, "target_pct": 0.001, "hold": 20},
        },
    )
    append_name(
        tmp_path,
        {
            "name": "a",
            "parent": "",
            "freeze_stamp": "2026-10-04T21:00:00+00:00",
            "status": "forward",
            "forward_bar": 30,
            "sentence": {"side": -1, "stop_pct": 0.001, "target_pct": 0.001, "hold": 20},
        },
    )
    for name in ("a", "b"):
        for index in range(30):
            append_outcome(
                tmp_path,
                {"name": name, "signal_close_ns": index + 1, "fill_ns": index + 2, "net_r": 0.2, "reason": "target"},
            )
    chosen = select_hand(tmp_path, book_open_ns=50, flat=True, market_shut=False)
    assert chosen is None
    assert hand_order(tmp_path, symbol="MES", price=5000.0, equity=100_000.0, now_ns=50) is None
    assert select_hand(tmp_path, book_open_ns=60, flat=False, market_shut=False) is None


@pytest.mark.unit
def test_a_passed_flag_without_rows_does_not_promote(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.rule_exam import exam_dir

    path = exam_dir(tmp_path)
    path.mkdir(parents=True)
    (path / "a.json").write_text('{"schema": "playground_rule_exam_v1", "passed": true}\n', encoding="utf-8")
    from lumina_core.maturity.playground.rule_exam import rule_exam_passed

    assert rule_exam_passed(tmp_path, "a", {"window": 2, "side": 1}, "MES") is False
