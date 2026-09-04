"""Awakening SELECT_OBJ P_BOUNCE_WEAK: protocol, predicate, license."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_path_exit_k3 import (
    INIT_SHA256,
    INIT_ZIP_NAME,
    PATH_A_NAME,
    PATH_EARLY_A_NAME,
    PATH_EXIT_K3_SHADOW,
    T_LOCK,
)
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import EPS_SIT, MFE_LIFE, PATH_SHAPE_A_NAME, PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select_obj_bounce import (
    BOUNCE_WEAK,
    FORBIDDEN_WRITE_NAMES,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    T025_A_NAME,
    SelectObjBounceProtocolError,
    assert_isolated_write,
    bounce_r,
    honesty_paragraph,
    overall_select_obj_bounce_string,
    pred_bounce_weak,
)
from lumina_core.birth.awakening_select_obj_bounce_flags import (
    TAG_OBJ_NONE,
    TAG_OBJ_SPLIT,
    TAG_S_HARM,
    TAG_S_MISSING,
    license_obj,
)
from lumina_core.birth.awakening_select_obj_bounce_path import inspect_select_obj_bounce_protocol


def _row(*, unreal: float | None, mae: float | None) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if unreal is not None:
        row["path_k3_unreal_r"] = unreal
    if mae is not None:
        row["path_k3_mae_r"] = mae
    return row


def _split(*, split: bool = True, harm: bool = False, missing: bool = False) -> dict[str, Any]:
    return {"S_SPLIT": split, "S_HARM": harm, "S_MISSING": missing}


def test_inspect_select_obj_bounce_protocol_complete() -> None:
    dump = inspect_select_obj_bounce_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_bounce_weak_is_050() -> None:
    assert BOUNCE_WEAK == 0.50
    src = Path("lumina_core/birth/awakening_select_obj_bounce.py").read_text(encoding="utf-8")
    assert "BOUNCE_WEAK = 0.50" in src


def test_eps_sit_still_005() -> None:
    assert EPS_SIT == 0.05
    src = Path("lumina_core/birth/awakening_path_shape_k3_dead.py").read_text(encoding="utf-8")
    assert "EPS_SIT = 0.05" in src


def test_mfe_life_still_025() -> None:
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
    with pytest.raises(SelectObjBounceProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_A_NAME)


def test_forbidden_write_path_exit_k3_jsonl(tmp_path: Path) -> None:
    assert PATH_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(SelectObjBounceProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_A_NAME)


def test_forbidden_write_t025_jsonl(tmp_path: Path) -> None:
    assert T025_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(SelectObjBounceProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / T025_A_NAME)


def test_forbidden_write_shape_jsonl(tmp_path: Path) -> None:
    assert PATH_SHAPE_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(SelectObjBounceProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_SHAPE_A_NAME)


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    assert INIT_ZIP_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(SelectObjBounceProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / INIT_ZIP_NAME)


def test_new_modules_under_400_loc() -> None:
    files = [
        "lumina_core/birth/awakening_select_obj_bounce.py",
        "lumina_core/birth/awakening_select_obj_bounce_flags.py",
        "lumina_core/birth/awakening_select_obj_bounce_path.py",
        "lumina_core/birth/awakening_select_obj_bounce_tables.py",
        "lumina_core/birth/awakening_select_obj_bounce_report.py",
        "lumina_core/birth/awakening_select_obj_bounce_run.py",
    ]
    for rel in files:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


def test_run_module_does_not_import_evaluate_only() -> None:
    src = Path("lumina_core/birth/awakening_select_obj_bounce_run.py").read_text(encoding="utf-8")
    assert "run_evaluate_only" not in src


def test_bounce_030_is_weak() -> None:
    row = _row(unreal=-3.20, mae=-3.50)
    assert bounce_r(row) == pytest.approx(0.30)
    assert pred_bounce_weak(row) is True


def test_bounce_050_is_weak() -> None:
    row = _row(unreal=-3.00, mae=-3.50)
    assert bounce_r(row) == pytest.approx(0.50)
    assert pred_bounce_weak(row) is True


def test_bounce_060_is_not_weak() -> None:
    row = _row(unreal=-2.90, mae=-3.50)
    assert bounce_r(row) == pytest.approx(0.60)
    assert pred_bounce_weak(row) is False


def test_bounce_wick_recovered_346_is_not_weak() -> None:
    row = _row(unreal=-0.05, mae=-3.51)
    assert bounce_r(row) == pytest.approx(3.46)
    assert pred_bounce_weak(row) is False


def test_missing_mae_false() -> None:
    assert pred_bounce_weak(_row(unreal=-3.20, mae=None)) is False


def test_missing_unreal_false() -> None:
    assert pred_bounce_weak(_row(unreal=None, mae=-3.50)) is False


def test_pred_source_has_no_t_tokens() -> None:
    src = Path("lumina_core/birth/awakening_select_obj_bounce.py").read_text(encoding="utf-8")
    start = src.index("def bounce_r")
    mid = src.index("def pred_bounce_weak")
    end = src.index("\ndef ", mid + 1)
    body = src[start:end]
    assert "T_LOCK" not in body
    assert "T_FP" not in body
    assert "EPS_SIT" not in body
    assert "-0.25" not in body


def test_obj_split_only_when_both() -> None:
    out = license_obj(_split(split=True), _split(split=True))
    assert out["tag"] == TAG_OBJ_SPLIT
    assert out["law"] == "NONE"
    assert out["licensed_next_family"] == "SELECT_OBJ:P_BOUNCE_WEAK"


def test_a_only_split_is_obj_none() -> None:
    out = license_obj(_split(split=True), _split(split=False))
    assert out["tag"] == TAG_OBJ_NONE
    assert out["S_SPLIT_A"] is True
    assert out["S_SPLIT_B"] is False
    assert out["licensed_next_family"] == "H_NONE"


def test_b_only_split_is_obj_none() -> None:
    out = license_obj(_split(split=False), _split(split=True))
    assert out["tag"] == TAG_OBJ_NONE


def test_s_harm_either_leg() -> None:
    assert license_obj(_split(harm=True, split=True), _split(split=True))["tag"] == TAG_S_HARM
    assert license_obj(_split(split=True), _split(harm=True, split=True))["tag"] == TAG_S_HARM


def test_s_missing() -> None:
    assert license_obj(_split(missing=True), _split(split=True))["tag"] == TAG_S_MISSING
    assert license_obj(_split(split=True), _split(missing=True))["tag"] == TAG_S_MISSING


def test_law_always_none() -> None:
    assert license_obj(_split(split=True), _split(split=True))["law"] == "NONE"
    assert license_obj(_split(split=True), _split(split=False))["law"] == "NONE"
    assert license_obj(_split(harm=True), _split(split=True))["law"] == "NONE"
    assert license_obj(_split(missing=True), _split(split=True))["law"] == "NONE"
    assert INIT_SHA256.startswith("8cc435c6")
    assert bool(PATH_EXIT_K3_SHADOW.get()) is False
    assert bool(PATH_SHAPE_K3_SHADOW.get()) is False
    assert overall_select_obj_bounce_string(gate1_complete=True) == OVERALL_MEASURE
    assert overall_select_obj_bounce_string(path_early_present=False) == OVERALL_INCONCLUSIVE
    assert "BOUNCE_WEAK=0.50" in honesty_paragraph()
