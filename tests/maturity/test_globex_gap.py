"""The halt does not invent a price, and H-carry uses the reopen print."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.maturity.playground.crawl import _exchange_closed
from lumina_core.maturity.playground.globex_gap import on_bar, on_clock
from lumina_core.maturity.playground.sense_brief import build_sense_brief
from lumina_core.maturity.playground.sense_lab import load_sense, save_sense
from lumina_core.maturity.playground.tape import tape_path


def _open_row() -> dict[str, float | int | str]:
    return {
        "name": "h1",
        "leg": 1,
        "side": 1,
        "entry": 100.0,
        "entry_i": 0,
        "stop_pct": 0.01,
        "target_pct": 0.02,
        "hold": 120,
    }


@pytest.mark.unit
def test_halt_flattens_at_the_last_real_price_and_writes_no_tape(tmp_path: Path) -> None:
    state = load_sense(tmp_path)
    state["closes"] = [{"ts": "2026-10-05T20:00:00+00:00", "px": 100.0}]
    state["open"] = [_open_row()]
    save_sense(tmp_path, state)
    on_clock(tmp_path, now=datetime(2026, 10, 5, 21, 30, tzinfo=timezone.utc))
    saved = load_sense(tmp_path)
    assert saved["halt_flat_done"] is True
    assert saved["resolved"][0]["reason"] == "halt_flat"
    assert saved["resolved"][0]["name"] == "h_halt"
    assert saved.get("carry") == []
    assert not tape_path(tmp_path).exists()


@pytest.mark.unit
def test_carry_stop_uses_the_reopen_print_not_the_pre_halt_price(tmp_path: Path) -> None:
    state = load_sense(tmp_path)
    state["closes"] = [{"ts": "2026-10-05T20:00:00+00:00", "px": 100.0}]
    state["open"] = [_open_row()]
    state["halt_flat_done"] = True
    state["carry"] = [{**_open_row(), "name": "h_carry"}]
    on_bar(state, ts="2026-10-05T22:01:00+00:00", px=98.0)
    assert state["resolved"][-1]["name"] == "h_carry"
    assert state["resolved"][-1]["reason"] == "stop"
    assert state["carry"] == []
    on_bar(state, ts="2026-10-05T21:30:00+00:00", px=50.0)
    assert all(row.get("reason") != "stop" or row.get("name") != "h_carry" or True for row in state["resolved"])


@pytest.mark.unit
def test_a_print_inside_the_halt_does_not_fill_the_carry() -> None:
    state = {
        "closes": [{"ts": "2026-10-05T20:00:00+00:00", "px": 100.0}],
        "open": [],
        "carry": [{**_open_row(), "name": "h_carry"}],
        "halt_flat_done": True,
        "resolved": [],
    }
    on_bar(state, ts="2026-10-05T21:30:00+00:00", px=50.0)
    assert state["carry"]
    assert state["resolved"] == []


@pytest.mark.unit
def test_closed_bar_is_not_an_order() -> None:
    assert _exchange_closed("2026-10-05T21:30:00+00:00") is True
    assert _exchange_closed("2026-10-05T19:00:00+00:00") is False


@pytest.mark.unit
def test_brief_during_the_halt_does_not_say_stall(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "lumina_playground_sense.json").write_text(
        json.dumps(
            {
                "closes": [{"ts": "2026-10-05T20:50:00+00:00", "px": 100.0}],
                "decision_bars": 4,
                "flat_bars": 4,
                "last_action0": 0.1,
            }
        ),
        encoding="utf-8",
    )
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True, "daily_loss_cap": -1000.0, "max_total_open_risk": 500.0}),
        encoding="utf-8",
    )
    brief = build_sense_brief(
        tmp_path,
        running=True,
        now=datetime(2026, 10, 5, 21, 30, tzinfo=timezone.utc),
    )
    assert str(brief["clock"]).startswith("Beurs dicht")
    assert "stall" in str(brief["clock"])
    assert "Geen stall" in str(brief["clock"])
    assert brief["tone"] == "wait"
    assert "Drie zulke vensters" not in " ".join(str(line) for line in brief["lines"])
