"""Awakening PATH_EXIT K3 T025: protocol, T_FP, ContextVar, license, runner."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.awakening_path_exit_k3 import (
    INIT_SHA256,
    PATH_A_NAME,
    PATH_EARLY_A_NAME,
    PATH_EXIT_K3_SHADOW,
    PATH_EXIT_K3_THRESHOLD,
    T_LOCK,
    TRAIN_SEED,
    assert_eval_seed,
    assert_not_evaluated_policy,
    should_path_exit_k3,
)
from lumina_core.birth.awakening_path_exit_k3_t025 import (
    FORBIDDEN_WRITE_NAMES,
    INIT_ZIP_NAME,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    T_FP,
    PathExitK3T025ProtocolError,
    assert_isolated_write,
    honesty_paragraph,
    overall_path_exit_k3_t025_string,
)
from lumina_core.birth.awakening_path_exit_k3_t025_flags import (
    TAG_S_HARM,
    TAG_S_MISSING,
    TAG_TRANSFER_FAIL,
    TAG_TRANSFER_OK,
    assert_n_exit_not_tlock_clone,
    license_transfer,
)
from lumina_core.birth.awakening_path_exit_k3_t025_path import inspect_path_exit_k3_t025_protocol


def _moved(*, hole: bool = True, harm: bool = False, missing: bool = False) -> dict[str, Any]:
    return {"HOLE_MOVED": hole, "S_HARM": harm, "S_MISSING_HOOK": missing}


def test_inspect_path_exit_k3_t025_protocol_complete() -> None:
    dump = inspect_path_exit_k3_t025_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_t_fp_is_minus_quarter() -> None:
    assert T_FP == -0.25
    src = Path("lumina_core/birth/awakening_path_exit_k3_t025.py").read_text(encoding="utf-8")
    assert "T_FP = -0.25" in src


def test_t_lock_literal_unchanged() -> None:
    assert T_LOCK == -0.04787176712367987
    src = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    assert "T_LOCK = -0.04787176712367987" in src
    assert "PATH_EXIT_K3_THRESHOLD: ContextVar[float]" in src


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_forbidden_write_path_exit_k3_jsonl(tmp_path: Path) -> None:
    assert PATH_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathExitK3T025ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_A_NAME)


def test_forbidden_write_path_early_jsonl(tmp_path: Path) -> None:
    assert PATH_EARLY_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathExitK3T025ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_A_NAME)


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    assert INIT_ZIP_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathExitK3T025ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / INIT_ZIP_NAME)


def test_should_default_none_uses_t_lock() -> None:
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=-0.24,
        )
        is True
    )


def test_should_tfp_minus_024_false() -> None:
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=-0.24,
            threshold=T_FP,
        )
        is False
    )


def test_should_tfp_minus_025_true() -> None:
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=-0.25,
            threshold=T_FP,
        )
        is True
    )


def test_should_disabled_false() -> None:
    assert (
        should_path_exit_k3(
            enabled=False,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=-0.25,
            threshold=T_FP,
        )
        is False
    )


def test_should_plant_false() -> None:
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=False,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=-0.25,
            threshold=T_FP,
        )
        is False
    )


def test_should_k_not_3_false() -> None:
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=5,
            unreal_r=-0.25,
            threshold=T_FP,
        )
        is False
    )


def test_should_unreal_none_false() -> None:
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=None,
            threshold=T_FP,
        )
        is False
    )


def test_contextvar_reset_restores_t_lock() -> None:
    tok = PATH_EXIT_K3_THRESHOLD.set(T_FP)
    try:
        assert (
            should_path_exit_k3(
                enabled=True,
                is_policy=True,
                entry_regime="NEUTRAL",
                bars_from_entry=3,
                unreal_r=-0.24,
            )
            is False
        )
    finally:
        PATH_EXIT_K3_THRESHOLD.reset(tok)
    assert (
        should_path_exit_k3(
            enabled=True,
            is_policy=True,
            entry_regime="NEUTRAL",
            bars_from_entry=3,
            unreal_r=-0.24,
        )
        is True
    )
    assert float(PATH_EXIT_K3_THRESHOLD.get()) == T_LOCK


def test_transfer_ok_only_when_both_hole_moved() -> None:
    out = license_transfer(_moved(hole=True), _moved(hole=True))
    assert out["tag"] == TAG_TRANSFER_OK
    assert out["law"] == "SHADOW"
    assert out["HOLE_MOVED_A"] is True
    assert out["HOLE_MOVED_B"] is True
    assert out["gate1"] == "SHADOW"


def test_a_only_hole_moved_is_transfer_fail() -> None:
    out = license_transfer(_moved(hole=True), _moved(hole=False))
    assert out["tag"] == TAG_TRANSFER_FAIL
    assert out["HOLE_MOVED_A"] is True
    assert out["HOLE_MOVED_B"] is False


def test_b_only_is_transfer_fail() -> None:
    out = license_transfer(_moved(hole=False), _moved(hole=True))
    assert out["tag"] == TAG_TRANSFER_FAIL
    assert out["HOLE_MOVED_A"] is False
    assert out["HOLE_MOVED_B"] is True


def test_s_harm_either_leg() -> None:
    assert license_transfer(_moved(harm=True, hole=True), _moved(hole=True))["tag"] == TAG_S_HARM
    assert license_transfer(_moved(hole=True), _moved(harm=True, hole=True))["tag"] == TAG_S_HARM


def test_s_missing_hook() -> None:
    assert license_transfer(_moved(missing=True), _moved(hole=True))["tag"] == TAG_S_MISSING
    assert license_transfer(_moved(hole=True), _moved(missing=True))["tag"] == TAG_S_MISSING


def test_t025_eval_sets_and_resets_both_contextvars(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.birth.awakening_path_exit_k3_t025_eval import replay_path_exit_k3_t025

    src = Path("lumina_core/birth/awakening_path_exit_k3_t025_eval.py").read_text(encoding="utf-8")
    assert "PATH_EXIT_K3_SHADOW.set" in src
    assert "PATH_EXIT_K3_THRESHOLD.set" in src
    assert "PATH_EXIT_K3_SHADOW.reset" in src
    assert "PATH_EXIT_K3_THRESHOLD.reset" in src
    seen: dict[str, Any] = {}

    def _armed(**kwargs: Any) -> dict[str, Any]:
        _ = kwargs
        seen["shadow"] = bool(PATH_EXIT_K3_SHADOW.get())
        seen["threshold"] = float(PATH_EXIT_K3_THRESHOLD.get())
        return {"ok": True}

    import lumina_core.birth.awakening_path_exit_k3_t025_eval as eval_mod

    monkeypatch.setattr(eval_mod, "_replay_path_exit_k3_t025_armed", _armed)
    out = replay_path_exit_k3_t025(
        reports_path=Path("."),
        proto={},
        workspace_a=Path("."),
        workspace_b=Path("."),
        rollout_fn=None,
    )
    assert out == {"ok": True}
    assert seen["shadow"] is True
    assert seen["threshold"] == T_FP
    assert bool(PATH_EXIT_K3_SHADOW.get()) is False
    assert float(PATH_EXIT_K3_THRESHOLD.get()) == T_LOCK


def test_k27_eval_does_not_set_threshold_var() -> None:
    eval_src = Path("lumina_core/birth/awakening_path_exit_k3_eval.py").read_text(encoding="utf-8")
    run_src = Path("lumina_core/birth/awakening_path_exit_k3_run.py").read_text(encoding="utf-8")
    assert "PATH_EXIT_K3_THRESHOLD.set" not in eval_src
    assert "PATH_EXIT_K3_THRESHOLD.set" not in run_src


def test_evaluate_only_learn_raises() -> None:
    class _Inner:
        def predict(self, *args: Any, **kwargs: Any) -> Any:
            _ = args, kwargs
            return [0.0, 0.5, 0.002, 0.003], None

        def learn(self, *args: Any, **kwargs: Any) -> Any:
            return self

    wrapped = EvaluateOnlyPolicy(_Inner())
    with pytest.raises(RuntimeError, match="learn\\(\\) forbidden"):
        wrapped.learn(total_timesteps=1)
    assert TRAIN is False
    assert overall_path_exit_k3_t025_string(skip_replay=True) == OVERALL_INCONCLUSIVE
    assert (
        overall_path_exit_k3_t025_string(replay_ran=True, parent_loaded=True, optimizer_steps=0)
        == OVERALL_MEASURE
    )
    assert "T_FP=-0.25" in honesty_paragraph()


def test_refuses_train_seed() -> None:
    with pytest.raises(Exception, match="train seed"):
        assert_eval_seed(TRAIN_SEED)


def test_refuses_control_sha(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3 import CONTROL_ZIP_NAME

    control = tmp_path / CONTROL_ZIP_NAME
    control.write_bytes(b"nope")
    with pytest.raises(Exception, match="refused"):
        assert_not_evaluated_policy(control)


def test_assert_n_exit_tlock_clone_raises() -> None:
    with pytest.raises(PathExitK3T025ProtocolError, match="T_LOCK"):
        assert_n_exit_not_tlock_clone(n_exit_a=50, mean_stamped_threshold_a=T_LOCK)
    with pytest.raises(PathExitK3T025ProtocolError, match=">= 80"):
        assert_n_exit_not_tlock_clone(n_exit_a=80, mean_stamped_threshold_a=T_FP)
    assert_n_exit_not_tlock_clone(n_exit_a=49, mean_stamped_threshold_a=T_FP)


def test_skip_replay_is_inconclusive(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3_t025_run import run_path_exit_k3_t025

    out = run_path_exit_k3_t025(
        reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True
    )
    assert out["overall"] == OVERALL_INCONCLUSIVE
    assert out["skip_replay"] is True
    flags = json.loads(
        (tmp_path / "artifacts" / "awakening_path_exit_k3_t025_flags.json").read_text(encoding="utf-8")
    )
    assert flags["overall"] == OVERALL_INCONCLUSIVE
    assert flags["T_FP"] == -0.25
    assert INIT_SHA256.startswith("8cc435c6")
