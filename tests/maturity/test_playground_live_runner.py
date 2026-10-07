"""Living Playground clock — incomplete is not failed; no deck stamp; REAL halt.

A flat n_P on a poll is not a stall. Three short windows halt only when a
real fault is injected. Production windows stay 30 minutes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed, mark_phase_running
from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress
from lumina_core.maturity.playground.runner import run_playground_live
from lumina_core.maturity.playground.surface import playground_habitat_wanted


@pytest.fixture(autouse=True)
def _no_live_account_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.maturity.playground.runner.ensure_portfolio_seal",
        lambda _root: "",
    )


def _prior(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])


def _arm_sim(tmp_path: Path) -> None:
    """Numeric SIM seal plus deck_live. A boolean seal stays waiting_operator."""
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
                "account_name": "DEMO5042070",
            }
        ),
        encoding="utf-8",
    )
    merge_playground_progress(tmp_path, {"deck_live": True})


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
def test_flat_n_p_poll_is_not_a_stall(tmp_path: Path) -> None:
    _prior(tmp_path)
    _arm_sim(tmp_path)
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 4

    result = run_playground_live(
        tmp_path,
        should_stop=stop,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
        stall_window_sec=0.0,
    )
    assert result["ok"] is False
    assert result.get("stop_reason") == "stop_requested"
    assert int(load_playground_progress(tmp_path).get("stall_windows") or 0) == 0


@pytest.mark.unit
def test_occupancy_without_sample_is_not_a_stall(tmp_path: Path) -> None:
    _prior(tmp_path)
    _arm_sim(tmp_path)
    merge_playground_progress(tmp_path, {"occupancy": 0.10})
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 4

    result = run_playground_live(
        tmp_path,
        should_stop=stop,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
        stall_window_sec=0.0,
    )
    assert result.get("stop_reason") == "stop_requested"
    assert int(load_playground_progress(tmp_path).get("stall_windows") or 0) == 0


@pytest.mark.unit
def test_nt_down_windows_halt(tmp_path: Path) -> None:
    _prior(tmp_path)
    _arm_sim(tmp_path)
    (tmp_path / "state" / "fabric_sim_health.json").write_text(
        json.dumps({"ok": False}),
        encoding="utf-8",
    )
    result = run_playground_live(
        tmp_path,
        should_stop=lambda: False,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
        stall_window_sec=0.0,
    )
    assert result["ok"] is False
    assert result.get("stop_reason") == "stall_windows_exhausted"


@pytest.mark.unit
def test_occupancy_crash_after_sample_halts(tmp_path: Path) -> None:
    _prior(tmp_path)
    _arm_sim(tmp_path)
    state = tmp_path / "state"
    (state / "lumina_playground_occupancy.json").write_text(
        json.dumps({"flat_bars": 50, "total_bars": 500, "occupancy": 0.10}),
        encoding="utf-8",
    )
    (state / "lumina_playground_crawl.json").write_text(
        json.dumps({"total_bars": 500, "flat_bars": 50}),
        encoding="utf-8",
    )
    result = run_playground_live(
        tmp_path,
        should_stop=lambda: False,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
        stall_window_sec=0.0,
    )
    assert result["ok"] is False
    assert result.get("stop_reason") == "stall_windows_exhausted"


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
