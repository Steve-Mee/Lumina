"""AWAKENING_SLOPE_SCALE: isolated |0.004|, 8e-6, last world knob, floor 150, both legs."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lumina_core.birth.awakening_band_tape import decide_world_ok, tape_in_band
from lumina_core.birth.awakening_drift_tape import DRIFT_RTH as DRIFT_MODULE_RTH
from lumina_core.birth.awakening_drift_tape import DriftProtocolError, assert_physical_drift
from lumina_core.birth.awakening_mark_eyes import MarkEyesProtocolError
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_eval_env, make_mark_eyes_train_env
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.awakening_scale_enrich import (
    PHYSICS_SLOPE_ABS,
    PROD_SLOPE_ABS,
    ScaleProtocolError,
    classify_prod_regime,
    classify_scale_regime,
    stamp_two_ticks,
)
from lumina_core.birth.awakening_scale_flags import (
    TAG_SCALE_BODY,
    TAG_SCALE_ENRICH_FAIL,
    TAG_SCALE_HARM,
    TAG_SCALE_OK,
    TAG_SCALE_THIN,
    TAG_SCALE_WORLD_FAIL,
    TAG_S_MISSING,
    TERMINAL_TAGS,
    compose_scale_flags,
    compute_scale_leg,
    empty_scale_flags,
    license_scale,
)
from lumina_core.birth.awakening_scale_tape import (
    DRIFT_RTH,
    FORBIDDEN_TAPE_PREFIXES,
    NQ_MAX,
    NQ_MIN,
    PHASE_BLOCKS,
    SCALE_SEEDS,
    assert_forbidden_init,
    inspect_scale_protocol,
    next_scale_seed,
    refuse_this_tape_hash,
)
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.observation_builder import OBSERVATION_DIM
from lumina_core.rl.trend_features import regime_from_strength

MODULES = (
    "lumina_core/birth/awakening_scale_enrich.py",
    "lumina_core/birth/awakening_scale_tape.py",
    "lumina_core/birth/awakening_scale_flags.py",
    "lumina_core/birth/awakening_scale_eval.py",
    "lumina_core/birth/awakening_scale_train.py",
    "lumina_core/birth/awakening_scale_tables.py",
    "lumina_core/birth/awakening_scale_report.py",
    "lumina_core/birth/awakening_scale_run.py",
)
GUARD = "lumina_core/birth/birth_constitution_guard.py"


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_slope_literal_0004() -> None:
    src = Path("lumina_core/birth/awakening_scale_enrich.py").read_text(encoding="utf-8")
    assert src.count("PHYSICS_SLOPE_ABS = 0.004") == 1
    assert PHYSICS_SLOPE_ABS == 0.004
    ticks = stamp_two_ticks(
        [{"trend_regime_strength": 0.005}, {"trend_regime_strength": -0.005}],
        slope_abs=PHYSICS_SLOPE_ABS,
    )
    assert ticks[0]["regime"] == "TREND_UP"
    assert ticks[1]["regime"] == "TREND_DOWN"
    assert classify_scale_regime(0.005) == "TREND_UP"
    proto = inspect_scale_protocol()
    assert not str(proto["physics_slope_abs_0004"]).endswith(":-1")


def test_prod_still_015() -> None:
    ticks = stamp_two_ticks(
        [{"trend_regime_strength": 0.13}, {"trend_regime_strength": -0.13}],
        slope_abs=None,
    )
    assert ticks[0]["regime"] == "NEUTRAL"
    assert ticks[1]["regime"] == "NEUTRAL"
    assert classify_prod_regime(0.13) == "NEUTRAL"
    assert classify_prod_regime(-0.13) == "NEUTRAL"
    assert regime_from_strength(0.13) == "NEUTRAL"
    assert PROD_SLOPE_ABS == 0.15
    src = Path("lumina_core/rl/trend_features_batch.py").read_text(encoding="utf-8")
    assert "threshold: float = 0.15" in src
    sig = inspect.signature(enrich_ticks_for_sim)
    assert sig.parameters["slope_abs"].default is None
    proto = inspect_scale_protocol()
    assert not str(proto["prod_default_015"]).endswith(":-1")


def test_identity_not_hunt() -> None:
    src = Path("lumina_core/birth/awakening_scale_enrich.py").read_text(encoding="utf-8")
    assert "0.12*(8e-6/2.4e-4)" in src
    assert abs(PHYSICS_SLOPE_ABS - 0.12 * (8.0e-6 / 2.4e-4)) < 1e-15
    assert PHYSICS_SLOPE_ABS == 0.004
    assert "PHYSICS_SLOPE_ABS = 0.003" not in src
    assert "PHYSICS_SLOPE_ABS = 0.005" not in src
    assert "PHYSICS_SLOPE_ABS = 0.12" not in src
    proto = inspect_scale_protocol()
    assert not str(proto["identity_comment"]).endswith(":-1")


def test_drift_still_8e_6() -> None:
    src = Path("lumina_core/birth/awakening_scale_tape.py").read_text(encoding="utf-8")
    assert src.count("DRIFT_RTH = 8.0e-6") == 1
    assert DRIFT_RTH == 8.0e-6
    assert DRIFT_MODULE_RTH == 8.0e-6
    assert PHASE_BLOCKS == 6
    assert abs(assert_physical_drift(DRIFT_RTH) - 8.0e-6) < 1e-15
    with pytest.raises(DriftProtocolError, match="used_old_drift_00024"):
        assert_physical_drift(2.4e-4)
    proto = inspect_scale_protocol()
    assert not str(proto["drift_rth_8e_6"]).endswith(":-1")


def test_band_no_clip() -> None:
    raw = [{"last": 1.46e7}, {"last": 21150.0}]
    clipped = [{"last": min(max(float(t["last"]), NQ_MIN), NQ_MAX)} for t in raw]
    raw_ok, _, _ = tape_in_band(raw)
    clip_ok, _, _ = tape_in_band(clipped)
    assert raw_ok is False
    assert clip_ok is True
    assert decide_world_ok(in_band=clip_ok, fracs_ok=True, clipped=True) is False
    assert decide_world_ok(in_band=raw_ok, fracs_ok=True, clipped=False) is False
    ok, _, _ = tape_in_band([{"last": 21150.0}, {"last": 18000.0}])
    assert ok is True
    proto = inspect_scale_protocol()
    assert not str(proto["band_gate_no_clip"]).endswith(":-1")
    assert SCALE_SEEDS == (20260920, 20260921, 20260922)
    assert next_scale_seed([]) == 20260920
    assert next_scale_seed([{}]) == 20260921
    assert next_scale_seed([{}, {}]) == 20260922
    assert next_scale_seed([{}, {}, {}]) is None
    assert not str(proto["max_three_seeds_20260920_22"]).endswith(":-1")


def test_eval_rejects_force_open() -> None:
    with pytest.raises(MarkEyesProtocolError, match="FORCE_OPEN must stay False at eval"):
        make_mark_eyes_eval_env([], workspace_root=".", reports_dir=".", max_steps=1, force_open=True)
    proto = inspect_scale_protocol()
    assert not str(proto["eval_refuses_true"]).endswith(":-1")
    assert not str(proto["force_open_train_only"]).endswith(":-1")
    sig = inspect.signature(make_mark_eyes_train_env)
    assert sig.parameters["force_open"].default is False


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    flags = compose_scale_flags({"floor_waived": True, "tag": TAG_SCALE_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["floor_waived"] is False
    thin_child = compute_scale_leg(_thick(n_policy=40, mean_r=-0.20), _thick(n_policy=40, mean_r=-0.10))
    licensed = license_scale(thin_child, thin_child)
    assert licensed["tag"] == TAG_SCALE_THIN
    assert licensed["tag"] != TAG_SCALE_OK
    assert licensed["floor_waived"] is False
    proto = inspect_scale_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_scale_leg(base, child)
    b = compute_scale_leg(base, child)
    licensed = license_scale(a, b)
    assert licensed["tag"] == TAG_SCALE_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_scale(a, compute_scale_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)))
    assert only_a["tag"] == TAG_SCALE_BODY
    assert only_a["tag"] != TAG_SCALE_OK
    flags = compose_scale_flags({"GENESIS_EYES_OK": True, "tag": TAG_SCALE_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_scale_flags({"tag": TAG_SCALE_OK, "MOVED_A": True, "MOVED_B": False})
    assert flags_a_only["tag"] == TAG_SCALE_BODY
    harm = compute_scale_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=40))
    assert license_scale(harm, harm)["tag"] == TAG_SCALE_HARM
    world = license_scale(compute_scale_leg({}, {}), compute_scale_leg({}, {}), world_fail=True)
    assert world["tag"] == TAG_SCALE_WORLD_FAIL
    enrich = license_scale(compute_scale_leg({}, {}), compute_scale_leg({}, {}), enrich_fail=True)
    assert enrich["tag"] == TAG_SCALE_ENRICH_FAIL


def test_world_engineering_closed_on_every_terminal_tag() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    moved = compute_scale_leg(base, child)
    cases = [
        license_scale(moved, moved),
        license_scale(moved, compute_scale_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160))),
        license_scale(compute_scale_leg(_thick(n_policy=40), _thick(n_policy=40)), compute_scale_leg(_thick(n_policy=40), _thick(n_policy=40))),
        license_scale(
            compute_scale_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=160)),
            compute_scale_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=160)),
        ),
        license_scale({}, {}, enrich_fail=True),
        license_scale({}, {}, world_fail=True),
        license_scale({}, {}, missing=True),
    ]
    seen = {str(c["tag"]) for c in cases}
    assert TAG_SCALE_OK in seen
    assert TAG_SCALE_BODY in seen
    assert TAG_SCALE_THIN in seen
    assert TAG_SCALE_HARM in seen
    assert TAG_SCALE_ENRICH_FAIL in seen
    assert TAG_SCALE_WORLD_FAIL in seen
    assert TAG_S_MISSING in seen
    for case in cases:
        assert case["world_engineering_closed"] is True
        composed = compose_scale_flags({"tag": case["tag"], "MOVED_A": case.get("MOVED_A"), "MOVED_B": case.get("MOVED_B")})
        assert composed["world_engineering_closed"] is True
    assert set(TERMINAL_TAGS) == {
        TAG_SCALE_OK,
        TAG_SCALE_BODY,
        TAG_SCALE_THIN,
        TAG_SCALE_HARM,
        TAG_SCALE_ENRICH_FAIL,
        TAG_SCALE_WORLD_FAIL,
        TAG_S_MISSING,
    }
    proto = inspect_scale_protocol()
    assert not str(proto["world_engineering_stops"]).endswith(":-1")
    empty = empty_scale_flags()
    assert empty["world_engineering_closed"] is False
    closed = compose_scale_flags(empty)
    assert closed["world_engineering_closed"] is True


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_scale_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    env = Path("lumina_core/birth/awakening_mark_eyes_env.py")
    assert sum(1 for _ in env.open(encoding="utf-8")) <= 400
    banned = ("stamp_oracle_regime", "inject_oracle_regime", "write_regime_after_enrich")
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        for name in banned:
            assert f"def {name}" not in text
        assert 'tick["regime"] = gen' not in text
        assert "tick['regime'] = phase" not in text
        assert "def risk_exceeds_1pct" not in text
        assert "guard_bypassed = True" not in text
    assert not str(proto["genesis_eyes_ok_false"]).endswith(":-1")
    assert not str(proto["guard_1pct_unedited"]).endswith(":-1")
    guard_src = Path(GUARD).read_text(encoding="utf-8")
    assert "risk_exceeds_1pct" in guard_src
    for prefix in FORBIDDEN_TAPE_PREFIXES:
        with pytest.raises(ScaleProtocolError, match="refused old tape hash"):
            refuse_this_tape_hash(prefix + "deadbeef")
    with pytest.raises(ScaleProtocolError, match="refused old tape hash"):
        refuse_this_tape_hash("79397a6fdeadbeef")
    with pytest.raises(ScaleProtocolError, match="refused forbidden init"):
        assert_forbidden_init("x.zip", "a9ffa852" + ("0" * 56))
    with pytest.raises(ScaleProtocolError, match="refused forbidden init"):
        assert_forbidden_init("awakening_drift_v1_pi_star.zip")
