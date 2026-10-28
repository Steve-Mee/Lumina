"""Gate 2 HOLD_COMPARE: measure-only. Floor 150. No GENESIS_EYES_OK. No learn."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_hold_compare import (
    G5_BIRTH_A,
    G5_BIRTH_B,
    G5_EYES_A,
    G5_EYES_B,
    GenesisHoldCompareError,
    HOLDOUT_TICKS_A,
    TAG_EVAL_BUDGET,
    TAG_HOLD_LONGER,
    TAG_MIXED,
    TAG_REFUSAL,
    TAG_S_MISSING,
    classify_cause,
    combine_leg_tags,
    compare_leg,
    g5_inputs_present,
    licensed_next_family,
    refuse_genesis_eyes_ok,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM


def _stats(*, n_policy: int, p50: float | None, present: bool = True) -> dict[str, object]:
    return {
        "n_policy": n_policy,
        "bars_held_p50": p50,
        "bars_held_present": present and p50 is not None,
    }


@pytest.mark.unit
def test_floor_stays_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src


@pytest.mark.unit
def test_observation_dim_still_43() -> None:
    assert OBSERVATION_DIM == 43


@pytest.mark.unit
def test_hooks_default_false() -> None:
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False


@pytest.mark.unit
def test_license_refuses_genesis_eyes_ok() -> None:
    with pytest.raises(GenesisHoldCompareError, match="GENESIS_EYES_OK"):
        refuse_genesis_eyes_ok({"GENESIS_EYES_OK": True})
    flags = refuse_genesis_eyes_ok({"GENESIS_EYES_OK": False, "tag": "GENESIS_FOLLOWON_OK"})
    assert flags["GENESIS_EYES_OK"] is False
    assert flags["HOLE_MOVED_A"] is False
    assert flags["HOLE_MOVED_B"] is False


@pytest.mark.unit
def test_hold_longer_rule() -> None:
    tag = classify_cause(
        birth=_stats(n_policy=150, p50=40.0),
        child=_stats(n_policy=113, p50=50.0),
        child_last_row={"close_reason": "stop"},
    )
    assert tag == TAG_HOLD_LONGER


@pytest.mark.unit
def test_refusal_rule() -> None:
    tag = classify_cause(
        birth=_stats(n_policy=150, p50=40.0),
        child=_stats(n_policy=113, p50=42.0),
        child_last_row={"close_reason": "stop"},
    )
    assert tag == TAG_REFUSAL


@pytest.mark.unit
def test_eval_budget_rule() -> None:
    tag = classify_cause(
        birth=_stats(n_policy=150, p50=40.0),
        child=_stats(n_policy=113, p50=80.0),
        child_last_row={"close_reason": "time_stop"},
    )
    assert tag == TAG_HOLD_LONGER
    tag_budget = classify_cause(
        birth=_stats(n_policy=150, p50=40.0),
        child=_stats(n_policy=113, p50=41.0),
        child_last_row={"close_reason": "truncated"},
    )
    assert tag_budget == TAG_MIXED
    tag_only = classify_cause(
        birth=_stats(n_policy=100, p50=40.0),
        child=_stats(n_policy=100, p50=40.0),
        child_last_row={"close_reason": "time_stop"},
    )
    assert tag_only == TAG_EVAL_BUDGET


@pytest.mark.unit
def test_mixed_when_not_separable() -> None:
    tag = classify_cause(
        birth=_stats(n_policy=100, p50=40.0),
        child=_stats(n_policy=120, p50=40.0),
        child_last_row={"close_reason": "stop"},
    )
    assert tag == TAG_MIXED


@pytest.mark.unit
def test_missing_bars_held_is_s_missing() -> None:
    tag = classify_cause(
        birth=_stats(n_policy=150, p50=None, present=False),
        child=_stats(n_policy=113, p50=50.0),
        child_last_row={"close_reason": "stop"},
    )
    assert tag == TAG_S_MISSING


@pytest.mark.unit
def test_licensed_next_family() -> None:
    assert licensed_next_family(TAG_HOLD_LONGER, gate1_ok=True) == "GENESIS_EYES_BUDGET"
    assert licensed_next_family(TAG_EVAL_BUDGET, gate1_ok=True) == "GENESIS_EYES_BUDGET"
    assert licensed_next_family(TAG_REFUSAL, gate1_ok=True) == "H_NONE"
    assert licensed_next_family(TAG_MIXED, gate1_ok=True) == "H_NONE"
    assert licensed_next_family(TAG_HOLD_LONGER, gate1_ok=False) == "H_NONE"


@pytest.mark.unit
def test_combine_legs() -> None:
    assert combine_leg_tags(TAG_HOLD_LONGER, TAG_HOLD_LONGER) == TAG_HOLD_LONGER
    assert combine_leg_tags(TAG_HOLD_LONGER, TAG_REFUSAL) == TAG_MIXED
    assert combine_leg_tags(TAG_S_MISSING, TAG_HOLD_LONGER) == TAG_S_MISSING


@pytest.mark.unit
def test_learn_absent_from_hold_compare_modules() -> None:
    root = Path("lumina_core/birth")
    for name in (
        "genesis_hold_compare.py",
        "genesis_hold_compare_tables.py",
        "genesis_hold_compare_report.py",
        "genesis_hold_compare_run.py",
    ):
        text = (root / name).read_text(encoding="utf-8")
        assert "model.learn" not in text
        assert ".learn(" not in text


@pytest.mark.unit
def test_g5_ledger_paths_listed_read_only() -> None:
    src = Path("lumina_core/birth/genesis_hold_compare.py").read_text(encoding="utf-8")
    assert "read-only" in src
    assert "genesis_birth_A_close_ledger.jsonl" in src
    assert "genesis_birth_B_close_ledger.jsonl" in src
    assert "genesis_mark_eyes_A_close_ledger.jsonl" in src
    assert "genesis_mark_eyes_B_close_ledger.jsonl" in src
    assert G5_BIRTH_A.name == "genesis_birth_A_close_ledger.jsonl"
    assert G5_EYES_B.name == "genesis_mark_eyes_B_close_ledger.jsonl"


@pytest.mark.unit
def test_frozen_books_restate_n_policy_113_103() -> None:
    if not g5_inputs_present():
        pytest.skip("G5 genesis ledgers missing on this SHA")
    cmp_a = compare_leg(
        birth_path=G5_BIRTH_A,
        child_path=G5_EYES_A,
        holdout_ticks=HOLDOUT_TICKS_A,
        expected_n_policy_child=113,
    )
    cmp_b = compare_leg(
        birth_path=G5_BIRTH_B,
        child_path=G5_EYES_B,
        holdout_ticks=21585,
        expected_n_policy_child=103,
    )
    assert int(cmp_a["child"]["n_policy"]) == 113
    assert int(cmp_b["child"]["n_policy"]) == 103
    assert int(cmp_a["birth"]["n_policy"]) == 150
    assert int(cmp_b["birth"]["n_policy"]) == 150
    assert cmp_a["learn_called"] is False
    assert cmp_a["g5_ledgers_read_only"] is True
    assert abs(float(cmp_a["child"]["mean_r"]) - (-0.06581195881282897)) < 1e-9
    assert abs(float(cmp_b["child"]["mean_r"]) - (-0.06422429818509125)) < 1e-9
    assert int(cmp_a["child"]["n_H"]) == 31
    assert int(cmp_b["child"]["n_H"]) == 21
    assert cmp_a["cause"] in {TAG_HOLD_LONGER, TAG_REFUSAL, TAG_EVAL_BUDGET, TAG_MIXED, TAG_S_MISSING}
    assert POLICY_EDGE_MIN_TRADES == 150
