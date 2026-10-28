"""Awakening MARK_EYES: protocol, eyes, license. New body. No parent weight load."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_mark_eyes import (
    CHILD_ZIP_NAME,
    FORBIDDEN_INIT_NAMES,
    FORBIDDEN_WRITE_NAMES,
    HOLD_NORM,
    INIT_ZIP_NAME,
    MARK_EYES_OBS_DIM,
    MARK_EYES_PPO_TIMESTEPS,
    PATH_EARLY_A_NAME,
    PATH_EXIT_A_NAME,
    MarkEyesProtocolError,
    assert_budget,
    assert_forbidden_init,
    assert_isolated_write,
    assert_train_seed,
)
from lumina_core.birth.awakening_mark_eyes_flags import license_eyes
from lumina_core.birth.awakening_mark_eyes_obs import MarkEyesState, concat_mark_eyes
from lumina_core.birth.awakening_mark_eyes_path import inspect_mark_eyes_protocol
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.rl.observation_builder import OBSERVATION_DIM


def _moved(*, hole: bool = True, harm: bool = False, missing: bool = False) -> dict[str, Any]:
    return {"HOLE_MOVED": hole, "S_HARM": harm, "S_MISSING": missing, "S_MISSING_HOOK": missing}


def test_inspect_mark_eyes_protocol_complete() -> None:
    dump = inspect_mark_eyes_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_observation_dim_still_43() -> None:
    assert OBSERVATION_DIM == 43
    src = Path("lumina_core/rl/observation_builder.py").read_text(encoding="utf-8")
    assert "OBSERVATION_DIM = 43" in src


def test_mark_eyes_dim_46() -> None:
    assert MARK_EYES_OBS_DIM == 46
    src = Path("lumina_core/birth/awakening_mark_eyes.py").read_text(encoding="utf-8")
    assert "MARK_EYES_OBS_DIM = 46" in src


def test_timesteps_pin_10000() -> None:
    assert MARK_EYES_PPO_TIMESTEPS == 10_000
    assert assert_budget(10_000) == 10_000
    with pytest.raises(MarkEyesProtocolError):
        assert_budget(9_999)
    with pytest.raises(MarkEyesProtocolError):
        assert_budget(20_000)


def test_hold_norm_120() -> None:
    assert HOLD_NORM == 120.0
    src = Path("lumina_core/birth/awakening_mark_eyes.py").read_text(encoding="utf-8")
    assert "HOLD_NORM = 120.0" in src


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    assert INIT_ZIP_NAME in FORBIDDEN_WRITE_NAMES
    assert "birth_exit_pi_star.zip" in FORBIDDEN_WRITE_NAMES
    with pytest.raises(MarkEyesProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / INIT_ZIP_NAME)


def test_forbidden_write_path_early_jsonl(tmp_path: Path) -> None:
    assert PATH_EARLY_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(MarkEyesProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_A_NAME)


def test_forbidden_write_path_exit_k3_jsonl(tmp_path: Path) -> None:
    assert PATH_EXIT_A_NAME in FORBIDDEN_WRITE_NAMES
    assert "path_exit_k3_A_close_ledger.jsonl" in FORBIDDEN_WRITE_NAMES
    with pytest.raises(MarkEyesProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "path_exit_k3_A_close_ledger.jsonl")


def test_forbidden_init_parent_zip(tmp_path: Path) -> None:
    assert "birth_exit_pi_star.zip" in FORBIDDEN_INIT_NAMES
    with pytest.raises(MarkEyesProtocolError, match="refused"):
        assert_forbidden_init(tmp_path / "birth_exit_pi_star.zip")


def test_forbidden_init_select_zip(tmp_path: Path) -> None:
    assert "awakening_select_pi_star.zip" in FORBIDDEN_INIT_NAMES
    with pytest.raises(MarkEyesProtocolError, match="refused"):
        assert_forbidden_init(tmp_path / "awakening_select_pi_star.zip")


def test_forbidden_init_hole_tax_zip(tmp_path: Path) -> None:
    assert "awakening_hole_tax_pi_star.zip" in FORBIDDEN_INIT_NAMES
    with pytest.raises(MarkEyesProtocolError, match="refused"):
        assert_forbidden_init(tmp_path / "awakening_hole_tax_pi_star.zip")


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_new_modules_under_400_loc() -> None:
    files = [
        "lumina_core/birth/awakening_mark_eyes.py",
        "lumina_core/birth/awakening_mark_eyes_obs.py",
        "lumina_core/birth/awakening_mark_eyes_env.py",
        "lumina_core/birth/awakening_mark_eyes_train.py",
        "lumina_core/birth/awakening_mark_eyes_eval.py",
        "lumina_core/birth/awakening_mark_eyes_flags.py",
        "lumina_core/birth/awakening_mark_eyes_path.py",
        "lumina_core/birth/awakening_mark_eyes_tables.py",
        "lumina_core/birth/awakening_mark_eyes_report.py",
        "lumina_core/birth/awakening_mark_eyes_run.py",
    ]
    for rel in files:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


def test_hooks_default_false() -> None:
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False


def test_flat_extra_is_zero() -> None:
    state = MarkEyesState()
    state.on_step(position=0, unreal_r=-0.5)
    assert state.extra_vec() == (0.0, 0.0, 0.0)


def test_first_bar_mae_equals_unreal() -> None:
    state = MarkEyesState()
    state.on_step(position=1, unreal_r=-0.20)
    extra = state.extra_vec()
    assert extra[0] == pytest.approx(-0.20)
    assert extra[1] == pytest.approx(-0.20)


def test_mae_tracks_min_unreal() -> None:
    state = MarkEyesState()
    state.on_step(position=1, unreal_r=-0.10)
    state.on_step(position=1, unreal_r=-0.40)
    state.on_step(position=1, unreal_r=-0.05)
    extra = state.extra_vec()
    assert extra[0] == pytest.approx(-0.05)
    assert extra[1] == pytest.approx(-0.40)


def test_mae_does_not_use_wick() -> None:
    src = Path("lumina_core/birth/awakening_mark_eyes_obs.py").read_text(encoding="utf-8")
    start = src.index("def on_step")
    end = src.index("\n    def extra_vec")
    body = src[start:end]
    assert "high" not in body
    assert "low" not in body
    assert "mae_usd" not in body
    assert "mfe" not in body


def test_bars_held_norm_caps_at_one() -> None:
    state = MarkEyesState()
    for _ in range(200):
        state.on_step(position=1, unreal_r=-0.01)
    extra = state.extra_vec()
    assert extra[2] == pytest.approx(1.0)


def test_concat_rejects_wrong_base_len() -> None:
    with pytest.raises(MarkEyesProtocolError, match="len\\(base\\)==43"):
        concat_mark_eyes([0.0] * 42, (0.0, 0.0, 0.0))
    out = concat_mark_eyes([0.0] * 43, (0.1, -0.2, 0.5))
    assert out.shape == (46,)
    assert float(out[43]) == pytest.approx(0.1)


def test_obs_source_has_no_t_tokens() -> None:
    src = Path("lumina_core/birth/awakening_mark_eyes_obs.py").read_text(encoding="utf-8")
    assert "T_LOCK" not in src
    assert "T_FP" not in src
    assert "EPS_SIT" not in src
    assert "BOUNCE_WEAK" not in src
    assert "-0.25" not in src


def test_eyes_ok_only_when_both() -> None:
    out = license_eyes(_moved(hole=True), _moved(hole=True))
    assert out["tag"] == "EYES_OK"
    assert out["law"] == "SHADOW"
    assert out["licensed_next_family"] == "AWAKENING_MARK_EYES"


def test_a_only_hole_moved_is_eyes_fail() -> None:
    out = license_eyes(_moved(hole=True), _moved(hole=False))
    assert out["tag"] == "EYES_FAIL"
    assert out["law"] == "NONE"


def test_b_only_hole_moved_is_eyes_fail() -> None:
    out = license_eyes(_moved(hole=False), _moved(hole=True))
    assert out["tag"] == "EYES_FAIL"


def test_s_missing() -> None:
    out = license_eyes(_moved(missing=True), _moved(hole=True))
    assert out["tag"] == "S_MISSING"
    assert out["law"] == "NONE"


def test_law_shadow_only_on_eyes_ok() -> None:
    assert license_eyes(_moved(hole=True), _moved(hole=True))["law"] == "SHADOW"
    assert license_eyes(_moved(hole=True), _moved(hole=False))["law"] == "NONE"
    assert license_eyes(_moved(missing=True), _moved(missing=True))["law"] == "NONE"
    assert license_eyes(_moved(harm=True, hole=False), _moved(hole=False))["law"] == "NONE"


def test_child_zip_name() -> None:
    assert CHILD_ZIP_NAME == "awakening_mark_eyes_pi_star.zip"


def test_holdout_seed_refused() -> None:
    with pytest.raises(MarkEyesProtocolError):
        assert_train_seed(20260902)
    with pytest.raises(MarkEyesProtocolError):
        assert_train_seed(20260903)
