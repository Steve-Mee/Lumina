"""Awakening PATH_SHAPE K3 DEAD: protocol, predicate, license, runner."""

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
    T_LOCK,
    TRAIN_SEED,
    assert_eval_seed,
    assert_not_evaluated_policy,
)
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import (
    EPS_SIT,
    FORBIDDEN_WRITE_NAMES,
    INIT_ZIP_NAME,
    MFE_LIFE,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    PATH_SHAPE_K3_SHADOW,
    T025_A_NAME,
    PathShapeK3DeadProtocolError,
    assert_isolated_write,
    honesty_paragraph,
    overall_path_shape_k3_dead_string,
    should_path_shape_k3_dead,
)
from lumina_core.birth.awakening_path_shape_k3_dead_flags import (
    TAG_S_HARM,
    TAG_S_MISSING,
    TAG_SHAPE_NONE,
    TAG_SHAPE_SPLIT,
    TAG_TRANSFER_FAIL,
    TAG_TRANSFER_OK,
    license_shape,
    license_transfer,
)
from lumina_core.birth.awakening_path_shape_k3_dead_path import inspect_path_shape_k3_dead_protocol


def _dead(**kwargs: Any) -> bool:
    base = dict(
        enabled=True,
        is_policy=True,
        entry_regime="NEUTRAL",
        bars_from_entry=3,
        unreal_r=-0.30,
        mae_r=-0.30,
        mfe_r=0.00,
    )
    base.update(kwargs)
    return should_path_shape_k3_dead(**base)


def _split(*, split: bool = True, harm: bool = False, missing: bool = False) -> dict[str, Any]:
    return {"S_SPLIT": split, "S_HARM": harm, "S_MISSING": missing}


def _moved(*, hole: bool = True, harm: bool = False, missing: bool = False) -> dict[str, Any]:
    return {"HOLE_MOVED": hole, "S_HARM": harm, "S_MISSING_HOOK": missing}


def test_inspect_path_shape_k3_dead_protocol_complete() -> None:
    dump = inspect_path_shape_k3_dead_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_eps_sit_is_005() -> None:
    assert EPS_SIT == 0.05
    src = Path("lumina_core/birth/awakening_path_shape_k3_dead.py").read_text(encoding="utf-8")
    assert "EPS_SIT = 0.05" in src


def test_mfe_life_is_025() -> None:
    assert MFE_LIFE == 0.25
    src = Path("lumina_core/birth/awakening_path_shape_k3_dead.py").read_text(encoding="utf-8")
    assert "MFE_LIFE = 0.25" in src


def test_t_lock_literal_unchanged() -> None:
    assert T_LOCK == -0.04787176712367987
    src = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    assert "T_LOCK = -0.04787176712367987" in src
    t025 = Path("lumina_core/birth/awakening_path_exit_k3_t025.py").read_text(encoding="utf-8")
    assert "T_FP = -0.25" in t025
    assert T_FP == -0.25


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_forbidden_write_path_early_jsonl(tmp_path: Path) -> None:
    assert PATH_EARLY_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathShapeK3DeadProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_A_NAME)


def test_forbidden_write_path_exit_k3_jsonl(tmp_path: Path) -> None:
    assert PATH_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathShapeK3DeadProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_A_NAME)


def test_forbidden_write_path_exit_k3_t025_jsonl(tmp_path: Path) -> None:
    assert T025_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathShapeK3DeadProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / T025_A_NAME)


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    assert INIT_ZIP_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathShapeK3DeadProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / INIT_ZIP_NAME)


def test_new_modules_under_400_loc() -> None:
    files = [
        "lumina_core/birth/awakening_path_shape_k3_dead.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_flags.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_path.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_tables.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_report.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_run.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_eval.py",
        "lumina_core/birth/awakening_path_shape_k3_dead_peek.py",
        "lumina_core/birth/awakening_path_exit_k3_hook.py",
    ]
    for rel in files:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


