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
    (root / "state" / "lumina_birth_fitness_vector.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_pi_star(root: Path, blob: bytes = b"frozen-pi-star-bytes") -> Path:
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
    child_path.write_bytes(b"awakening-child-policy")
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
    assert any("insufficient lift" in r for r in result["reasons"])
    rec = json.loads(evolution_proof_state_path(tmp_path).read_text(encoding="utf-8"))
    assert rec["passed"] is False
    assert evolution_proof_passed(tmp_path) is False
    assert "hold-a" not in seen["train_ids"]
    assert "train-a" not in seen["eval_ids"]
    assert live_child_zip(tmp_path).is_file()


@pytest.mark.unit
def test_shot_honest_pass_on_lift(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    seen: dict[str, Any] = {}
    result = run_live_awakening_shot(
        tmp_path,
        split_loader=_split,
        train_fn=lambda **kw: _train_stub(seen=seen, **kw),
        eval_fn=lambda **kw: _eval_stub(seen=seen, oos=0.40, n=600, **kw),
    )
    assert result["passed"] is True
    assert result["winrate_lift"] == pytest.approx(0.066667, abs=1e-6)
    assert evolution_proof_passed(tmp_path) is True
    rec = json.loads(evolution_proof_state_path(tmp_path).read_text(encoding="utf-8"))
    assert rec["birth_exit_winrate"] == pytest.approx(0.333333)
    assert rec["polish_oos_winrate"] == pytest.approx(0.40)
    assert rec["holdout_trades"] == 600


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
    (tmp_path / "state" / "twin_mode_metrics_summary.json").write_text('{"samples": 25}', encoding="utf-8")
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
    (tmp_path / "state" / "twin_mode_metrics_summary.json").write_text('{"samples": 25}', encoding="utf-8")
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
def test_shot_default_split_uses_exam_loader(tmp_path: Path) -> None:
    _write_birth_plant(tmp_path)
    freeze = snapshot_birth_freeze(tmp_path)
    seen: dict[str, Any] = {}
    loads: list[Path] = []

    def _exam(root: Path, **_k: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        loads.append(root)
        return _split(root)

    with patch(
        "lumina_core.maturity.awakening.exam_tape.load_awakening_exam_split",
        side_effect=_exam,
    ):
        result = run_live_awakening_shot(
            tmp_path,
            train_fn=lambda **kw: _train_stub(seen=seen, **kw),
            eval_fn=lambda **kw: _eval_stub(seen=seen, oos=0.34, n=600, **kw),
        )
    assert loads == [tmp_path]
    assert seen["train_ids"] == ["train-a", "train-b"]
    assert seen["eval_ids"] == ["hold-a", "hold-b"]
    assert result["passed"] is False
    assert snapshot_birth_freeze(tmp_path) == freeze
