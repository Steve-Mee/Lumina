"""AWAKENING_GEOMETRY_REWARD: first-touch 0.10, +1.21/−1.04 train-only, floor 150."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lumina_core.birth.awakening_drift_tape import DRIFT_RTH as DRIFT_MODULE_RTH
from lumina_core.birth.awakening_drift_tape import DriftProtocolError, assert_physical_drift
from lumina_core.birth.awakening_geom_flags import (
    TAG_GEOM_BODY,
    TAG_GEOM_HARM,
    TAG_GEOM_OK,
    TAG_GEOM_THIN,
    TAG_GEOM_UNHITTABLE,
    TAG_S_MISSING,
    TERMINAL_TAGS,
    compose_geom_flags,
    compute_geom_leg,
    empty_geom_flags,
    license_geom,
)
from lumina_core.birth.awakening_geom_reward import (
    GEOM_LOSS_R,
    GEOM_WIN_R,
    USE_GEOM_CLOSE_REWARD,
    GeomProtocolError,
    geom_close_reward,
)
from lumina_core.birth.awakening_geom_tape import (
    DRIFT_RTH,
    FORBIDDEN_TAPE_PREFIXES,
    GEOM_SEEDS,
    PHASE_BLOCKS,
    SCALE_TAPE_HASH,
    assert_forbidden_init,
    inspect_geom_protocol,
    next_geom_seed,
    refuse_this_tape_hash,
)
from lumina_core.birth.awakening_geom_touch import TARGET_FRAC_MIN, first_touch_books
from lumina_core.birth.awakening_geom_train import should_learn
from lumina_core.birth.awakening_mark_eyes import MarkEyesProtocolError
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_eval_env, make_mark_eyes_train_env
from lumina_core.birth.awakening_scale_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS, classify_prod_regime
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.observation_builder import OBSERVATION_DIM
from lumina_core.rl.trend_features import regime_from_strength

MODULES = (
    "lumina_core/birth/awakening_geom_reward.py",
    "lumina_core/birth/awakening_geom_touch.py",
    "lumina_core/birth/awakening_geom_flags.py",
    "lumina_core/birth/awakening_geom_tape.py",
    "lumina_core/birth/awakening_geom_eval.py",
    "lumina_core/birth/awakening_geom_train.py",
    "lumina_core/birth/awakening_geom_tables.py",
    "lumina_core/birth/awakening_geom_report.py",
    "lumina_core/birth/awakening_geom_run.py",
)
GUARD = "lumina_core/birth/birth_constitution_guard.py"


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_unhittable_skips_learn() -> None:
    assert should_learn(unhittable=True, n_policy_a=200, n_policy_b=200) is False
    assert should_learn(unhittable=False, n_policy_a=200, n_policy_b=200) is True
    assert should_learn(unhittable=False, n_policy_a=149, n_policy_b=200) is False
    assert should_learn(unhittable=False, n_policy_a=200, n_policy_b=149) is False
    books = first_touch_books(
        [{"close_reason": "stop", "plant": False, "force_open": False}] * 160,
        [{"close_reason": "time_stop", "plant": False, "force_open": False}] * 160,
    )
    assert books["unhittable"] is True
    assert books["target_frac"] < TARGET_FRAC_MIN
    assert should_learn(
        unhittable=bool(books["unhittable"]),
        n_policy_a=int(books["n_policy_A"]),
        n_policy_b=int(books["n_policy_B"]),
    ) is False
    proto = inspect_geom_protocol()
    assert not str(proto["learn_skipped_unhittable"]).endswith(":-1")


def test_reward_literals_121_104() -> None:
    assert GEOM_WIN_R == 1.21
    assert GEOM_LOSS_R == -1.04
    assert geom_close_reward(9.9, "target", "TREND_UP") == 1.21
    assert geom_close_reward(-9.9, "stop", "NEUTRAL") == -1.04
    assert geom_close_reward(1.0, "time_stop", "NEUTRAL") == 0.0
    assert geom_close_reward(1.0, "flatten", "NEUTRAL") == 0.0
    assert geom_close_reward(1.0, "force_exit", "NEUTRAL") == 0.0
    assert geom_close_reward(0.5, "geometry-win", "X") == 1.21
    assert geom_close_reward(0.5, "geometry-loss", "X") == -1.04
    proto = inspect_geom_protocol()
    assert not str(proto["geom_win_r_121"]).endswith(":-1")
    assert not str(proto["geom_loss_r_104"]).endswith(":-1")
    assert not str(proto["target_frac_min_010"]).endswith(":-1")
    assert TARGET_FRAC_MIN == 0.10


def test_eval_not_using_train_reward_flag() -> None:
    assert USE_GEOM_CLOSE_REWARD is False
    sig = inspect.signature(make_mark_eyes_train_env)
    assert sig.parameters["use_geom_close_reward"].default is False
    eval_src = Path("lumina_core/birth/awakening_geom_eval.py").read_text(encoding="utf-8")
    assert "use_geom_close_reward=True" not in eval_src
    assert "geom_close_reward(" not in eval_src
    src = inspect.getsource(make_mark_eyes_eval_env)
    assert "use_geom_close_reward=True" not in src
    with pytest.raises(MarkEyesProtocolError, match="FORCE_OPEN must stay False at eval"):
        make_mark_eyes_eval_env([], workspace_root=".", reports_dir=".", max_steps=1, force_open=True)
    proto = inspect_geom_protocol()
    assert not str(proto["force_open_train_only"]).endswith(":-1")


def test_prod_slope_015() -> None:
    assert PROD_SLOPE_ABS == 0.15
    assert PHYSICS_SLOPE_ABS == 0.004
    assert classify_prod_regime(0.13) == "NEUTRAL"
    assert regime_from_strength(0.13) == "NEUTRAL"
    sig = inspect.signature(enrich_ticks_for_sim)
    assert sig.parameters["slope_abs"].default is None
    src = Path("lumina_core/rl/trend_features_batch.py").read_text(encoding="utf-8")
    assert "threshold: float = 0.15" in src
    proto = inspect_geom_protocol()
    assert not str(proto["prod_slope_015"]).endswith(":-1")


def test_drift_8e_6() -> None:
    src = Path("lumina_core/birth/awakening_geom_tape.py").read_text(encoding="utf-8")
    assert "DRIFT_RTH==8.0e-6" in src
    assert DRIFT_RTH == 8.0e-6
    assert DRIFT_MODULE_RTH == 8.0e-6
    assert PHASE_BLOCKS == 6
    assert abs(assert_physical_drift(DRIFT_RTH) - 8.0e-6) < 1e-15
    with pytest.raises(DriftProtocolError, match="used_old_drift_00024"):
        assert_physical_drift(2.4e-4)
    assert GEOM_SEEDS == (20260923, 20260924, 20260925)
    assert next_geom_seed([]) == 20260923
    assert next_geom_seed([{}]) == 20260924
    assert next_geom_seed([{}, {}]) == 20260925
    assert next_geom_seed([{}, {}, {}]) is None
    proto = inspect_geom_protocol()
    assert not str(proto["drift_8e_6"]).endswith(":-1")


def test_world_engineering_stays_closed() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    moved = compute_geom_leg(base, child)
    cases = [
        license_geom(moved, moved),
        license_geom(moved, compute_geom_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160))),
        license_geom(compute_geom_leg(_thick(n_policy=40), _thick(n_policy=40)), compute_geom_leg(_thick(n_policy=40), _thick(n_policy=40))),
        license_geom(
            compute_geom_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=160)),
            compute_geom_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=160)),
        ),
        license_geom({}, {}, unhittable=True),
        license_geom({}, {}, missing=True),
    ]
    seen = {str(c["tag"]) for c in cases}
    assert TAG_GEOM_OK in seen
    assert TAG_GEOM_BODY in seen
    assert TAG_GEOM_THIN in seen
    assert TAG_GEOM_HARM in seen
    assert TAG_GEOM_UNHITTABLE in seen
    assert TAG_S_MISSING in seen
    for case in cases:
        assert case["world_engineering_closed"] is True
        composed = compose_geom_flags({"tag": case["tag"], "MOVED_A": case.get("MOVED_A"), "MOVED_B": case.get("MOVED_B")})
        assert composed["world_engineering_closed"] is True
    assert set(TERMINAL_TAGS) == {
        TAG_GEOM_OK,
        TAG_GEOM_BODY,
        TAG_GEOM_THIN,
        TAG_GEOM_HARM,
        TAG_GEOM_UNHITTABLE,
        TAG_S_MISSING,
    }
    proto = inspect_geom_protocol()
    assert not str(proto["world_engineering_closed_true"]).endswith(":-1")
    empty = empty_geom_flags()
    assert empty["world_engineering_closed"] is True
    closed = compose_geom_flags(empty)
    assert closed["world_engineering_closed"] is True
    assert closed["GENESIS_EYES_OK"] is False


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    flags = compose_geom_flags({"floor_waived": True, "tag": TAG_GEOM_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["floor_waived"] is False
    thin_child = compute_geom_leg(_thick(n_policy=40, mean_r=-0.20), _thick(n_policy=40, mean_r=-0.10))
    licensed = license_geom(thin_child, thin_child)
    assert licensed["tag"] == TAG_GEOM_THIN
    assert licensed["tag"] != TAG_GEOM_OK
    assert licensed["floor_waived"] is False
    proto = inspect_geom_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_geom_leg(base, child)
    b = compute_geom_leg(base, child)
    licensed = license_geom(a, b)
    assert licensed["tag"] == TAG_GEOM_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_geom(a, compute_geom_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)))
    assert only_a["tag"] == TAG_GEOM_BODY
    assert only_a["tag"] != TAG_GEOM_OK
    flags = compose_geom_flags({"GENESIS_EYES_OK": True, "tag": TAG_GEOM_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_geom_flags({"tag": TAG_GEOM_OK, "MOVED_A": True, "MOVED_B": False})
    assert flags_a_only["tag"] == TAG_GEOM_BODY
    harm = compute_geom_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=160))
    assert license_geom(harm, harm)["tag"] == TAG_GEOM_HARM
    miss = license_geom(compute_geom_leg({}, {}), compute_geom_leg({}, {}), missing=True)
    assert miss["tag"] == TAG_S_MISSING
    unhit = license_geom(a, b, unhittable=True)
    assert unhit["tag"] == TAG_GEOM_UNHITTABLE
    assert unhit["law"] == "NONE"
    assert unhit["licensed_next_family"] == "H_NONE"


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_geom_protocol()
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
    guard_src = Path(GUARD).read_text(encoding="utf-8")
    assert "risk_exceeds_1pct" in guard_src
    for prefix in FORBIDDEN_TAPE_PREFIXES:
        with pytest.raises(GeomProtocolError, match="refused old tape hash"):
            refuse_this_tape_hash(prefix + "deadbeef")
    with pytest.raises(GeomProtocolError, match="refused old tape hash"):
        refuse_this_tape_hash(SCALE_TAPE_HASH)
    with pytest.raises(GeomProtocolError, match="refused forbidden init"):
        assert_forbidden_init("x.zip", "a9ffa852" + ("0" * 56))
    with pytest.raises(GeomProtocolError, match="refused forbidden init"):
        assert_forbidden_init("awakening_scale_v1_pi_star.zip")
    with pytest.raises(GeomProtocolError, match="refused forbidden init"):
        assert_forbidden_init("x.zip", "b83d2b67" + ("0" * 56))