def test_dead_sitting_lifeless_true() -> None:
    assert _dead(unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is True


def test_dead_sitting_but_mfe_life_false() -> None:
    assert _dead(unreal_r=-0.30, mae_r=-0.30, mfe_r=0.26) is False


def test_dead_recovered_off_low_false() -> None:
    assert _dead(unreal_r=-0.05, mae_r=-0.80, mfe_r=0.00) is False


def test_dead_missing_mae_false() -> None:
    assert _dead(mae_r=None) is False


def test_dead_missing_mfe_false() -> None:
    assert _dead(mfe_r=None) is False


def test_dead_missing_unreal_false() -> None:
    assert _dead(unreal_r=None) is False


def test_dead_disabled_false() -> None:
    assert _dead(enabled=False) is False


def test_dead_plant_false() -> None:
    assert _dead(is_policy=False) is False


def test_dead_k_not_3_false() -> None:
    assert _dead(bars_from_entry=5) is False


def test_dead_non_neutral_false() -> None:
    assert _dead(entry_regime="TREND_UP") is False


def test_dead_has_no_t_compare() -> None:
    src = Path("lumina_core/birth/awakening_path_shape_k3_dead.py").read_text(encoding="utf-8")
    start = src.index("def should_path_shape_k3_dead")
    end = src.index("\ndef ", start + 1)
    body = src[start:end]
    assert "T_LOCK" not in body
    assert "T_FP" not in body
    assert "-0.25" not in body
    assert _dead(unreal_r=-0.24, mae_r=None, mfe_r=None) is False


def test_contextvar_reset_restores_false() -> None:
    assert bool(PATH_SHAPE_K3_SHADOW.get()) is False
    tok = PATH_SHAPE_K3_SHADOW.set(True)
    try:
        assert bool(PATH_SHAPE_K3_SHADOW.get()) is True
    finally:
        PATH_SHAPE_K3_SHADOW.reset(tok)
    assert bool(PATH_SHAPE_K3_SHADOW.get()) is False


def test_shape_split_only_when_both() -> None:
    out = license_shape(_split(split=True), _split(split=True))
    assert out["tag"] == TAG_SHAPE_SPLIT
    assert out["law"] == "SHADOW"
    assert out["licensed_next_family"] == "PATH_SHAPE:P_K3_DEAD"


def test_a_only_split_is_shape_none() -> None:
    out = license_shape(_split(split=True), _split(split=False))
    assert out["tag"] == TAG_SHAPE_NONE
    assert out["S_SPLIT_A"] is True
    assert out["S_SPLIT_B"] is False


def test_b_only_split_is_shape_none() -> None:
    out = license_shape(_split(split=False), _split(split=True))
    assert out["tag"] == TAG_SHAPE_NONE


def test_s_harm_either_leg() -> None:
    assert license_shape(_split(harm=True, split=True), _split(split=True))["tag"] == TAG_S_HARM
    assert license_shape(_split(split=True), _split(harm=True, split=True))["tag"] == TAG_S_HARM


def test_s_missing() -> None:
    assert license_shape(_split(missing=True), _split(split=True))["tag"] == TAG_S_MISSING
    assert license_shape(_split(split=True), _split(missing=True))["tag"] == TAG_S_MISSING


def test_transfer_ok_only_when_both_hole_moved() -> None:
    out = license_transfer(_moved(hole=True), _moved(hole=True))
    assert out["tag"] == TAG_TRANSFER_OK
    assert out["law"] == "SHADOW"
    assert out["HOLE_MOVED_A"] is True
    assert out["HOLE_MOVED_B"] is True


def test_a_only_hole_moved_is_transfer_fail() -> None:
    out = license_transfer(_moved(hole=True), _moved(hole=False))
    assert out["tag"] == TAG_TRANSFER_FAIL
    assert out["HOLE_MOVED_A"] is True
    assert out["HOLE_MOVED_B"] is False


def test_gate2_eval_sets_shape_and_not_t_shadow() -> None:
    eval_src = Path("lumina_core/birth/awakening_path_shape_k3_dead_eval.py").read_text(encoding="utf-8")
    run_src = Path("lumina_core/birth/awakening_path_shape_k3_dead_run.py").read_text(encoding="utf-8")
    assert "PATH_SHAPE_K3_SHADOW.set" in eval_src
    assert "PATH_SHAPE_K3_SHADOW.set" in run_src
    assert "PATH_EXIT_K3_SHADOW.set(True)" not in eval_src
    assert "PATH_EXIT_K3_SHADOW.set(True)" not in run_src


def test_k27_eval_does_not_set_shape_var() -> None:
    eval_src = Path("lumina_core/birth/awakening_path_exit_k3_eval.py").read_text(encoding="utf-8")
    run_src = Path("lumina_core/birth/awakening_path_exit_k3_run.py").read_text(encoding="utf-8")
    assert "PATH_SHAPE_K3_SHADOW.set" not in eval_src
    assert "PATH_SHAPE_K3_SHADOW.set" not in run_src


def test_t025_eval_does_not_set_shape_var() -> None:
    eval_src = Path("lumina_core/birth/awakening_path_exit_k3_t025_eval.py").read_text(encoding="utf-8")
    run_src = Path("lumina_core/birth/awakening_path_exit_k3_t025_run.py").read_text(encoding="utf-8")
    assert "PATH_SHAPE_K3_SHADOW.set" not in eval_src
    assert "PATH_SHAPE_K3_SHADOW.set" not in run_src


def test_both_shadows_on_raises() -> None:
    from lumina_core.birth.awakening_path_exit_k3_hook import after_open_telem_path_exit_k3

    stash = {"is_policy": True, "entry_regime": "NEUTRAL", "entry_price": 24000.0, "side": 1}
    env = type("E", (), {"_idx": 1, "_entry_stop_pct": 0.0012, "_path_exit_k3_request": False})()
    tok_s = PATH_SHAPE_K3_SHADOW.set(True)
    tok_t = PATH_EXIT_K3_SHADOW.set(True)
    try:
        with pytest.raises(PathShapeK3DeadProtocolError, match="both on"):
            after_open_telem_path_exit_k3(stash, env, [{}], {}, 2, 1)
    finally:
        PATH_SHAPE_K3_SHADOW.reset(tok_s)
        PATH_EXIT_K3_SHADOW.reset(tok_t)


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
    assert overall_path_shape_k3_dead_string(skip_replay=True, gate2_attempted=True) == OVERALL_INCONCLUSIVE
    assert (
        overall_path_shape_k3_dead_string(gate1_complete=True, replay_ran=False, gate2_attempted=False)
        == OVERALL_MEASURE
    )
    assert "EPS_SIT=0.05" in honesty_paragraph()


def test_refuses_train_seed() -> None:
    with pytest.raises(Exception, match="train seed"):
        assert_eval_seed(TRAIN_SEED)


def test_refuses_control_sha(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3 import CONTROL_ZIP_NAME

    control = tmp_path / CONTROL_ZIP_NAME
    control.write_bytes(b"nope")
    with pytest.raises(Exception, match="refused"):
        assert_not_evaluated_policy(control)


def test_peek_does_not_write_stash_mae() -> None:
    from lumina_core.birth.awakening_path_shape_k3_dead_peek import _peek_excursion_usd

    stash = {"mae_usd": -10.0, "mfe_usd": 4.0, "entry_price": 24000.0, "side": 1}
    before = dict(stash)
    peek_mae, peek_mfe = _peek_excursion_usd(stash, {"high": 24010.0, "low": 23980.0})
    assert stash == before
    assert stash["mae_usd"] == -10.0
    assert peek_mae is not None
    assert peek_mfe is not None
    src = Path("lumina_core/birth/awakening_path_shape_k3_dead_peek.py").read_text(encoding="utf-8")
    assert 'stash["mae_usd"]' not in src


def test_skip_replay_shape_none_is_measure(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_shape_k3_dead_run import run_path_shape_k3_dead

    out = run_path_shape_k3_dead(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True)
    assert out["replay_ran"] is False
    flags = json.loads((tmp_path / "artifacts" / "awakening_path_shape_k3_dead_flags.json").read_text(encoding="utf-8"))
    assert flags["EPS_SIT"] == 0.05
    assert flags["MFE_LIFE"] == 0.25
    assert flags["gate1_tag"] in {TAG_SHAPE_NONE, TAG_S_MISSING}
    assert flags["replay_ran"] is False
    assert INIT_SHA256.startswith("8cc435c6")
