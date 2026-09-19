"""ADR-0051 Apprenticeship law — n_A≥150, 5 green session days, no backtest/JSON cheat."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from lumina_core.maturity.apprenticeship.days import N_D_MIN
from lumina_core.maturity.apprenticeship.heal import heal_apprenticeship_from_law
from lumina_core.maturity.apprenticeship.law import (
    N_A_MIN,
    ApprenticeshipSnapshot,
    evaluate_apprenticeship_exit,
    evaluate_apprenticeship_pass,
)
from lumina_core.maturity.apprenticeship.progress import save_apprenticeship_progress
from lumina_core.maturity.apprenticeship.tape import record_orderpath_fill
from lumina_core.maturity.apprenticeship_sim import run_apprenticeship_multi_day_sim
from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.phase_specs import evaluate_exit_proofs


def _pass_snap(**overrides: object) -> ApprenticeshipSnapshot:
    base: dict[str, object] = {
        "n_a": 160,
        "n_plant": 0,
        "n_d": 5,
        "occupancy": 0.40,
        "median_loss_r": 1.2,
        "sharpe": 0.35,
        "dd_pct": 8.0,
        "freeze_ok": True,
        "policy_only": True,
        "playground_completed": True,
        "child_sha": "aa" * 32,
        "playground_child_sha": "aa" * 32,
        "birth_sha": "bb" * 32,
        "envelope_sealed": True,
        "envelope_breached": False,
        "deck_live": True,
        "mode": "sim_real_guard",
        "recovery_ok": True,
        "risk_events": 0,
        "var_breach_count": 0,
        "daily_kill": False,
    }
    base.update(overrides)
    return ApprenticeshipSnapshot(**base)  # type: ignore[arg-type]


def _seal(root: Path) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True, "source": "test"}),
        encoding="utf-8",
    )


def _write_progress(root: Path) -> None:
    save_apprenticeship_progress(
        root,
        {
            "occupancy": 0.40,
            "freeze_ok": True,
            "child_sha": "aa" * 32,
            "playground_child_sha": "aa" * 32,
            "birth_sha": "bb" * 32,
            "deck_live": True,
            "mode": "sim_real_guard",
            "envelope_breached": False,
            "recovery_ok": True,
            "risk_events": 0,
            "var_breach_count": 0,
            "daily_kill": False,
        },
    )


def _session_days(n: int) -> list[str]:
    start = date(2026, 9, 14)  # Monday
    out: list[str] = []
    cursor = start
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return out


def _write_closes(root: Path, *, days: int, per_day: int, pnl_by_day: list[float] | None = None) -> None:
    sessions = _session_days(days)
    pnls = pnl_by_day or [20.0 + float(i) for i in range(days)]
    idx = 0
    for d_i, session in enumerate(sessions):
        day_pnl = pnls[d_i] if d_i < len(pnls) else 20.0
        per = max(1, per_day)
        piece = day_pnl / float(per)
        for j in range(per):
            r = 0.20 if j % 3 else -0.10
            record_orderpath_fill(
                root,
                order_id=f"SIM-{idx}",
                fill_px=5000.0,
                qty=1,
                instrument="MES",
                mode="sim_real_guard",
                source="orderpath",
                kind="close",
                policy=True,
                r=r,
                win=r > 0,
                pnl=piece,
                session_date=session,
            )
            idx += 1


def _write_pass_workspace(root: Path, *, days: int = 5, per_day: int = 32) -> None:
    _seal(root)
    _write_progress(root)
    for phase in ("genesis", "birth", "awakening", "playground"):
        mark_phase_completed(root, phase, learned={}, exit_proofs=["x"])
    _write_closes(root, days=days, per_day=per_day)


@pytest.mark.unit
def test_n_a_below_150_is_inconclusive() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(n_a=N_A_MIN - 1))
    assert result.passed is False
    assert result.clock_open is True
    assert any(f"n_A={N_A_MIN - 1}" in b for b in result.blockers)


@pytest.mark.unit
def test_four_green_days_cannot_pass() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(n_d=N_D_MIN - 1))
    assert result.passed is False
    assert any(f"n_D={N_D_MIN - 1}" in b for b in result.blockers)


@pytest.mark.unit
def test_full_and_passes() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap())
    assert result.passed is True
    assert "risk_discipline" in result.proofs
    assert "n_D>=5" in result.proofs
    assert "constitution_0" in result.proofs


@pytest.mark.unit
def test_sim_mode_is_not_apprenticeship() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(mode="sim"))
    assert result.passed is False
    assert any("mode_not_sim_real_guard" in b for b in result.blockers)


@pytest.mark.unit
def test_real_mode_fails() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(mode="real"))
    assert result.passed is False
    assert "constitution_violated" in result.blockers


@pytest.mark.unit
def test_sharpe_below_floor_cannot_pass() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(sharpe=0.19))
    assert result.passed is False
    assert any("sharpe=" in b for b in result.blockers)


@pytest.mark.unit
def test_dd_above_12_cannot_pass() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(dd_pct=12.01))
    assert result.passed is False
    assert any("dd=" in b for b in result.blockers)


@pytest.mark.unit
def test_missing_sharpe_cannot_pass() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(sharpe=None))
    assert result.passed is False


@pytest.mark.unit
def test_constitution_event_fails() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(risk_events=1))
    assert result.passed is False
    assert "constitution_violated" in result.blockers


@pytest.mark.unit
def test_soft_complete_cannot_set_ok() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(n_a=1, n_d=0, recovery_ok=False))
    assert result.passed is False


@pytest.mark.unit
def test_freeze_and_child_gates() -> None:
    frozen = evaluate_apprenticeship_pass(_pass_snap(freeze_ok=False))
    assert frozen.passed is False
    swapped = evaluate_apprenticeship_pass(_pass_snap(child_sha="cc" * 32))
    assert swapped.passed is False
    same_as_birth = evaluate_apprenticeship_pass(
        _pass_snap(child_sha="bb" * 32, playground_child_sha="bb" * 32)
    )
    assert same_as_birth.passed is False


@pytest.mark.unit
def test_playground_not_completed_blocks() -> None:
    result = evaluate_apprenticeship_pass(_pass_snap(playground_completed=False))
    assert result.passed is False
    assert "playground_not_completed" in result.blockers


@pytest.mark.unit
def test_backtest_bridge_writes_nothing(tmp_path: Path) -> None:
    out = run_apprenticeship_multi_day_sim(tmp_path, days=5)
    assert out["ok"] is False
    assert out["reason"] == "backtest_is_not_a_session_day"
    assert out["days_written"] == 0
    runs = tmp_path / "state" / "test_runs"
    assert not runs.exists() or list(runs.glob("apprenticeship_sim_day_*.json")) == []


@pytest.mark.unit
def test_json_day_files_are_not_session_days(tmp_path: Path) -> None:
    runs = tmp_path / "state" / "test_runs"
    runs.mkdir(parents=True)
    (runs / "apprenticeship_sim_day_2026-09-14.json").write_text(
        json.dumps({"mode": "sim", "pnl_realized": 50.0, "total_trades": 10, "sharpe_annualized": 1.2}),
        encoding="utf-8",
    )
    _write_progress(tmp_path)
    ok, missing, _ = evaluate_apprenticeship_exit(tmp_path)
    assert ok is False
    assert any("n_A=" in m or "n_D=" in m or "playground" in m for m in missing)


@pytest.mark.unit
def test_sim_fill_rejected_on_apprenticeship_tape(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=5000.0,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        kind="close",
    )
    assert rec["ok"] is False
    assert rec["reason"] == "mode_not_sim_real_guard"


@pytest.mark.unit
def test_health_source_rejected(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=1.0,
        qty=1,
        instrument="MES",
        mode="sim_real_guard",
        source="fabric_health",
    )
    assert rec["ok"] is False


@pytest.mark.unit
def test_workspace_n_a_149_inconclusive(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, days=5, per_day=29)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "apprenticeship")
    assert ok is False
    assert any("n_A=" in m for m in missing)
    assert learned.get("pass_now") is False


@pytest.mark.unit
def test_workspace_four_days_inconclusive(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, days=4, per_day=40)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "apprenticeship")
    assert ok is False
    assert any("n_D=" in m for m in missing)
    assert learned.get("clock_open") is True


@pytest.mark.unit
def test_workspace_full_and_passes(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, days=5, per_day=32)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "apprenticeship")
    assert ok is True, missing
    assert missing == []
    assert learned.get("pass_now") is True
    assert "risk_discipline" in (learned.get("exit_proofs") or [])


@pytest.mark.unit
def test_milestone_stamp_without_tape_cannot_pass(tmp_path: Path) -> None:
    from lumina_core.maturity.maturation_progress import record_maturation_milestone

    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=["x"])
    record_maturation_milestone(tmp_path, "sim_real_guard_stable", metadata={"cheat": True})
    ok, missing, _ = evaluate_exit_proofs(tmp_path, "apprenticeship")
    assert ok is False
    assert missing


@pytest.mark.unit
def test_heal_reopens_false_stamp(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(tmp_path, phase, learned={"soft": True}, exit_proofs=["stamp"])
    result = heal_apprenticeship_from_law(tmp_path)
    assert result["healed"] is True
    data = load_continuum(tmp_path)
    assert "apprenticeship" not in (data.get("completed_phases") or [])
    assert "playground" in (data.get("completed_phases") or [])
    assert "birth" in (data.get("completed_phases") or [])


@pytest.mark.unit
def test_wipe_apprenticeship_keeps_playground(tmp_path: Path) -> None:
    from lumina_core.maturity.wipe import wipe_phase

    _write_pass_workspace(tmp_path)
    tape = tmp_path / "state" / "lumina_apprenticeship_tape.jsonl"
    playground_tape = tmp_path / "state" / "lumina_playground_tape.jsonl"
    playground_tape.write_text("{}\n", encoding="utf-8")
    assert tape.is_file()
    result = wipe_phase(tmp_path, "apprenticeship", confirm=True)
    assert result["ok"] is True
    assert not tape.is_file()
    assert playground_tape.is_file()
    data = load_continuum(tmp_path)
    assert "apprenticeship" not in (data.get("completed_phases") or [])
    assert "playground" in (data.get("completed_phases") or [])


@pytest.mark.unit
def test_runner_does_not_stamp_from_ready_report(tmp_path: Path) -> None:
    from lumina_core.maturity.maturation_progress import load_maturation_progress
    from lumina_core.maturity.phase_runners.apprenticeship import run_apprenticeship

    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "sim_stability_report.json").write_text(
        json.dumps({"READY_FOR_REAL": True, "consecutive_green_days": 5}),
        encoding="utf-8",
    )
    for phase in ("genesis", "birth", "awakening", "playground"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    result = run_apprenticeship(tmp_path, should_stop=lambda: True)
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    reached = load_maturation_progress(tmp_path).milestones_reached
    assert "sim_real_guard_stable" not in reached
    data = load_continuum(tmp_path)
    rec = (data.get("phase_records") or {}).get("apprenticeship") or {}
    assert rec.get("status") != "failed"
