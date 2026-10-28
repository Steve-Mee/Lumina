"""GENESIS_EYES_BUDGET: frozen students, new thick tape, floor 150, no learn."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_eyes_budget import (
    BUDGET_FIXTURE_SEED,
    BUDGET_HOLDOUT_PCT,
    BUDGET_START_ET_ISO,
    FORBIDDEN_TAPE_HASH_5726,
    FORBIDDEN_TAPE_HASH_7E86,
    MIN_TICKS_PER_LEG,
    STUDENT_BIRTH_SHA256,
    STUDENT_EYES_SHA256,
    BudgetProtocolError,
    inspect_budget_protocol,
    refuse_path_early_baseline,
    refuse_this_tape_hash,
)
from lumina_core.birth.genesis_eyes_budget_flags import (
    TAG_BUDGET_FAIL,
    TAG_BUDGET_OK,
    TAG_BUDGET_THIN,
    TAG_S_HARM,
    TAG_S_MISSING,
    compose_budget_flags,
    compute_budget_leg,
    license_budget,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/genesis_eyes_budget.py",
    "lumina_core/birth/genesis_eyes_budget_eval.py",
    "lumina_core/birth/genesis_eyes_budget_flags.py",
    "lumina_core/birth/genesis_eyes_budget_tables.py",
    "lumina_core/birth/genesis_eyes_budget_report.py",
    "lumina_core/birth/genesis_eyes_budget_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": 0.4, "n_W": 20, "bars_held_p50": 90.0}


@pytest.mark.unit
def test_floor_still_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_budget_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


@pytest.mark.unit
def test_student_sha_pins() -> None:
    assert STUDENT_BIRTH_SHA256.startswith("d313b107")
    assert STUDENT_EYES_SHA256.startswith("a9ffa852")
    proto = inspect_budget_protocol()
    assert not str(proto["student_sha_d313b107"]).endswith(":-1")
    assert not str(proto["student_sha_a9ffa852"]).endswith(":-1")


@pytest.mark.unit
def test_refuses_old_tape_hashes() -> None:
    assert FORBIDDEN_TAPE_HASH_5726.startswith("5726ae7e")
    assert FORBIDDEN_TAPE_HASH_7E86.startswith("7e86c2bb")
    with pytest.raises(BudgetProtocolError, match="5726ae7e"):
        refuse_this_tape_hash("5726ae7e83ff3d48")
    with pytest.raises(BudgetProtocolError, match="7e86c2bb"):
        refuse_this_tape_hash("7e86c2bb1c71d514")
    assert refuse_this_tape_hash("abc123def4567890") == "abc123def4567890"
    proto = inspect_budget_protocol()
    assert not str(proto["forbidden_hash_5726ae7e"]).endswith(":-1")
    assert not str(proto["forbidden_hash_7e86c2bb"]).endswith(":-1")


@pytest.mark.unit
def test_refuses_path_early_baseline() -> None:
    with pytest.raises(BudgetProtocolError, match="path_early"):
        refuse_path_early_baseline("path_early_A_close_ledger.jsonl")
    with pytest.raises(BudgetProtocolError, match="G5 halves"):
        refuse_path_early_baseline("genesis_mark_eyes_A_close_ledger.jsonl")
    with pytest.raises(BudgetProtocolError, match="n_H pin"):
        refuse_path_early_baseline(n_h_pin=78)
    refuse_path_early_baseline("budget_birth_A_close_ledger.jsonl")


@pytest.mark.unit
def test_budget_ok_requires_both_thick_and_both_moved() -> None:
    birth = _thick(n_h=80, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=50, mean_r=-0.10, n_policy=160)
    a = compute_budget_leg(birth, child)
    b = compute_budget_leg(birth, child)
    assert a["HOLE_MOVED"] is True
    licensed = license_budget(a, b)
    assert licensed["tag"] == TAG_BUDGET_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_budget(a, compute_budget_leg(birth, _thick(n_h=79, mean_r=-0.20, n_policy=160)))
    assert only_a["tag"] == TAG_BUDGET_FAIL
    assert only_a["HOLE_MOVED_A"] is True
    assert only_a["HOLE_MOVED_B"] is False


@pytest.mark.unit
def test_thin_cannot_be_budget_ok() -> None:
    birth = _thick(n_policy=160, n_h=80, mean_r=-0.20)
    child = _thick(n_policy=113, n_h=31, mean_r=-0.06)
    thin = compute_budget_leg(birth, child)
    assert thin["S_THIN"] is True
    assert thin["HOLE_MOVED"] is False
    licensed = license_budget(thin, thin)
    assert licensed["tag"] == TAG_BUDGET_THIN
    assert licensed["tag"] != TAG_BUDGET_OK
    proto = inspect_budget_protocol()
    assert not str(proto["thin_refuses_budget_ok"]).endswith(":-1")


@pytest.mark.unit
def test_genesis_eyes_ok_forced_false() -> None:
    flags = compose_budget_flags({"GENESIS_EYES_OK": True, "tag": TAG_BUDGET_OK, "HOLE_MOVED_A": True, "HOLE_MOVED_B": True})
    assert flags["GENESIS_EYES_OK"] is False
    proto = inspect_budget_protocol()
    assert not str(proto["genesis_eyes_ok_forced_false"]).endswith(":-1")


@pytest.mark.unit
def test_learn_absent() -> None:
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        assert "model.learn" not in text
        assert ".learn(" not in text
    proto = inspect_budget_protocol()
    assert not str(proto["learn_absent"]).endswith(":-1")


@pytest.mark.unit
def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    assert real_data_percentage([{"source": "real_historical"}]) == 0.0
    proto = inspect_budget_protocol()
    assert not str(proto["synthetic_pct_zero"]).endswith(":-1")


@pytest.mark.unit
def test_new_modules_under_400_loc() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


@pytest.mark.unit
def test_protocol_pins_and_hooks() -> None:
    assert BUDGET_FIXTURE_SEED == 20260905
    assert BUDGET_HOLDOUT_PCT == 0.40
    assert MIN_TICKS_PER_LEG == 40_000
    assert BUDGET_START_ET_ISO.startswith("2026-07-06")
    assert OBSERVATION_DIM == 43
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    proto = inspect_budget_protocol()
    assert proto["gate0_complete"] is True
    harm = compute_budget_leg(
        _thick(n_h=40, mean_r=0.10, n_policy=160),
        _thick(n_h=39, mean_r=0.04, n_policy=160),
    )
    assert harm["S_HARM"] is True
    assert license_budget(harm, harm)["tag"] == TAG_S_HARM
    miss = compute_budget_leg({}, {}, missing=True)
    assert license_budget(miss, miss, missing=True)["tag"] == TAG_S_MISSING
