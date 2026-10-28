"""AWAKENING_OBJECTIVE_TRADE: FORCE_OPEN train-only, floor 150, both legs."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lumina_core.birth.awakening_conv_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS, stamp_two_ticks
from lumina_core.birth.awakening_mark_eyes import MarkEyesProtocolError
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_eval_env, make_mark_eyes_train_env
from lumina_core.birth.awakening_obj_flags import (
    TAG_OBJ_BODY,
    TAG_OBJ_HARM,
    TAG_OBJ_OK,
    TAG_OBJ_THIN,
    compose_obj_flags,
    compute_obj_leg,
    empty_obj_flags,
    license_obj,
)
from lumina_core.birth.awakening_obj_tape import OBJ_SEED, inspect_obj_protocol
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.observation_builder import OBSERVATION_DIM
from lumina_core.rl.trend_features import regime_from_strength

MODULES = (
    "lumina_core/birth/awakening_obj_tape.py",
    "lumina_core/birth/awakening_obj_flags.py",
    "lumina_core/birth/awakening_obj_eval.py",
    "lumina_core/birth/awakening_obj_train.py",
    "lumina_core/birth/awakening_obj_tables.py",
    "lumina_core/birth/awakening_obj_report.py",
    "lumina_core/birth/awakening_obj_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_eval_rejects_force_open() -> None:
    with pytest.raises(MarkEyesProtocolError, match="FORCE_OPEN must stay False at eval"):
        make_mark_eyes_eval_env([], workspace_root=".", reports_dir=".", max_steps=1, force_open=True)
    proto = inspect_obj_protocol()
    assert not str(proto["eval_refuses_true"]).endswith(":-1")
    assert not str(proto["force_open_train_only"]).endswith(":-1")


def test_train_flag_defaults_false() -> None:
    sig = inspect.signature(make_mark_eyes_train_env)
    assert sig.parameters["force_open"].default is False
    eval_sig = inspect.signature(make_mark_eyes_eval_env)
    assert eval_sig.parameters["force_open"].default is False
    flags = empty_obj_flags()
    assert flags["train_force_open"] is False
    assert flags["eval_force_open"] is False
    proto = inspect_obj_protocol()
    assert not str(proto["force_open_train_only"]).endswith(":-1")


def test_prod_slope_still_015() -> None:
    ticks = stamp_two_ticks(
        [{"trend_regime_strength": 0.13}, {"trend_regime_strength": -0.13}],
        slope_abs=None,
    )
    assert ticks[0]["regime"] == "NEUTRAL"
    assert ticks[1]["regime"] == "NEUTRAL"
    assert regime_from_strength(0.13) == "NEUTRAL"
    assert PROD_SLOPE_ABS == 0.15
    assert PHYSICS_SLOPE_ABS == 0.12
    src = Path("lumina_core/rl/trend_features_batch.py").read_text(encoding="utf-8")
    assert "threshold: float = 0.15" in src
    sig = inspect.signature(enrich_ticks_for_sim)
    assert sig.parameters["slope_abs"].default is None
    proto = inspect_obj_protocol()
    assert not str(proto["prod_default_015"]).endswith(":-1")
    assert not str(proto["slope_012_isolated"]).endswith(":-1")


def test_exam_seed_20260913() -> None:
    assert OBJ_SEED == 20260913
    proto = inspect_obj_protocol()
    assert not str(proto["exam_seed_20260913"]).endswith(":-1")


def test_floor_not_waived() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    flags = compose_obj_flags({"floor_waived": True, "tag": TAG_OBJ_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["floor_waived"] is False
    thin_base = compute_obj_leg(_thick(n_policy=40, mean_r=-0.20), _thick(n_policy=160, mean_r=-0.10))
    thick_child = compute_obj_leg(_thick(n_policy=40, mean_r=-0.20), _thick(n_policy=160, mean_r=-0.10))
    licensed = license_obj(thin_base, thick_child)
    assert licensed["tag"] != TAG_OBJ_OK
    assert licensed["floor_waived"] is False
    proto = inspect_obj_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both_thick_and_both_moved() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_obj_leg(base, child)
    b = compute_obj_leg(base, child)
    licensed = license_obj(a, b)
    assert licensed["tag"] == TAG_OBJ_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_obj(a, compute_obj_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)))
    assert only_a["tag"] == TAG_OBJ_BODY
    assert only_a["tag"] != TAG_OBJ_OK
    proto = inspect_obj_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_obj_flags(
        {"GENESIS_EYES_OK": True, "tag": TAG_OBJ_OK, "MOVED_A": True, "MOVED_B": True}
    )
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_obj_flags({"tag": TAG_OBJ_OK, "MOVED_A": True, "MOVED_B": False})
    assert flags_a_only["tag"] == TAG_OBJ_BODY


def test_harm_beats_thin_in_tag_order() -> None:
    base = _thick(n_h=40, mean_r=0.10, n_policy=160)
    child = _thick(n_h=40, mean_r=0.00, n_policy=40)
    a = compute_obj_leg(base, child)
    b = compute_obj_leg(base, child)
    assert a["S_HARM"] is True
    assert a["S_THIN"] is True
    licensed = license_obj(a, b)
    assert licensed["tag"] == TAG_OBJ_HARM
    assert licensed["tag"] != TAG_OBJ_THIN
    thin_only = compute_obj_leg(_thick(n_policy=160, mean_r=-0.10), _thick(n_policy=40, mean_r=-0.08))
    thin_lic = license_obj(thin_only, thin_only)
    assert thin_lic["tag"] == TAG_OBJ_THIN


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    proto = inspect_obj_protocol()
    assert not str(proto["no_oracle"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_obj_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    env = Path("lumina_core/birth/awakening_mark_eyes_env.py")
    assert sum(1 for _ in env.open(encoding="utf-8")) <= 400
    banned = ("stamp_oracle_regime", "inject_oracle_regime", "write_regime_after_enrich")
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        for name in banned:
            assert f"def {name}" not in text
        assert 'tick["regime"] = gen' not in text
        assert "tick['regime'] = phase" not in text
    assert not str(proto["genesis_eyes_ok_false"]).endswith(":-1")
