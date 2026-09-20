"""Living Awakening runner — clock, stall→retry, Twin-watch, Birth freeze."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from lumina_core.maturity.phase_runners.awakening_shot_io import _heartbeat
from lumina_core.maturity.awakening.clock import classify_stable, clock_keeps_running
from lumina_core.maturity.awakening.law import AwakeningSnapshot
from lumina_core.maturity.awakening.recovery import recovery_proven
from lumina_core.maturity.awakening.progress import load_awakening_progress
from lumina_core.maturity.awakening.regime import attempt_regime_slices
from lumina_core.maturity.awakening.twin_watch import watch_count
from lumina_core.maturity.continuum import load_continuum
from lumina_core.maturity.phase_runners.awakening import run_awakening
from lumina_core.maturity.phase_runners.awakening_shot import (
    run_live_awakening_shot as _REAL_SHOT,
    snapshot_birth_freeze,
)
from tests.maturity.test_awakening_live_shot import (
    _eval_stub,
    _split,
    _train_stub,
    _write_birth_plant,
)
from tests.maturity.test_awakening_law import _write_pass_workspace


@pytest.mark.unit
def test_clock_ignores_tape_exhausted_below_500() -> None:
    snap = AwakeningSnapshot(n_b=150, tape_exhausted=True)
    assert clock_keeps_running(snap, cycle=1, max_cycles=8, stall_retries=0, passed=False) is True
    assert clock_keeps_running(snap, cycle=8, max_cycles=8, stall_retries=0, passed=False) is False
    assert clock_keeps_running(snap, cycle=2, max_cycles=8, stall_retries=3, passed=False) is False
    assert clock_keeps_running(snap, cycle=2, max_cycles=8, stall_retries=0, passed=True) is False


@pytest.mark.unit
def test_exhausted_tape_same_n_b_is_not_a_stall() -> None:
    from lumina_core.maturity.awakening.recovery import is_stall

    assert is_stall(prev_n_b=86, n_b=86, shot_error=False, tape_exhausted=True) is False
    assert is_stall(prev_n_b=86, n_b=86, shot_error=False, tape_exhausted=False) is True
    assert is_stall(prev_n_b=86, n_b=86, shot_error=True, tape_exhausted=True) is True


@pytest.mark.unit
def test_recovery_proven_after_cycle_without_requiring_stall() -> None:
    assert recovery_proven(stall_retries=0, freeze_ok=True, cycles_completed=1) is True
    assert recovery_proven(stall_retries=0, freeze_ok=True, cycles_completed=0) is False
    assert recovery_proven(stall_retries=1, freeze_ok=True, cycles_completed=0) is True
    assert recovery_proven(stall_retries=1, freeze_ok=False, cycles_completed=3) is False


@pytest.mark.unit
def test_stable_never_at_n_below_500() -> None:
    assert classify_stable(n_b=172, sharpe=-0.5, dd_pct=10.0) == "INCONCLUSIVE"
    assert classify_stable(n_b=133, sharpe=-0.3, dd_pct=8.0) == "INCONCLUSIVE"
    assert classify_stable(n_b=600, sharpe=-0.5, dd_pct=10.0) == "STABLE"
    assert classify_stable(n_b=600, sharpe=-3.5, dd_pct=10.0) == "GRIND_REGRESS"


@pytest.mark.unit
def test_regime_attempts_all_slices_when_tape_empty() -> None:
    vis = attempt_regime_slices([])
    assert vis["slices"] == ["trend", "range", "mixed"]
    assert vis["attempted"] is True
    assert vis["visibility_ok"] is False
    assert vis["observed"] == []
    assert vis["status"]["trend"] == "INCONCLUSIVE"
    unlabeled = attempt_regime_slices([{"pnl": 1.0}, {"pnl": -1.0}])
    assert unlabeled["visibility_ok"] is False
    assert unlabeled["unlabeled"] == 2
    vis2 = attempt_regime_slices([{"regime": "TREND_UP", "pnl": 1.0}])
    assert vis2["status"]["trend"] == "observed"
    assert vis2["counts"]["trend"] == 1
    assert vis2["visibility_ok"] is True


@pytest.mark.unit
def test_living_runner_stalls_under_500_recovers_keeps_birth(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    freeze = snapshot_birth_freeze(tmp_path)

    def _cycle(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.40, n=133, **kw),
            init_path=kwargs.get("init_path"),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_cycle,
    ):
        result = run_awakening(tmp_path, max_cycles=8, max_stall_retries=3)
    assert result["ok"] is False
    assert any("n_B=" in str(m) for m in (result.get("missing") or []))
    prog = load_awakening_progress(tmp_path)
    assert int(prog.get("n_b") or 0) == 133
    assert prog.get("recovery_ok") is True
    assert watch_count(tmp_path) == 0
    assert list(prog.get("regime_slices") or []) == ["trend", "range", "mixed"]
    assert list(prog.get("regime_observed") or []) == []
    data = load_continuum(tmp_path)
    assert "awakening" not in data["completed_phases"]
    assert "birth" in data["completed_phases"]
    assert snapshot_birth_freeze(tmp_path) == freeze
    assert int(prog.get("stall_retries") or 0) >= 1
    assert int(prog.get("cycle") or 0) <= 8


@pytest.mark.unit
def test_living_runner_skips_when_law_already_passed(tmp_path: Path) -> None:
    from lumina_core.maturity.continuum import mark_phase_completed

    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    _write_pass_workspace(tmp_path)
    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
    ) as shot:
        result = run_awakening(tmp_path)
    assert result["ok"] is True
    shot.assert_not_called()


@pytest.mark.unit
def test_n_ge_500_does_not_loop_max_cycles(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    seen: list[int] = []

    def _cycle(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
        seen.append(1)
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.40, n=600, **kw),
            init_path=kwargs.get("init_path"),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_cycle,
    ):
        result = run_awakening(tmp_path, max_cycles=8, max_stall_retries=3)
    assert result["ok"] is False
    assert 1 <= len(seen) <= 6
    prog = load_awakening_progress(tmp_path)
    assert int(prog.get("n_b") or 0) == 600
    assert watch_count(tmp_path) == 0


@pytest.mark.unit
def test_tape_exhausted_does_not_stop_clock_before_cycle_budget(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    seen: list[int] = []

    def _cycle(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
        seen.append(1)
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: {
                **_eval_stub(seen={}, oos=0.36, n=150, **kw),
                "holdout_exhausted": True,
            },
            init_path=kwargs.get("init_path"),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_cycle,
    ):
        result = run_awakening(tmp_path, max_cycles=8, max_stall_retries=3)
    assert result["ok"] is False
    assert len(seen) == 9
    prog = load_awakening_progress(tmp_path)
    assert int(prog.get("n_b") or 0) == 150
    assert int(prog.get("stall_retries") or 0) == 0
    assert prog.get("recovery_ok") is True
    assert "birth" in load_continuum(tmp_path)["completed_phases"]
    assert "awakening" not in load_continuum(tmp_path)["completed_phases"]


@pytest.mark.unit
def test_retry_continues_child_zip_not_frozen_pi_star(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.select import continuation_init_path
    from lumina_core.maturity.phase_runners.awakening_shot import live_child_zip

    from lumina_core.maturity.awakening.progress import save_awakening_progress

    _write_birth_plant(tmp_path)
    child = live_child_zip(tmp_path)
    child.parent.mkdir(parents=True, exist_ok=True)
    child.write_bytes(b"living-child")
    save_awakening_progress(
        tmp_path,
        {"n_b": 200, "wr": 0.40, "birth_oos_wr": 0.333, "policy_only": True},
    )
    assert continuation_init_path(tmp_path, cycle=1) == child
    inits: list[str] = []

    def _cycle(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
        init = kwargs.get("init_path")
        inits.append(str(init) if init is not None else "frozen")
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.36, n=150, **kw),
            init_path=kwargs.get("init_path"),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_cycle,
    ):
        run_awakening(tmp_path, max_cycles=2, max_stall_retries=3)
    assert inits
    assert inits[0] == str(child)


@pytest.mark.unit
def test_cycle_zero_is_eval_only_then_trains(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    flags: list[bool] = []

    def _cycle(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
        flags.append(bool(kwargs.get("eval_only")))
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.36, n=150, **kw),
            init_path=kwargs.get("init_path"),
            eval_only=bool(kwargs.get("eval_only")),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_cycle,
    ):
        run_awakening(tmp_path, max_cycles=2, max_stall_retries=3)
    assert flags[0] is True
    assert flags[1:] == [False, False]


@pytest.mark.unit
def test_locked_same_tape_parent_skips_cycle_zero(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.keep_best import incumbent_zip
    from lumina_core.maturity.awakening.progress import save_awakening_progress
    from lumina_core.maturity.phase_runners.awakening_shot import live_child_zip

    _write_birth_plant(tmp_path)
    freeze = snapshot_birth_freeze(tmp_path)
    child = live_child_zip(tmp_path)
    child.parent.mkdir(parents=True, exist_ok=True)
    child.write_bytes(b"incumbent-child")
    incumbent_zip(tmp_path).write_bytes(b"incumbent-child")
    save_awakening_progress(
        tmp_path,
        {
            "parent_same_tape": True,
            "parent_holdout_wr": 0.273,
            "birth_oos_wr": 0.273,
            "birth_mean_r": -0.25,
            "n_b": 501,
            "wr": 0.325,
            "freeze_ok": True,
            "freeze_fingerprint": freeze,
            "policy_only": True,
        },
    )
    flags: list[bool] = []

    def _cycle(workspace_root: Path | str, **kwargs: Any) -> dict[str, Any]:
        flags.append(bool(kwargs.get("eval_only")))
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.36, n=150, **kw),
            init_path=kwargs.get("init_path"),
            eval_only=bool(kwargs.get("eval_only")),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_cycle,
    ):
        run_awakening(tmp_path, max_cycles=2, max_stall_retries=3)
    assert flags
    assert flags[0] is False
    prog = load_awakening_progress(tmp_path)
    assert float(prog.get("birth_oos_wr") or 0) == pytest.approx(0.273)


@pytest.mark.unit
def test_keep_best_discards_worse_child(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.keep_best import child_beats_incumbent

    incumbent = {"incumbent_n_b": 150, "incumbent_wr": 0.32, "incumbent_mean_r": -0.23, "incumbent_occupancy": 0.33}
    worse = {"policy_trades": 150, "polish_oos_winrate": 0.22, "mean_r": -0.64, "occupancy": 0.39}
    better = {"policy_trades": 180, "polish_oos_winrate": 0.37, "mean_r": -0.20, "occupancy": 0.35}
    thin_skill = {
        "policy_trades": 131,
        "polish_oos_winrate": 0.3359,
        "mean_r": -0.28,
        "occupancy": 0.33,
    }
    taxi = {"policy_trades": 200, "polish_oos_winrate": 0.20, "mean_r": -0.70, "occupancy": 0.40}
    assert child_beats_incumbent(worse, incumbent) is False
    assert child_beats_incumbent(better, incumbent) is True
    assert child_beats_incumbent(thin_skill, incumbent) is True
    assert child_beats_incumbent(taxi, incumbent) is False
    oob = {"policy_trades": 200, "polish_oos_winrate": 0.50, "mean_r": 0.1, "occupancy": 0.90}
    assert child_beats_incumbent(oob, incumbent) is False


@pytest.mark.unit
def test_overhold_train_tax_skips_plant_and_short_holds() -> None:
    from lumina_core.birth.awakening_select_env import OVERHOLD_TAX_R, overhold_train_tax

    assert overhold_train_tax(plant=True, bars_in_position=500, hold_bars=90) == 0.0
    assert overhold_train_tax(plant=False, bars_in_position=90, hold_bars=90) == 0.0
    assert overhold_train_tax(plant=False, bars_in_position=91, hold_bars=90) == -abs(OVERHOLD_TAX_R)


@pytest.mark.unit
def test_discard_rewrites_evolution_proof_to_incumbent(tmp_path: Path) -> None:
    from lumina_core.birth.evolution_proof_gate import load_evolution_proof_record, save_evolution_proof_record
    from lumina_core.maturity.awakening.keep_best import persist_incumbent_proof

    _write_birth_plant(tmp_path)
    save_evolution_proof_record(
        tmp_path,
        {"passed": False, "holdout_trades": 220, "polish_oos_winrate": 0.309, "birth_exit_winrate": 0.333},
    )
    persist_incumbent_proof(
        tmp_path,
        {"incumbent_n_b": 230, "incumbent_wr": 0.322, "incumbent_sha": "abc"},
    )
    rec = load_evolution_proof_record(tmp_path)
    assert int(rec.get("holdout_trades") or 0) == 230
    assert float(rec.get("polish_oos_winrate") or 0) == pytest.approx(0.322)


@pytest.mark.unit
def test_policy_participation_bonus_ignores_plant() -> None:
    from lumina_core.birth.awakening_select_env import (
        POLICY_PARTICIPATION_BONUS_R,
        policy_participation_bonus,
    )

    assert policy_participation_bonus(0.40) == POLICY_PARTICIPATION_BONUS_R
    assert policy_participation_bonus(0.10) == 0.0
    assert policy_participation_bonus(None) == 0.0


@pytest.mark.unit
def test_occupancy_rolling_seed_matches_s5_not_midpoint() -> None:
    from lumina_core.birth.awakening_grind_run import occupancy_rolling_seed

    win = occupancy_rolling_seed(0.277, n=200)
    assert len(win) == 200
    assert win.count(1) == 55
    assert 0.5 not in {sum(win) / len(win)}


@pytest.mark.unit
def test_worse_child_does_not_replace_frozen_pi_star(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.progress import save_awakening_progress
    from lumina_core.maturity.awakening.select import continuation_init_path
    from lumina_core.maturity.phase_runners.awakening_shot import live_child_zip

    _write_birth_plant(tmp_path)
    child = live_child_zip(tmp_path)
    child.parent.mkdir(parents=True, exist_ok=True)
    child.write_bytes(b"worse-child")
    save_awakening_progress(
        tmp_path,
        {"n_b": 86, "wr": 0.2558, "birth_oos_wr": 0.333333, "policy_only": True},
    )
    assert continuation_init_path(tmp_path, cycle=2) is None


@pytest.mark.unit
def test_occupancy_seed_prefers_live_s5_over_stale_artifact_s4(tmp_path: Path) -> None:
    import json

    from lumina_core.birth.awakening_grind_run import resolve_awakening_occupancy_seed

    _write_birth_plant(tmp_path)
    state = tmp_path / "state"
    (state / "lumina_birth_foundation_receipts.json").write_text(
        json.dumps(
            [
                {
                    "stage": "stage5_probe_handoff",
                    "occupancy": 0.277,
                    "schema": "foundation_v2",
                }
            ]
        ),
        encoding="utf-8",
    )
    reports = tmp_path / "reports" / "birth_cloud_run" / "artifacts"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "s4_receipt.json").write_text(
        json.dumps({"stage": "stage4_viable_plant", "occupancy": 0.473}),
        encoding="utf-8",
    )
    occ, source = resolve_awakening_occupancy_seed(reports, tmp_path)
    assert source == "s5_receipt"
    assert occ == pytest.approx(0.277)


@pytest.mark.unit
def test_policy_skill_ignores_plant_airframe(tmp_path: Path) -> None:
    import json

    from lumina_core.maturity.phase_runners.awakening_shot_io import _policy_skill_from_ledger

    ledger = tmp_path / "awakening_live_holdout.jsonl"
    rows = [
        {"pnl": -1.0, "trade_r": -0.1, "plant": True, "skill_grade": "plant"},
        {"pnl": 10.0, "trade_r": 1.0, "plant": False, "skill_grade": "policy"},
        {"pnl": -10.0, "trade_r": -1.0, "plant": False, "skill_grade": "policy"},
    ]
    ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    skill = _policy_skill_from_ledger(ledger)
    assert skill["policy_only"] is True
    assert skill["policy_trades"] == 2
    assert skill["n_plant"] == 1
    assert skill["n_all"] == 3
    assert skill["wr"] == pytest.approx(0.5)
    assert skill["mean_r"] == pytest.approx(0.0)


@pytest.mark.unit
def test_train_heartbeat_writes_activity_and_timesteps(tmp_path: Path) -> None:
    _heartbeat(tmp_path, activity="train_A", train_timesteps=2048)
    prog = load_awakening_progress(tmp_path)
    assert prog.get("activity") == "train_A"
    assert int(prog.get("train_timesteps") or 0) == 2048
    assert isinstance(prog.get("updated_at"), str)
