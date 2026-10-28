"""Sense lab: closed candles, shadows, no tape, flat is not a crawl."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.maturity.playground.habitat import live_occupancy, write_occupancy
from lumina_core.maturity.playground.journal import experiment_path
from lumina_core.maturity.playground.sense_candles import closed_candles, slope_sign
from lumina_core.maturity.playground.sense_clock import flat_clock_message
from lumina_core.maturity.playground.sense_lab import (
    ALL_FLAT_BARS,
    net_r_after_cost,
    observe_closed_bar,
    summarize_book,
)
from lumina_core.maturity.playground.sense_slots import classify_eyes
from lumina_core.maturity.playground.tape import tape_path

GEO = {"stop_pct": 0.01, "target_pct": 0.02, "hold_bars": 20}
ROOT = Path(__file__).resolve().parents[2]
SENSE_SRC = (ROOT / "lumina_core" / "maturity" / "playground" / "sense_lab.py").read_text(encoding="utf-8")


def _minute(start: datetime, i: int) -> str:
    return (start + timedelta(minutes=i)).isoformat()


def _bars(start: datetime, prices: list[float]) -> list[dict[str, float | str]]:
    return [{"ts": _minute(start, i), "px": px} for i, px in enumerate(prices)]


@pytest.mark.unit
def test_forming_higher_timeframe_is_not_a_feature() -> None:
    start = datetime(2026, 10, 1, 13, 0, tzinfo=timezone.utc)
    prices = [100.0 + i for i in range(240)]
    bars = _bars(start, prices)
    assert closed_candles(bars, span_min=240) == []
    bars.append({"ts": _minute(start, 240), "px": 999.0})
    closed = closed_candles(bars, span_min=240)
    assert len(closed) == 1
    assert float(closed[0]["close"]) == pytest.approx(100.0 + 239)
    assert slope_sign(bars, span_min=240) is None


@pytest.mark.unit
def test_five_minute_sign_uses_two_closed_buckets_only() -> None:
    start = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    one_closed = [100.0] * 5 + [110.0]
    assert slope_sign(_bars(start, one_closed), span_min=5) is None
    rising = [100.0] * 5 + [110.0] * 5 + [120.0]
    assert slope_sign(_bars(start, rising), span_min=5) == 1


@pytest.mark.unit
def test_native_htf_does_not_crash_or_bucket_1m(tmp_path: Path) -> None:
    start = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    observe_closed_bar(
        tmp_path,
        ts=_minute(start, 0),
        close=100.0,
        decision={"side": 1, "action0": 0.7},
        geometry=GEO,
        native_htf={"5m": [100.0, 101.0], "60m": [100.0, 101.0], "240m": [100.0, 101.0]},
    )
    saved = json.loads((tmp_path / "state" / "lumina_playground_sense.json").read_text(encoding="utf-8"))
    assert saved["signs"] == {"m5": 1, "m60": 1, "m240": 1}
    observe_closed_bar(
        tmp_path,
        ts=_minute(start, 1),
        close=103.0,
        decision={"side": 1, "action0": 0.7},
        geometry=GEO,
        native_htf={},
    )
    saved = json.loads((tmp_path / "state" / "lumina_playground_sense.json").read_text(encoding="utf-8"))
    assert saved["signs"] == {"m5": None, "m60": None, "m240": None}


@pytest.mark.unit
def test_shadow_does_not_write_the_tape_and_stays_inconclusive(tmp_path: Path) -> None:
    assert "append_tape_row" not in SENSE_SRC
    assert "place_order(" not in SENSE_SRC
    start = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    observe_closed_bar(
        tmp_path,
        ts=_minute(start, 0),
        close=100.0,
        decision={"side": 0, "action0": 0.12},
        geometry=GEO,
    )
    observe_closed_bar(
        tmp_path,
        ts=_minute(start, 1),
        close=103.0,
        decision={"side": 0, "action0": 0.10},
        geometry=GEO,
    )
    state_path = tmp_path / "state" / "lumina_playground_sense.json"
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["pass_now"] is False
    assert not tape_path(tmp_path).exists()
    book = summarize_book(list(saved.get("resolved") or []))
    assert book["pass_now"] is False
    assert book["names"]["h1"]["verdict"] == "INCONCLUSIVE"
    assert book["names"]["null_a"]["mean_r"] == 0.0


@pytest.mark.unit
def test_stop_r_is_worse_than_minus_one_after_cost() -> None:
    scored = net_r_after_cost(entry=100.0, exit_px=99.0, side=1, stop_pct=0.01)
    assert scored is not None
    assert scored < -1.0


@pytest.mark.unit
def test_all_flat_journals_once_and_is_not_a_pass(tmp_path: Path) -> None:
    start = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    for i in range(ALL_FLAT_BARS):
        observe_closed_bar(
            tmp_path,
            ts=_minute(start, i),
            close=100.0,
            decision={"side": 0, "action0": 0.08},
            geometry=None,
        )
    text = experiment_path(tmp_path).read_text(encoding="utf-8")
    assert text.count("all_flat") == 1
    assert "not a pass" in text
    observe_closed_bar(
        tmp_path,
        ts=_minute(start, ALL_FLAT_BARS),
        close=100.0,
        decision={"side": 0, "action0": 0.08},
        geometry=None,
    )
    again = experiment_path(tmp_path).read_text(encoding="utf-8")
    assert again.count("## ") == text.count("## ")


@pytest.mark.unit
def test_running_clock_says_flat_instead_of_crawling(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.maturity.continuum import mark_phase_completed
    from lumina_core.maturity.playground.progress import merge_playground_progress
    import lumina_core.maturity.playground.runner as runner_mod
    from lumina_core.maturity.playground.runner import run_playground_live
    from lumina_core.maturity.playground.sense_lab import load_sense, save_sense

    monkeypatch.setattr(
        "lumina_core.maturity.playground.runner.ensure_portfolio_seal",
        lambda _root: "",
    )
    for phase in ("genesis", "birth", "awakening"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps(
            {
                "sealed": True,
                "daily_loss_cap": -1000.0,
                "max_total_open_risk": 1000.0,
                "floor_basis": "cash",
                "cash": 50000.0,
            }
        ),
        encoding="utf-8",
    )
    merge_playground_progress(tmp_path, {"deck_live": True})
    sense = load_sense(tmp_path)
    sense["audit_verdict"] = "thin"
    sense["decision_bars"] = 4
    sense["flat_bars"] = 4
    sense["last_action0"] = 0.12
    save_sense(tmp_path, sense)
    calls = {"n": 0}
    seen: list[str] = []
    real_write = runner_mod.write_phase_progress

    def spy(workspace_root: Path, phase: str, **kwargs: object) -> None:
        text = kwargs.get("message")
        if isinstance(text, str):
            seen.append(text)
        real_write(workspace_root, phase, **kwargs)

    monkeypatch.setattr(runner_mod, "write_phase_progress", spy)

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    result = run_playground_live(tmp_path, should_stop=stop, poll_sec=0.0, sleep_fn=lambda _s: None)
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    assert any("kiest plat" in line and "Crawling" not in line for line in seen)


@pytest.mark.unit
def test_existing_flat_crawl_is_journaled_once(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.sense_clock import (
        playground_flat_line,
        recognize_existing_flat_book,
    )

    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_playground_crawl.json").write_text(
        json.dumps({"total_bars": 500, "flat_bars": 500, "position_side": 0}),
        encoding="utf-8",
    )
    recognize_existing_flat_book(tmp_path)
    recognize_existing_flat_book(tmp_path)
    text = experiment_path(tmp_path).read_text(encoding="utf-8")
    assert text.count("all_flat") == 1
    assert "not a pass" in text
    assert not tape_path(tmp_path).exists()
    line = playground_flat_line(tmp_path, n_p=0)
    assert line is not None
    assert "Crawling" not in line
    assert "Geen pass" in line


@pytest.mark.unit
def test_flat_clock_names_the_hold() -> None:
    line = flat_clock_message(
        {"decision_bars": 12, "flat_bars": 12, "last_action0": 0.12},
        n_p=0,
    )
    assert line is not None
    assert "Crawling" not in line
    assert "Geen stall" in line
    assert flat_clock_message({"decision_bars": 12, "flat_bars": 3, "last_action0": 0.9}, n_p=1) is None


@pytest.mark.unit
def test_occupancy_without_decision_bars_is_missing(tmp_path: Path) -> None:
    write_occupancy(tmp_path, flat_bars=0, total_bars=0)
    assert live_occupancy(tmp_path) is None
    path = tmp_path / "state" / "lumina_playground_occupancy.json"
    path.write_text(json.dumps({"occupancy": 1.0, "total_bars": 0}), encoding="utf-8")
    assert live_occupancy(tmp_path) is None
    write_occupancy(tmp_path, flat_bars=10, total_bars=10)
    assert live_occupancy(tmp_path) == pytest.approx(1.0)


@pytest.mark.unit
def test_eye_verdict_is_blind_when_exam_bible_slot_is_empty() -> None:
    live = [[0.0] * 43]
    live[0][0] = 7700.0
    assert (
        classify_eyes(
            live=live,
            reference_closes=[],
            reference_slopes=[],
            exam_bible_session=1.0,
            exam_bible_mtf=-1.0,
        )
        == "blind"
    )


@pytest.mark.unit
def test_eye_verdict_does_not_call_a_missing_reference_matched() -> None:
    live = [[0.0] * 43 for _ in range(20)]
    for row in live:
        row[0] = 7700.0
        row[26] = 1.0
        row[27] = -1.0
        row[38] = -0.01
    assert (
        classify_eyes(
            live=live,
            reference_closes=[7700.0],
            reference_slopes=[-0.01],
            exam_bible_session=1.0,
            exam_bible_mtf=-1.0,
        )
        == "reference_missing"
    )
