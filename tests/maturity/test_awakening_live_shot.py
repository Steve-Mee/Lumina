"""Live Awakening shot: freeze Birth artefacts, honest ADR-0026 persist."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from lumina_core.birth.evolution_proof_gate import (
    evolution_proof_passed,
    evolution_proof_state_path,
)
from lumina_core.birth.foundation_metrics import FOUNDATION_SCHEMA
from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.phase_runners.awakening_shot import (
    AwakeningShotError,
    assert_birth_freeze,
    live_child_zip,
    run_live_awakening_shot,
    snapshot_birth_freeze,
)

_REAL_SHOT = run_live_awakening_shot


def _write_fitness(root: Path, *, oos_wr: float = 0.333333) -> None:
    (root / "state").mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": FOUNDATION_SCHEMA,
        "mean_r": -0.2978,
        "edge": 0.0336,
        "occupancy": 0.277,
        "oos_wr": oos_wr,
        "oos_sharpe": -0.2123,
        "median_loss_r": 1.2,
        "s5_receipt_checksum": "96e2e2362c046173",
        "trades": 162,
    }
    (root / "state" / "lumina_birth_fitness_vector.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_pi_star(root: Path, blob: bytes | None = None) -> Path:
    from lumina_core.maturity.awakening.weight_sha import pack_policy_weight_zip

    if blob is None:
        blob = pack_policy_weight_zip(b"frozen-weights")
    path = root / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    path.with_name("birth_exit_pi_star.json").write_text("{}", encoding="utf-8")
    return path


def _write_birth_plant(root: Path) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_birth_foundation_receipts.json").write_text("[]", encoding="utf-8")
    (state / "lumina_birth_completed.flag").write_text("2026-09-17T21:43:14Z", encoding="utf-8")
    (state / "lumina_birth_progress.json").write_text(
        json.dumps({"phase": "completed", "curriculum_stage": "stage5_probe_handoff"}),
        encoding="utf-8",
    )
    _write_fitness(root)
    _write_pi_star(root)
    mark_phase_completed(root, "genesis", learned={}, exit_proofs=["setup"])
    mark_phase_completed(
        root,
        "birth",
        learned={"trades": 1145, "message": "Birth Foundation complete"},
        exit_proofs=["foundation_five_receipts_v2", "foundation_fitness_vector"],
    )


def _split(_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    train = [
        {"timestamp": "2026-01-01T00:00:00", "last": 5000.0, "id": "train-a"},
        {"timestamp": "2026-01-01T00:01:00", "last": 5001.0, "id": "train-b"},
    ]
    holdout = [
        {"timestamp": "2026-02-01T00:00:00", "last": 5100.0, "id": "hold-a"},
        {"timestamp": "2026-02-01T00:01:00", "last": 5101.0, "id": "hold-b"},
    ]
    return train, holdout, {"holdout_pct": 0.2, "train_n": 2, "holdout_n": 2}


def _train_stub(*, train: list[dict[str, Any]], child_path: Path, seen: dict[str, Any], **_: Any) -> dict[str, Any]:
    seen["train_ids"] = [str(t.get("id")) for t in train]
    child_path.parent.mkdir(parents=True, exist_ok=True)
    from lumina_core.maturity.awakening.weight_sha import pack_policy_weight_zip

    child_path.write_bytes(pack_policy_weight_zip(b"child-weights"))
    return {"actual_timesteps": 10_000}


def _eval_stub(
    *,
    holdout: list[dict[str, Any]],
    seen: dict[str, Any],
    oos: float,
    n: int,
    **_: Any,
) -> dict[str, Any]:
    seen["eval_ids"] = [str(t.get("id")) for t in holdout]
    return {
        "oos_winrate": float(oos),
        "holdout_trades": int(n),
        "policy_trades": int(n),
        "n_all": int(n),
        "policy_only": True,
    }


@pytest.mark.unit
def test_birth_hub_card_rewrite_does_not_break_freeze(tmp_path: Path) -> None:
    from lumina_core.maturity.continuum import load_continuum, save_continuum
    from lumina_core.maturity.phase_runners.awakening_shot import (
        assert_birth_freeze,
        snapshot_birth_freeze,
    )

    _write_birth_plant(tmp_path)
    before = snapshot_birth_freeze(tmp_path)
    data = load_continuum(tmp_path)
    birth = dict((data.get("phase_records") or {}).get("birth") or {})
    learned = dict(birth.get("learned") or {})
    learned["message"] = "hub card refreshed"
    learned.pop("birth_exit", None)
    birth.pop("completed_at", None)
    birth["learned"] = learned
    data["phase_records"]["birth"] = birth
    save_continuum(tmp_path, data)
    assert_birth_freeze(tmp_path, before)


@pytest.mark.unit
def test_dropping_birth_exit_proofs_breaks_freeze(tmp_path: Path) -> None:
    from lumina_core.maturity.continuum import load_continuum, save_continuum
    from lumina_core.maturity.phase_runners.awakening_shot import (
        AwakeningShotError,
        assert_birth_freeze,
        snapshot_birth_freeze,
    )

    _write_birth_plant(tmp_path)
    before = snapshot_birth_freeze(tmp_path)
    data = load_continuum(tmp_path)
    birth = dict((data.get("phase_records") or {}).get("birth") or {})
    birth["exit_proofs"] = []
    data["phase_records"]["birth"] = birth
    save_continuum(tmp_path, data)
    with pytest.raises(AwakeningShotError, match="continuum.birth_exit_proofs"):
        assert_birth_freeze(tmp_path, before)


@pytest.mark.unit
def test_shot_fail_closed_without_pi_star(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    pi_star = tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    pi_star.unlink()
    freeze = snapshot_birth_freeze(tmp_path)
    with pytest.raises(AwakeningShotError, match="birth_exit_pi_star_missing"):
        run_live_awakening_shot(tmp_path, split_loader=_split)
    assert not evolution_proof_state_path(tmp_path).is_file()
    assert snapshot_birth_freeze(tmp_path) == freeze
    data = load_continuum(tmp_path)
    assert "birth" in data["completed_phases"]
    assert "awakening" not in data["completed_phases"]


@pytest.mark.unit
def test_refuse_write_to_birth_exit_pi_star(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.freeze_pin import refuse_birth_pi_star_write
    from lumina_core.maturity.awakening.keep_best import copy_zip

    frozen = tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    frozen.parent.mkdir(parents=True)
    src = tmp_path / "child.zip"
    src.write_bytes(b"child")
    with pytest.raises(RuntimeError, match="refused write"):
        refuse_birth_pi_star_write(frozen)
    with pytest.raises(RuntimeError, match="refused write"):
        copy_zip(src, frozen)


@pytest.mark.unit
def test_snapshot_aligns_harvest_live_to_pin(tmp_path: Path) -> None:
    from lumina_core.birth.birth_exit_policy_export import file_sha256
    from lumina_core.maturity.awakening.freeze_pin import pin_birth_pi_star

    _write_birth_plant(tmp_path)
    pi_star = tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    plant = file_sha256(pi_star)
    pin_birth_pi_star(tmp_path)
    pi_star.write_bytes(b"harvest-8cc435c6-not-this-birth")
    meta = pi_star.with_name("birth_exit_pi_star.json")
    meta.write_text('{"sha256":"harvest"}', encoding="utf-8")
    freeze = snapshot_birth_freeze(tmp_path)
    assert file_sha256(pi_star) == plant
    key = next(k for k in freeze if str(k).endswith("birth_exit_pi_star.zip"))
    assert freeze[key] == plant
    assert_birth_freeze(tmp_path, freeze)


@pytest.mark.unit
def test_freeze_pin_restores_mutated_pi_star(tmp_path: Path) -> None:
    from lumina_core.birth.birth_exit_policy_export import file_sha256
    from lumina_core.maturity.awakening.freeze_pin import pin_birth_pi_star, restore_birth_pi_star_from_pin

    _write_birth_plant(tmp_path)
    pi_star = tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    original = file_sha256(pi_star)
    pin_birth_pi_star(tmp_path)
    pi_star.write_bytes(b"harvest-overwrite")
    assert file_sha256(pi_star) != original
    assert restore_birth_pi_star_from_pin(tmp_path) is True
    assert file_sha256(pi_star) == original


@pytest.mark.unit
def test_shot_does_not_mutate_birth_artifacts(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    freeze = snapshot_birth_freeze(tmp_path)
    seen: dict[str, Any] = {}
    result = run_live_awakening_shot(
        tmp_path,
        split_loader=_split,
        train_fn=lambda **kw: _train_stub(seen=seen, **kw),
        eval_fn=lambda **kw: _eval_stub(seen=seen, oos=0.34, n=600, **kw),
    )
    assert result["passed"] is False
    assert snapshot_birth_freeze(tmp_path) == freeze
    data = load_continuum(tmp_path)
    assert data["phase_records"]["birth"]["exit_proofs"] == [
        "foundation_five_receipts_v2",
        "foundation_fitness_vector",
    ]


@pytest.mark.unit
def test_shot_honest_fail_insufficient_lift(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    seen: dict[str, Any] = {}
    result = run_live_awakening_shot(
        tmp_path,
        split_loader=_split,
        train_fn=lambda **kw: _train_stub(seen=seen, **kw),
        eval_fn=lambda **kw: _eval_stub(seen=seen, oos=0.34, n=600, **kw),
    )
    assert result["passed"] is False
    assert result["birth_exit_winrate"] == pytest.approx(0.333333)
    assert result["polish_oos_winrate"] == pytest.approx(0.34)
    assert any("parent_replay_missing" in r for r in result["reasons"])
    rec = json.loads(evolution_proof_state_path(tmp_path).read_text(encoding="utf-8"))
    assert rec["passed"] is False
    assert rec.get("child_sha256")
    assert rec.get("init_sha256")
    assert evolution_proof_passed(tmp_path) is False
    assert "hold-a" not in seen["train_ids"]
    assert "train-a" not in seen["eval_ids"]
    assert live_child_zip(tmp_path).is_file()


@pytest.mark.unit
def test_shot_winrate_lift_without_replay_does_not_pass(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    seen: dict[str, Any] = {}
    result = run_live_awakening_shot(
        tmp_path,
        split_loader=_split,
        train_fn=lambda **kw: _train_stub(seen=seen, **kw),
        eval_fn=lambda **kw: _eval_stub(seen=seen, oos=0.40, n=600, **kw),
    )
    assert result["passed"] is False
    assert result["winrate_lift"] == pytest.approx(0.066667, abs=1e-6)
    assert result["parent_replay_present"] is False
    assert evolution_proof_passed(tmp_path) is False


@pytest.mark.unit
def test_shot_passes_on_paired_closes(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    seen: dict[str, Any] = {}
    child = []
    parent = []
    for index in range(8):
        day = f"2026-03-{index + 1:02d}"
        child.append({"day": day, "trade_r": 0.30, "plant": False})
        parent.append({"day": day, "trade_r": -0.20, "plant": False})

    def _eval(**kw: Any) -> dict[str, Any]:
        base = _eval_stub(seen=seen, oos=0.36, n=600, **kw)
        base["child_closes"] = child
        base["parent_closes"] = parent
        return base

    result = run_live_awakening_shot(
        tmp_path,
        split_loader=_split,
        train_fn=lambda **kw: _train_stub(seen=seen, **kw),
        eval_fn=_eval,
    )
    assert result["passed"] is True
    assert float(result["paired_ci_low"]) >= 0.05
    assert evolution_proof_passed(tmp_path) is True
    assert "hold-a" not in seen["train_ids"]


@pytest.mark.unit
def test_default_train_never_feeds_holdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.maturity.phase_runners.awakening_shot_io import default_train

    seen: dict[str, Any] = {}

    def _env(ticks: list[dict[str, Any]], **_kwargs: Any) -> None:
        seen["ids"] = [row.get("id") for row in ticks]
        raise RuntimeError("tape-captured")

    monkeypatch.setattr(
        "lumina_core.birth.awakening_select_env.make_select_train_env",
        _env,
    )
    with pytest.raises(RuntimeError, match="tape-captured"):
        default_train(
            train=[{"id": "train-a", "last": 1.0}],
            holdout=[{"id": "hold-a", "last": 2.0}],
            init_path=tmp_path / "missing.zip",
            child_path=tmp_path / "child.zip",
            workspace=tmp_path,
            reports=tmp_path,
            pin=10,
        )
    assert seen["ids"] == ["train-a"]


@pytest.mark.unit
def test_default_train_stop_requested_before_learn() -> None:
    from lumina_core.maturity.phase_runners.awakening_shot import AwakeningShotError
    from lumina_core.maturity.phase_runners.awakening_shot_io import default_train

    with pytest.raises(AwakeningShotError, match="stop_requested"):
        default_train(
            train=[{"id": "train-a"}],
            holdout=[{"id": "hold-a"}],
            init_path=Path("missing.zip"),
            child_path=Path("child.zip"),
            workspace=Path("."),
            reports=Path("."),
            pin=10,
            should_stop=lambda: True,
        )


@pytest.mark.unit
def test_default_eval_forwards_should_stop_and_honors_operator_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lumina_core.birth.awakening_grind import GrindLegMetrics
    from lumina_core.maturity.phase_runners.awakening_shot import AwakeningShotError
    from lumina_core.maturity.phase_runners.awakening_shot_io import default_eval

    seen: dict[str, Any] = {}

    def _eval(**kwargs: Any) -> GrindLegMetrics:
        seen["should_stop"] = kwargs.get("should_stop")
        return GrindLegMetrics(stopped=False, holdout_exhausted=True)

    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.run_evaluate_only",
        _eval,
    )
    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.resolve_awakening_occupancy_seed",
        lambda *_a, **_k: (0.27, "test"),
    )
    child = tmp_path / "child.zip"
    child.write_bytes(b"not-a-real-zip")
    ledger = tmp_path / "ledger.jsonl"
    result = default_eval(
        holdout=[{"last": 1.0}],
        child_path=child,
        workspace=tmp_path,
        reports=tmp_path,
        ledger_path=ledger,
        should_stop=lambda: False,
    )
    assert seen["should_stop"] is not None
    assert seen["should_stop"]() is False
    assert result["holdout_exhausted"] is True

    def _stopped(**_kwargs: Any) -> GrindLegMetrics:
        return GrindLegMetrics(stopped=True)

    monkeypatch.setattr(
        "lumina_core.birth.awakening_grind_run.run_evaluate_only",
        _stopped,
    )
    with pytest.raises(AwakeningShotError, match="stop_requested"):
        default_eval(
            holdout=[{"last": 1.0}],
            child_path=child,
            workspace=tmp_path,
            reports=tmp_path,
            ledger_path=ledger,
            should_stop=lambda: False,
        )


@pytest.mark.unit
def test_train_callback_stops_when_operator_requests(tmp_path: Path) -> None:
    from lumina_core.maturity.phase_runners.awakening_shot_io import _timestep_cap_callback

    callback = _timestep_cap_callback(8, workspace=tmp_path, should_stop=lambda: True)
    if callback is None:
        pytest.skip("stable-baselines3 callback base is not importable")
    assert callback._on_step() is False
    assert callback.stopped is True
    assert callback.ran == 0


def _exam_card(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "policy_trades": 500,
        "polish_oos_winrate": 0.402,
        "birth_exit_winrate": 0.30,
        "mean_r": -0.1696,
        "birth_mean_r": -0.399,
        "edge": 0.10,
        "median_loss_r": 0.83,
        "occupancy": 0.27,
        "occupancy_at_nb": 0.268,
        "oos_sharpe": -0.213,
        "oos_dd_pct": 8.4,
        "paired_delta": 0.15,
        "paired_ci_low": 0.08,
        "parent_replay_present": True,
        "child_median_win_r": 0.55,
        "parent_median_win_r": 0.80,
        "child_weight_sha": "child-weight",
        "init_weight_sha": "birth-weight",
        "policy_only": True,
    }
    base.update(overrides)
    return base


def _incumbent_from_exam(**overrides: object) -> dict[str, object]:
    child = _exam_card(**overrides)
    return {
        "incumbent_n_b": child["policy_trades"],
        "incumbent_wr": child["polish_oos_winrate"],
        "incumbent_mean_r": child["mean_r"],
        "incumbent_occupancy": child["occupancy"],
        "incumbent_occupancy_at_nb": child["occupancy_at_nb"],
        "incumbent_edge": child["edge"],
        "incumbent_sharpe": child["oos_sharpe"],
        "incumbent_dd_pct": child["oos_dd_pct"],
        "incumbent_median_loss_r": child["median_loss_r"],
        "incumbent_paired_delta": child["paired_delta"],
        "incumbent_paired_ci_low": child["paired_ci_low"],
        "incumbent_parent_replay_present": child["parent_replay_present"],
        "incumbent_child_median_win_r": child["child_median_win_r"],
        "incumbent_parent_median_win_r": child["parent_median_win_r"],
        "incumbent_weight_sha": child["child_weight_sha"],
        "incumbent_init_weight_sha": child["init_weight_sha"],
    }


@pytest.mark.unit
def test_a_ci_clearance_does_not_replace_the_plant_baseline() -> None:
    """First Watch keeps the plant. A later card with a better CI is not the exit."""
    from lumina_core.maturity.awakening.keep_best import keep_block_reason

    collapsed = _incumbent_from_exam(
        polish_oos_winrate=0.384,
        mean_r=-0.1702,
        paired_delta=0.26,
        paired_ci_low=0.113,
        child_median_win_r=0.425,
        parent_median_win_r=0.962,
        child_weight_sha="incumbent-weight",
    )
    passer = _exam_card(paired_delta=0.15, paired_ci_low=0.08)
    assert keep_block_reason(passer, collapsed) is not None


@pytest.mark.unit
def test_keeper_still_ranks_two_exam_passes_by_paired_delta() -> None:
    from lumina_core.maturity.awakening.keep_best import keep_block_reason

    incumbent = _incumbent_from_exam(paired_delta=0.20, paired_ci_low=0.09)
    lower = _exam_card(paired_delta=0.12, paired_ci_low=0.06)
    assert keep_block_reason(lower, incumbent) == "paired_delta_not_higher"


@pytest.mark.unit
def test_keeper_does_not_drop_a_higher_paired_delta_for_a_mean_r_twitch() -> None:
    from lumina_core.maturity.awakening.keep_best import child_beats_incumbent, keep_block_reason

    incumbent = {
        "incumbent_n_b": 940,
        "incumbent_wr": 0.382,
        "incumbent_mean_r": -0.153,
        "incumbent_occupancy": 0.40,
        "incumbent_occupancy_at_nb": 0.40,
        "incumbent_sharpe": -0.23,
        "incumbent_dd_pct": 12.6,
        "incumbent_paired_delta": 0.08,
        "incumbent_paired_ci_low": 0.04,
    }
    twitch = {
        "policy_trades": 947,
        "polish_oos_winrate": 0.361,
        "mean_r": -0.144,
        "occupancy": 0.40,
        "occupancy_at_nb": 0.269,
        "oos_sharpe": -0.22,
        "oos_dd_pct": 11.9,
        "paired_delta": 0.02,
        "paired_ci_low": 0.01,
    }
    assert keep_block_reason(twitch, incumbent) == "paired_delta_not_higher"
    assert child_beats_incumbent(twitch, incumbent) is False
    closer = dict(twitch)
    closer["paired_delta"] = 0.10
    closer["paired_ci_low"] = 0.06
    closer["polish_oos_winrate"] = 0.36
    closer["mean_r"] = -0.20
    assert child_beats_incumbent(closer, incumbent) is True


@pytest.mark.unit
def test_shot_honest_pass_on_oos_floor(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    result = run_live_awakening_shot(
        tmp_path,
        split_loader=_split,
        train_fn=lambda **kw: _train_stub(seen={}, **kw),
        eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.45, n=600, **kw),
    )
    assert result["passed"] is True
    assert evolution_proof_passed(tmp_path) is True


@pytest.mark.unit
def test_run_awakening_uses_shot_then_stays_incomplete_on_fail(tmp_path: Path) -> None:
    from lumina_core.maturity.phase_runners.awakening import run_awakening

    _write_birth_plant(tmp_path)
    (tmp_path / "state" / "twin_mode_metrics_summary.json").write_text(
        '{"samples": 25}', encoding="utf-8"
    )
    freeze = snapshot_birth_freeze(tmp_path)

    def _shot(workspace_root: Path | str, **_: Any) -> dict[str, Any]:
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.34, n=600, **kw),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_shot,
    ):
        result = run_awakening(tmp_path)
    assert result["ok"] is False
    missing = result.get("missing") or []
    assert missing
    assert any("lift" in str(m) or "occupancy" in str(m) or "n_B" in str(m) for m in missing)
    learned = (load_continuum(tmp_path).get("phase_records") or {}).get("awakening", {}).get("learned") or {}
    assert float(learned.get("wr") or learned.get("probe_oos_wr") or 0.0) == pytest.approx(0.34)
    assert snapshot_birth_freeze(tmp_path) == freeze
    data = load_continuum(tmp_path)
    assert "awakening" not in data["completed_phases"]
    assert "birth" in data["completed_phases"]


@pytest.mark.unit
def test_run_awakening_shot_pass_is_not_enough_without_and(tmp_path: Path) -> None:
    from lumina_core.maturity.phase_runners.awakening import run_awakening

    _write_birth_plant(tmp_path)
    (tmp_path / "state" / "twin_mode_metrics_summary.json").write_text(
        '{"samples": 25}', encoding="utf-8"
    )
    freeze = snapshot_birth_freeze(tmp_path)

    def _shot(workspace_root: Path | str, **_: Any) -> dict[str, Any]:
        return _REAL_SHOT(
            workspace_root,
            split_loader=_split,
            train_fn=lambda **kw: _train_stub(seen={}, **kw),
            eval_fn=lambda **kw: _eval_stub(seen={}, oos=0.40, n=600, **kw),
        )

    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot.run_live_awakening_shot",
        side_effect=_shot,
    ):
        result = run_awakening(tmp_path)
    assert result["ok"] is False
    missing = result.get("missing") or []
    assert any("twin_watch" in str(m) or "occupancy" in str(m) for m in missing)
    data = load_continuum(tmp_path)
    assert "awakening" not in data["completed_phases"]
    assert snapshot_birth_freeze(tmp_path) == freeze


@pytest.mark.unit
def test_cycle_zero_reuses_its_own_ledger_as_the_parent_replay(tmp_path: Path) -> None:
    from lumina_core.maturity.phase_runners.awakening_shot import _paired_for_shot

    frozen = tmp_path / "birth_exit_pi_star.zip"
    child = tmp_path / "awakening_live_pi_star.zip"
    frozen.write_bytes(b"same-frozen-policy")
    child.write_bytes(b"same-frozen-policy")
    ledger = tmp_path / "awakening_live_holdout.jsonl"
    lines = []
    for index in range(8):
        day = f"2026-06-{index + 1:02d}"
        lines.append(
            '{"entry_bar_index": %d, "trade_r": -0.2, "plant": false, "ts_iso": "%sT00:00:00"}\n'
            % (index, day)
        )
    ledger.write_text("".join(lines), encoding="utf-8")

    def _boom(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("frozen parent was walked a second time")

    book = _paired_for_shot(
        {},
        eval_fn=None,
        holdout=[{"timestamp": f"2026-06-{i + 1:02d}T00:00:00"} for i in range(8)],
        frozen_path=frozen,
        child_path=child,
        child_ledger=ledger,
        workspace=tmp_path,
        reports=tmp_path,
        should_stop=None,
        progress=None,
        cycle=0,
    )
    assert book["parent_replay_present"] is True
    assert book["paired_delta"] == pytest.approx(0.0)
    with patch(
        "lumina_core.maturity.phase_runners.awakening_shot_io.default_eval",
        _boom,
    ):
        again = _paired_for_shot(
            {},
            eval_fn=None,
            holdout=[],
            frozen_path=frozen,
            child_path=tmp_path / "missing-student.zip",
            child_ledger=ledger,
            workspace=tmp_path,
            reports=tmp_path,
            should_stop=None,
            cycle=1,
        )
    assert again["parent_replay_present"] is True
