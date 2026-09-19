"""ADR-0052 Proving Ground law — n_G≥150, cert walls, this-run shadow/gate, no Birth JSON."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.phase_specs import evaluate_exit_proofs
from lumina_core.maturity.proving_ground.evidence import fabrication_reasons
from lumina_core.maturity.proving_ground.heal import heal_proving_ground_from_law
from lumina_core.maturity.proving_ground.law import (
    N_G_MIN,
    ProvingGroundSnapshot,
    evaluate_proving_ground_exit,
    evaluate_proving_ground_pass,
)
from lumina_core.maturity.proving_ground.progress import save_proving_ground_progress
from lumina_core.maturity.proving_ground.tape import record_orderpath_fill


def _pass_snap(**overrides: object) -> ProvingGroundSnapshot:
    base: dict[str, object] = {
        "n_g": 160,
        "n_plant": 0,
        "occupancy": 0.40,
        "median_loss_r": 1.2,
        "oos_wr": 0.50,
        "oos_sharpe": 0.40,
        "dd_pct": 5.0,
        "freeze_ok": True,
        "policy_only": True,
        "apprenticeship_completed": True,
        "child_sha": "aa" * 32,
        "apprenticeship_child_sha": "aa" * 32,
        "birth_sha": "bb" * 32,
        "envelope_sealed": True,
        "envelope_breached": False,
        "deck_live": True,
        "mode": "sim_real_guard",
        "recovery_ok": True,
        "risk_events": 0,
        "var_breach_count": 0,
        "daily_kill": False,
        "exam_source": "proving_exam",
        "exam_folds": 8,
        "exam_eval_only": True,
        "holdout_b_only": False,
        "shadow_this_run": True,
        "promotion_this_run": True,
        "promotion_criteria_passed": 4,
    }
    base.update(overrides)
    return ProvingGroundSnapshot(**base)  # type: ignore[arg-type]


def _seal(root: Path) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps({"sealed": True, "source": "test"}),
        encoding="utf-8",
    )


def _write_progress(root: Path, **extra: object) -> None:
    payload: dict[str, object] = {
        "occupancy": 0.40,
        "freeze_ok": True,
        "child_sha": "aa" * 32,
        "apprenticeship_child_sha": "aa" * 32,
        "birth_sha": "bb" * 32,
        "deck_live": True,
        "mode": "sim_real_guard",
        "envelope_breached": False,
        "recovery_ok": True,
        "risk_events": 0,
        "var_breach_count": 0,
        "daily_kill": False,
        "exam_source": "proving_exam",
        "exam_eval_only": True,
        "exam_folds": 8,
        "holdout_b_only": False,
        "oos_wr": 0.50,
        "oos_sharpe": 0.40,
        "dd_pct": 5.0,
        "clock_id": "clock-1",
        "shadow_this_run": True,
        "shadow_clock_id": "clock-1",
        "shadow_sample_count": 160,
        "reality_gap_band": "GREEN",
        "reality_gap_trend": "STABLE",
        "live_fill_rate": 0.92,
        "backtest_fill_rate": 0.95,
        "live_slippage": 0.12,
        "backtest_slippage": 0.10,
        "promotion_this_run": True,
        "promotion_clock_id": "clock-1",
        "promotion_criteria_passed": 4,
    }
    payload.update(extra)
    save_proving_ground_progress(root, payload)


def _write_closes(root: Path, *, n: int) -> None:
    for i in range(n):
        r = 0.20 if i % 3 else -0.10
        record_orderpath_fill(
            root,
            order_id=f"SIM-{i}",
            fill_px=5000.0,
            qty=1,
            instrument="MES",
            mode="sim_real_guard",
            source="orderpath",
            kind="close",
            policy=True,
            r=r,
            win=r > 0,
            pnl=8.0 if r > 0 else -4.0,
        )


def _write_pass_workspace(root: Path, *, n: int = 160) -> None:
    _seal(root)
    _write_progress(root)
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(root, phase, learned={}, exit_proofs=["x"])
    _write_closes(root, n=n)


@pytest.mark.unit
def test_n_g_below_150_is_inconclusive() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(n_g=N_G_MIN - 1))
    assert result.passed is False
    assert result.clock_open is True
    assert any(f"n_G={N_G_MIN - 1}" in b for b in result.blockers)


@pytest.mark.unit
def test_full_and_passes() -> None:
    result = evaluate_proving_ground_pass(_pass_snap())
    assert result.passed is True
    assert "certificate_oos_walls" in result.proofs
    assert "shadow_this_run" in result.proofs
    assert "promotion_gate_this_run" in result.proofs


@pytest.mark.unit
def test_or_shadow_alone_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(promotion_this_run=False, promotion_criteria_passed=0))
    assert result.passed is False
    assert "promotion_gate_this_run" in result.blockers


@pytest.mark.unit
def test_or_promotion_alone_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(shadow_this_run=False))
    assert result.passed is False
    assert "shadow_this_run" in result.blockers


@pytest.mark.unit
def test_real_mode_halts() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(mode="real"))
    assert result.passed is False
    assert "mode_real_halt" in result.blockers
    assert "constitution_violated" in result.blockers


@pytest.mark.unit
def test_cert_wr_below_48_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(oos_wr=0.47))
    assert result.passed is False
    assert any("oos_wr=" in b for b in result.blockers)


@pytest.mark.unit
def test_cert_sharpe_below_035_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(oos_sharpe=0.34))
    assert result.passed is False
    assert any("oos_sharpe=" in b for b in result.blockers)


@pytest.mark.unit
def test_cert_dd_above_8_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(dd_pct=8.01))
    assert result.passed is False
    assert any("dd=" in b for b in result.blockers)


@pytest.mark.unit
def test_birth_certificate_source_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(exam_source="birth_certificate"))
    assert result.passed is False
    assert any("exam_source=" in b for b in result.blockers)


@pytest.mark.unit
def test_holdout_b_only_cannot_pass() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(holdout_b_only=True))
    assert result.passed is False
    assert "exam_holdout_b_only" in result.blockers


@pytest.mark.unit
def test_folds_below_5_inconclusive() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(exam_folds=4))
    assert result.passed is False
    assert any("exam_folds=" in b for b in result.blockers)


@pytest.mark.unit
def test_learn_exam_rejected() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(exam_eval_only=False))
    assert result.passed is False
    assert "exam_not_eval_only" in result.blockers


@pytest.mark.unit
def test_soft_complete_cannot_set_ok() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(n_g=1, recovery_ok=False, shadow_this_run=False))
    assert result.passed is False


@pytest.mark.unit
def test_freeze_and_child_gates() -> None:
    frozen = evaluate_proving_ground_pass(_pass_snap(freeze_ok=False))
    assert frozen.passed is False
    swapped = evaluate_proving_ground_pass(_pass_snap(child_sha="cc" * 32))
    assert swapped.passed is False
    same_as_birth = evaluate_proving_ground_pass(
        _pass_snap(child_sha="bb" * 32, apprenticeship_child_sha="bb" * 32)
    )
    assert same_as_birth.passed is False


@pytest.mark.unit
def test_apprenticeship_not_completed_blocks() -> None:
    result = evaluate_proving_ground_pass(_pass_snap(apprenticeship_completed=False))
    assert result.passed is False
    assert "apprenticeship_not_completed" in result.blockers


@pytest.mark.unit
def test_audit_scan_flag_cannot_pass(tmp_path: Path) -> None:
    _seal(tmp_path)
    _write_progress(tmp_path, promotion_from_audit_scan=True, promotion_this_run=True)
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    _write_closes(tmp_path, n=160)
    ok, missing, _ = evaluate_proving_ground_exit(tmp_path)
    assert ok is False
    assert "promotion_gate_this_run" in missing


@pytest.mark.unit
def test_birth_certificate_json_cannot_pass(tmp_path: Path) -> None:
    _seal(tmp_path)
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_birth_certificate.json").write_text(
        json.dumps({"oos_winrate": 0.55, "oos_sharpe": 0.50, "max_drawdown_pct": 3.0}),
        encoding="utf-8",
    )
    _write_progress(tmp_path, exam_source="birth_certificate", oos_wr=0.55, oos_sharpe=0.50)
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    _write_closes(tmp_path, n=160)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "proving_ground")
    assert ok is False
    assert any("exam_source=" in m for m in missing)
    assert learned.get("pass_now") is False


@pytest.mark.unit
def test_foreign_audit_row_cannot_pass(tmp_path: Path) -> None:
    _seal(tmp_path)
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "promotion_gate_audit.jsonl").write_text(
        json.dumps({"passed": True, "promoted": True, "shadow_passed": True, "dna_hash": "zz"}) + "\n",
        encoding="utf-8",
    )
    _write_progress(tmp_path, shadow_this_run=False, promotion_this_run=False, promotion_criteria_passed=0)
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    _write_closes(tmp_path, n=160)
    ok, missing, _ = evaluate_exit_proofs(tmp_path, "proving_ground")
    assert ok is False
    assert "shadow_this_run" in missing
    assert "promotion_gate_this_run" in missing


@pytest.mark.unit
def test_real_fill_rejected_on_tape(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="R-1",
        fill_px=5000.0,
        qty=1,
        instrument="MES",
        mode="real",
        source="orderpath",
        kind="close",
    )
    assert rec["ok"] is False
    assert rec["reason"] == "mode_not_sim"


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


@pytest.mark.unit
def test_workspace_n_g_149_inconclusive(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, n=149)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "proving_ground")
    assert ok is False
    assert any("n_G=" in m for m in missing)
    assert learned.get("pass_now") is False
    assert learned.get("clock_open") is True


@pytest.mark.unit
def test_workspace_full_and_passes(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, n=160)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "proving_ground")
    assert ok is True, missing
    assert missing == []
    assert learned.get("pass_now") is True
    assert "certificate_oos_walls" in (learned.get("exit_proofs") or [])


@pytest.mark.unit
def test_milestone_stamp_without_tape_cannot_pass(tmp_path: Path) -> None:
    from lumina_core.maturity.maturation_progress import record_maturation_milestone

    mark_phase_completed(tmp_path, "apprenticeship", learned={}, exit_proofs=["x"])
    record_maturation_milestone(tmp_path, "promotion_gate_passed", metadata={"cheat": True})
    record_maturation_milestone(tmp_path, "shadow_validation_passed", metadata={"cheat": True})
    ok, missing, _ = evaluate_exit_proofs(tmp_path, "proving_ground")
    assert ok is False
    assert missing


@pytest.mark.unit
def test_heal_reopens_false_stamp(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship", "proving_ground"):
        mark_phase_completed(tmp_path, phase, learned={"soft": True}, exit_proofs=["stamp"])
    result = heal_proving_ground_from_law(tmp_path)
    assert result["healed"] is True
    data = load_continuum(tmp_path)
    assert "proving_ground" not in (data.get("completed_phases") or [])
    assert "apprenticeship" in (data.get("completed_phases") or [])
    assert "birth" in (data.get("completed_phases") or [])


@pytest.mark.unit
def test_wipe_proving_ground_keeps_apprenticeship(tmp_path: Path) -> None:
    from lumina_core.maturity.wipe import wipe_phase

    _write_pass_workspace(tmp_path)
    tape = tmp_path / "state" / "lumina_proving_ground_tape.jsonl"
    ap_tape = tmp_path / "state" / "lumina_apprenticeship_tape.jsonl"
    ap_tape.write_text("{}\n", encoding="utf-8")
    assert tape.is_file()
    result = wipe_phase(tmp_path, "proving_ground", confirm=True)
    assert result["ok"] is True
    assert not tape.is_file()
    assert ap_tape.is_file()
    data = load_continuum(tmp_path)
    assert "proving_ground" not in (data.get("completed_phases") or [])
    assert "apprenticeship" in (data.get("completed_phases") or [])


@pytest.mark.unit
def test_fabricated_samples_rejected() -> None:
    reasons = fabrication_reasons(
        {
            "live_pnl_samples": [12.0],
            "shadow_total_pnl": 12.0,
            "backtest_pnl_samples": [5.0] * 160,
            "min_sample_trades": 30,
        }
    )
    assert "live_samples_are_shadow_total_scalar" in reasons
    assert "backtest_samples_repeated_baseline" in reasons
    assert any("min_sample_trades" in r for r in reasons)


@pytest.mark.unit
def test_runner_does_not_stamp_from_audit(tmp_path: Path) -> None:
    from lumina_core.maturity.maturation_progress import load_maturation_progress
    from lumina_core.maturity.phase_runners.proving_ground import run_proving_ground

    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "promotion_gate_audit.jsonl").write_text(
        json.dumps({"passed": True, "promoted": True, "shadow_passed": True}) + "\n",
        encoding="utf-8",
    )
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    result = run_proving_ground(tmp_path, should_stop=lambda: True)
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    reached = load_maturation_progress(tmp_path).milestones_reached
    assert "promotion_gate_passed" not in reached
    data = load_continuum(tmp_path)
    rec = (data.get("phase_records") or {}).get("proving_ground") or {}
    assert rec.get("status") != "failed"
