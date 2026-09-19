"""Living Playground clock — incomplete is not failed; no deck stamp; REAL halt."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed, mark_phase_running
from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress
from lumina_core.maturity.playground.runner import run_playground_live
from lumina_core.maturity.playground.surface import playground_habitat_wanted


def _prior(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])


@pytest.mark.unit
def test_live_clock_incomplete_is_not_failed(tmp_path: Path) -> None:
    _prior(tmp_path)
    result = run_playground_live(
        tmp_path,
        should_stop=lambda: True,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
    )
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    rec = (load_continuum(tmp_path).get("phase_records") or {}).get("playground") or {}
    assert rec.get("status") != "failed"


@pytest.mark.unit
def test_heartbeat_writes_activity(tmp_path: Path) -> None:
    _prior(tmp_path)
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    run_playground_live(tmp_path, should_stop=stop, poll_sec=0.0, sleep_fn=lambda _s: None)
    prog = load_playground_progress(tmp_path)
    assert prog.get("activity") == "session_watch"
    assert prog.get("updated_at")
    assert prog.get("deck_live") is not True


@pytest.mark.unit
def test_runner_does_not_stamp_deck_live(tmp_path: Path) -> None:
    _prior(tmp_path)
    run_playground_live(
        tmp_path, should_stop=lambda: True, poll_sec=0.0, sleep_fn=lambda _s: None
    )
    assert load_playground_progress(tmp_path).get("deck_live") is not True


@pytest.mark.unit
def test_real_mode_halts(tmp_path: Path) -> None:
    _prior(tmp_path)
    (tmp_path / "config.yaml").write_text("mode: real\n", encoding="utf-8")
    result = run_playground_live(
        tmp_path, should_stop=lambda: False, poll_sec=0.0, sleep_fn=lambda _s: None
    )
    assert result["ok"] is False
    assert result.get("stop_reason") == "mode_not_sim=real"
    assert "REAL" in str(result.get("next_step") or "")


@pytest.mark.unit
def test_stall_retries_exhaust_when_n_p_flat(tmp_path: Path) -> None:
    _prior(tmp_path)
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True}), encoding="utf-8"
    )
    merge_playground_progress(tmp_path, {"deck_live": True, "occupancy": 0.40})
    result = run_playground_live(
        tmp_path,
        should_stop=lambda: False,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
        max_stall_retries=3,
    )
    assert result["ok"] is False
    assert result.get("stop_reason") == "stall_retries_exhausted"


@pytest.mark.unit
def test_occupancy_crash_stalls(tmp_path: Path) -> None:
    _prior(tmp_path)
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True}), encoding="utf-8"
    )
    merge_playground_progress(tmp_path, {"deck_live": True, "occupancy": 0.10})
    result = run_playground_live(
        tmp_path,
        should_stop=lambda: False,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
        max_stall_retries=3,
    )
    assert result["ok"] is False
    assert result.get("stop_reason") == "stall_retries_exhausted"


@pytest.mark.unit
def test_habitat_wanted_when_running(tmp_path: Path) -> None:
    _prior(tmp_path)
    mark_phase_running(tmp_path, "playground", learned={"status": "starting"})
    wanted, why = playground_habitat_wanted(tmp_path)
    assert wanted is True
    assert why == "playground_running"


@pytest.mark.unit
def test_habitat_not_wanted_before_start(tmp_path: Path) -> None:
    _prior(tmp_path)
    wanted, why = playground_habitat_wanted(tmp_path)
    assert wanted is False
    assert why == "playground_pending"
