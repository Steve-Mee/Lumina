"""ADR-0050 Playground law — n_P≥150 hard, JSON is not a fill, no Birth-tape pass."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.phase_specs import evaluate_exit_proofs
from lumina_core.maturity.playground.fills import first_honest_fill, record_orderpath_fill
from lumina_core.maturity.playground.heal import heal_playground_from_law
from lumina_core.maturity.playground.law import (
    N_P_MIN,
    PlaygroundSnapshot,
    evaluate_playground_exit,
    evaluate_playground_pass,
)
from lumina_core.maturity.playground.progress import save_playground_progress


def _pass_snap(**overrides: object) -> PlaygroundSnapshot:
    base: dict[str, object] = {
        "n_p": 160,
        "n_plant": 0,
        "occupancy": 0.40,
        "skill_wr": 0.50,
        "breakeven_wr": 0.42,
        "mean_r": 0.05,
        "median_loss_r": 1.2,
        "freeze_ok": True,
        "policy_only": True,
        "child_sha": "aa" * 32,
        "awakening_child_sha": "aa" * 32,
        "birth_sha": "bb" * 32,
        "envelope_sealed": True,
        "envelope_breached": False,
        "deck_live": True,
        "mode": "sim",
        "first_fill": True,
        "first_fill_source": "orderpath",
    }
    base.update(overrides)
    return PlaygroundSnapshot(**base)  # type: ignore[arg-type]


def _seal(root: Path) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True, "source": "test"}),
        encoding="utf-8",
    )


def _write_pass_workspace(root: Path, *, n_p: int = 160) -> None:
    _seal(root)
    save_playground_progress(
        root,
        {
            "occupancy": 0.40,
            "breakeven_wr": 0.42,
            "freeze_ok": True,
            "child_sha": "aa" * 32,
            "awakening_child_sha": "aa" * 32,
            "birth_sha": "bb" * 32,
            "deck_live": True,
            "mode": "sim",
            "envelope_breached": False,
        },
    )
    for i in range(n_p):
        record_orderpath_fill(
            root,
            order_id=f"SIM-{i}",
            fill_px=5000.0,
            qty=1,
            instrument="MES",
            mode="sim",
            source="orderpath",
            kind="close",
            policy=True,
            r=0.20 if i % 2 == 0 else -0.10,
            win=i % 2 == 0,
        )


@pytest.mark.unit
def test_n_p_below_150_is_inconclusive() -> None:
    result = evaluate_playground_pass(_pass_snap(n_p=N_P_MIN - 1))
    assert result.passed is False
    assert result.clock_open is True
    assert any(f"n_P={N_P_MIN - 1}" in b for b in result.blockers)


@pytest.mark.unit
def test_full_and_passes() -> None:
    result = evaluate_playground_pass(_pass_snap())
    assert result.passed is True
    assert "economic_viability" in result.proofs
    assert "first_honest_fill" in result.proofs
    assert "n_P>=150" in result.proofs


@pytest.mark.unit
def test_birth_fitness_wr_is_not_pass() -> None:
    result = evaluate_playground_pass(
        _pass_snap(skill_wr=0.30, breakeven_wr=0.42, mean_r=-0.20)
    )
    assert result.passed is False
    assert any("skill_wr" in b or "mean_r" in b for b in result.blockers)


@pytest.mark.unit
def test_missing_be_cannot_pass() -> None:
    result = evaluate_playground_pass(_pass_snap(breakeven_wr=None))
    assert result.passed is False
    assert any("wr_or_be_missing" in b for b in result.blockers)


@pytest.mark.unit
def test_json_source_is_not_first_fill() -> None:
    result = evaluate_playground_pass(
        _pass_snap(first_fill=True, first_fill_source="state/first_sim_order.json")
    )
    assert result.passed is False
    assert "first_honest_fill" in result.blockers


@pytest.mark.unit
def test_soft_complete_cannot_set_ok() -> None:
    result = evaluate_playground_pass(_pass_snap(n_p=1, first_fill=False))
    assert result.passed is False


@pytest.mark.unit
def test_freeze_and_child_gates() -> None:
    frozen = evaluate_playground_pass(_pass_snap(freeze_ok=False))
    assert frozen.passed is False
    swapped = evaluate_playground_pass(_pass_snap(child_sha="cc" * 32))
    assert swapped.passed is False
    same_as_birth = evaluate_playground_pass(_pass_snap(child_sha="bb" * 32, awakening_child_sha="bb" * 32))
    assert same_as_birth.passed is False


@pytest.mark.unit
def test_real_mode_fails() -> None:
    result = evaluate_playground_pass(_pass_snap(mode="real"))
    assert result.passed is False
    assert any("mode_not_sim" in b for b in result.blockers)


@pytest.mark.unit
def test_occupancy_and_process_r_required() -> None:
    occ = evaluate_playground_pass(_pass_snap(occupancy=0.10))
    assert occ.passed is False
    proc = evaluate_playground_pass(_pass_snap(median_loss_r=2.0))
    assert proc.passed is False


@pytest.mark.unit
def test_json_stamp_file_is_not_honest_fill(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "first_sim_order.json").write_text(
        json.dumps({"placed": True, "order_id": "FAKE-1"}),
        encoding="utf-8",
    )
    assert first_honest_fill(tmp_path) is None
    ok, missing, _ = evaluate_playground_exit(tmp_path)
    assert ok is False
    assert "first_honest_fill" in missing


@pytest.mark.unit
def test_orderpath_fill_counts(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=5124.25,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
    )
    assert rec["ok"] is True
    fill = first_honest_fill(tmp_path)
    assert fill is not None
    assert fill["order_id"] == "SIM-1"


@pytest.mark.unit
def test_health_source_rejected(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=1.0,
        qty=1,
        instrument="MES",
        mode="sim",
        source="fabric_health",
    )
    assert rec["ok"] is False
    assert rec["reason"] == "source_not_orderpath"


@pytest.mark.unit
def test_workspace_n_p_149_inconclusive(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, n_p=149)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "playground")
    assert ok is False
    assert any("n_P=" in m for m in missing)
    assert learned.get("clock_open") is True
    assert learned.get("pass_now") is False


@pytest.mark.unit
def test_workspace_full_and_passes(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, n_p=160)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "playground")
    assert ok is True
    assert missing == []
    assert learned.get("pass_now") is True
    assert "economic_viability" in (learned.get("exit_proofs") or [])


@pytest.mark.unit
def test_heal_reopens_false_stamp(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={"soft": True}, exit_proofs=["deck_unlocked"])
    result = heal_playground_from_law(tmp_path)
    assert result["healed"] is True
    data = load_continuum(tmp_path)
    assert "playground" not in (data.get("completed_phases") or [])
    assert "awakening" in (data.get("completed_phases") or [])
    assert "birth" in (data.get("completed_phases") or [])


@pytest.mark.unit
def test_missing_envelope_file_is_unsealed(tmp_path: Path) -> None:
    ok, missing, _ = evaluate_playground_exit(tmp_path)
    assert ok is False
    assert "sim_envelope_sealed" in missing


@pytest.mark.unit
def test_runner_does_not_stamp_deck_or_json_fill(tmp_path: Path) -> None:
    from lumina_core.maturity.maturation_progress import load_maturation_progress
    from lumina_core.maturity.phase_runners.playground import run_playground

    result = run_playground(tmp_path, should_stop=lambda: True, poll_sec=0.0, sleep_fn=lambda _s: None)
    assert result["ok"] is False
    reached = load_maturation_progress(tmp_path).milestones_reached
    assert "deck_unlocked" not in reached
    assert "first_sim_order_placed" not in reached
    from lumina_core.maturity.playground.progress import load_playground_progress

    assert load_playground_progress(tmp_path).get("deck_live") is not True
