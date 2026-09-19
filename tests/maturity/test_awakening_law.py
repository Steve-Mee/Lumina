"""ADR-0049 Awakening law — n_B≥500 hard, Twin dump is not proof, no soft."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.evolution_proof_gate import (
    evaluate_evolution_proof,
    evolution_proof_passed,
    save_evolution_proof_record,
)
from lumina_core.maturity.awakening.heal import heal_awakening_from_law
from lumina_core.maturity.awakening.law import (
    N_B_MIN,
    AwakeningSnapshot,
    evaluate_awakening_exit,
    evaluate_awakening_pass,
)
from lumina_core.maturity.awakening.progress import save_awakening_progress
from lumina_core.maturity.awakening.twin_watch import append_watch
from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.phase_specs import evaluate_exit_proofs


def _pass_snap(**overrides: object) -> AwakeningSnapshot:
    base: dict[str, object] = {
        "n_b": 600,
        "n_plant": 0,
        "occupancy": 0.40,
        "wr": 0.44,
        "birth_oos_wr": 0.333,
        "mean_r": -0.20,
        "birth_mean_r": -0.30,
        "edge": 0.02,
        "median_loss_r": 1.2,
        "sharpe": -0.5,
        "dd_pct": 10.0,
        "stable_class": "STABLE",
        "freeze_ok": True,
        "policy_only": True,
        "child_sha": "aa" * 32,
        "init_sha": "bb" * 32,
        "twin_watch_n": 2,
        "recovery_ok": True,
        "regime_slices": ("trend", "range", "mixed"),
        "regime_observed": ("trend", "range", "mixed"),
    }
    base.update(overrides)
    return AwakeningSnapshot(**base)  # type: ignore[arg-type]


def _write_pass_workspace(root: Path) -> None:
    from lumina_core.maturity.phase_runners.awakening_shot import snapshot_birth_freeze

    (root / "state").mkdir(parents=True, exist_ok=True)
    save_awakening_progress(
        root,
        {
            "n_b": 600,
            "n_plant": 0,
            "occupancy": 0.40,
            "wr": 0.44,
            "birth_oos_wr": 0.333,
            "mean_r": -0.20,
            "birth_mean_r": -0.30,
            "edge": 0.02,
            "median_loss_r": 1.2,
            "sharpe": -0.5,
            "dd_pct": 10.0,
            "stable_class": "STABLE",
            "freeze_ok": True,
            "policy_only": True,
            "child_sha": "aa" * 32,
            "init_sha": "bb" * 32,
            "recovery_ok": True,
            "regime_slices": ["trend", "range", "mixed"],
            "regime_observed": ["trend", "range", "mixed"],
            "freeze_fingerprint": snapshot_birth_freeze(root),
        },
    )
    append_watch(root, kind="prefer_better", note="child preferred", source="twin")
    save_evolution_proof_record(
        root,
        {
            "passed": True,
            "holdout_trades": 600,
            "birth_exit_winrate": 0.333,
            "polish_oos_winrate": 0.44,
            "oos_winrate": 0.44,
            "winrate_lift": 0.107,
        },
    )


@pytest.mark.unit
def test_n_133_lift_fails_hard() -> None:
    result = evaluate_evolution_proof(
        birth_exit_winrate=0.333,
        polish_oos_winrate=0.436,
        holdout_trades=133,
    )
    assert result.passed is False
    assert any("133" in r and str(N_B_MIN) in r for r in result.reasons)


@pytest.mark.unit
def test_disk_passed_n_133_re_evaluates_false(tmp_path: Path) -> None:
    save_evolution_proof_record(
        tmp_path,
        {
            "passed": True,
            "holdout_trades": 133,
            "birth_exit_winrate": 0.333,
            "polish_oos_winrate": 0.436,
            "oos_winrate": 0.436,
            "winrate_lift": 0.103,
        },
    )
    assert evolution_proof_passed(tmp_path) is False


@pytest.mark.unit
def test_and_requires_occupancy_even_with_lift() -> None:
    result = evaluate_awakening_pass(_pass_snap(occupancy=None))
    assert result.passed is False
    assert any("occupancy" in b for b in result.blockers)


@pytest.mark.unit
def test_and_requires_n_b_even_when_other_gates_green() -> None:
    result = evaluate_awakening_pass(_pass_snap(n_b=133))
    assert result.passed is False
    assert any("n_B=" in b for b in result.blockers)
    assert result.clock_open is True


@pytest.mark.unit
def test_thin_n_b_does_not_emit_edge_missing() -> None:
    result = evaluate_awakening_pass(_pass_snap(n_b=86, edge=None, tape_exhausted=True))
    assert result.passed is False
    assert any("n_B=" in b for b in result.blockers)
    assert not any("edge_missing" in b for b in result.blockers)


@pytest.mark.unit
def test_tape_exhausted_below_500_is_inconclusive_clock_stays_open() -> None:
    result = evaluate_awakening_pass(_pass_snap(n_b=150, tape_exhausted=True))
    assert result.passed is False
    assert result.clock_open is True
    assert any("n_B=" in b for b in result.blockers)


@pytest.mark.unit
def test_full_and_passes() -> None:
    result = evaluate_awakening_pass(_pass_snap())
    assert result.passed is True
    assert result.blockers == ()
    assert "evolution_proof_passed" in result.proofs
    assert "twin_watch" in result.proofs


@pytest.mark.unit
def test_child_sha_equals_init_is_substitution() -> None:
    result = evaluate_awakening_pass(_pass_snap(child_sha="xx" * 32, init_sha="xx" * 32))
    assert result.passed is False
    assert "child_sha_equals_init" in result.blockers


@pytest.mark.unit
def test_runner_telemetry_is_not_twin_watch(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.twin_watch import watch_count

    append_watch(tmp_path, kind="prefer_better", note="self stamp", source="runner")
    assert watch_count(tmp_path) == 0
    append_watch(tmp_path, kind="prefer_better", note="twin saw it", source="twin")
    assert watch_count(tmp_path) == 1


@pytest.mark.unit
def test_regime_slices_without_observed_fail() -> None:
    result = evaluate_awakening_pass(
        _pass_snap(regime_slices=("trend", "range", "mixed"), regime_observed=())
    )
    assert result.passed is False
    assert "regime_visibility_missing" in result.blockers


@pytest.mark.unit
def test_persist_does_not_stamp_freeze_ok(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.select import persist_cycle

    persist_cycle(
        tmp_path,
        {
            "policy_trades": 600,
            "policy_only": True,
            "polish_oos_winrate": 0.44,
            "birth_exit_winrate": 0.33,
            "child_sha256": "aa",
            "init_sha256": "bb",
        },
        cycle=1,
    )
    from lumina_core.maturity.awakening.progress import load_awakening_progress

    prog = load_awakening_progress(tmp_path)
    assert prog.get("freeze_ok") is False
    assert prog.get("policy_only") is True
    assert int(prog.get("n_b") or 0) == 600


@pytest.mark.unit
def test_twin_dump_is_not_proof(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "twin_mode_metrics_summary.json").write_text(
        '{"samples": 197819}', encoding="utf-8"
    )
    save_evolution_proof_record(
        tmp_path,
        {
            "passed": True,
            "holdout_trades": 600,
            "birth_exit_winrate": 0.333,
            "polish_oos_winrate": 0.50,
            "oos_winrate": 0.50,
        },
    )
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "awakening")
    assert ok is False
    assert any("twin_watch" in m for m in missing)
    assert learned.get("twin_watch_n") == 0


@pytest.mark.unit
def test_soft_complete_cannot_pass_awakening(tmp_path: Path) -> None:
    mark_phase_completed(
        tmp_path,
        "awakening",
        learned={"soft_complete": True, "awakening_eval_ok": True},
        exit_proofs=["soft_complete"],
    )
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "awakening")
    assert ok is False
    assert learned.get("soft_complete") is not True
    assert missing


@pytest.mark.unit
def test_heal_reopens_false_complete_keeps_birth(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=["setup"])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=["foundation_five_receipts_v2"])
    mark_phase_completed(
        tmp_path,
        "awakening",
        learned={"evolution_proof_ok": True},
        exit_proofs=["evolution_proof_passed", "twin_observability"],
    )
    save_evolution_proof_record(
        tmp_path,
        {
            "passed": True,
            "holdout_trades": 133,
            "birth_exit_winrate": 0.333,
            "polish_oos_winrate": 0.436,
            "oos_winrate": 0.436,
        },
    )
    from lumina_core.maturity.maturation_progress import record_maturation_milestone

    record_maturation_milestone(tmp_path, "evolution_proof_passed")
    out = heal_awakening_from_law(tmp_path)
    assert out["healed"] is True
    data = load_continuum(tmp_path)
    assert "birth" in data["completed_phases"]
    assert "genesis" in data["completed_phases"]
    assert "awakening" not in data["completed_phases"]
    rec = json.loads((tmp_path / "state" / "lumina_evolution_proof.json").read_text(encoding="utf-8"))
    assert rec["passed"] is False
    assert rec["superseded_by"] == "adr_0049"
    from lumina_core.maturity.maturation_progress import load_maturation_progress

    assert "evolution_proof_passed" not in load_maturation_progress(tmp_path).milestones_reached


@pytest.mark.unit
def test_workspace_pass_roundtrip(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path)
    ok, missing, learned = evaluate_awakening_exit(tmp_path)
    assert ok is True
    assert missing == []
    assert learned["pass_now"] is True
