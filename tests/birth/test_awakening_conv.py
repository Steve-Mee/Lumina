"""AWAKENING_ENRICHER_CONVERSION: isolated |0.12|, 25/25 both, floor 150, both legs."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from lumina_core.birth.awakening_conv_enrich import (
    PHYSICS_SLOPE_ABS,
    PROD_SLOPE_ABS,
    classify_conv_regime,
    classify_prod_regime,
    enrich_ticks_for_conv,
    stamp_two_ticks,
)
from lumina_core.birth.awakening_conv_flags import (
    TAG_CONV_BODY,
    TAG_CONV_OK,
    TAG_CONV_WORLD_FAIL,
    compose_conv_flags,
    compute_conv_leg,
    license_conv,
)
from lumina_core.birth.awakening_conv_run import body_exam_enabled
from lumina_core.birth.awakening_conv_tape import (
    CONV_SEED,
    MIN_TREND_DOWN_FRAC,
    MIN_TREND_UP_FRAC,
    inspect_conv_protocol,
)
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.observation_builder import OBSERVATION_DIM
from lumina_core.rl.trend_features import MIN_TREND_LOOKBACK, regime_from_strength

MODULES = (
    "lumina_core/birth/awakening_conv_enrich.py",
    "lumina_core/birth/awakening_conv_tape.py",
    "lumina_core/birth/awakening_conv_flags.py",
    "lumina_core/birth/awakening_conv_eval.py",
    "lumina_core/birth/awakening_conv_train.py",
    "lumina_core/birth/awakening_conv_tables.py",
    "lumina_core/birth/awakening_conv_report.py",
    "lumina_core/birth/awakening_conv_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_prod_slope_still_015() -> None:
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
    proto = inspect_conv_protocol()
    assert not str(proto["prod_default_015"]).endswith(":-1")


def test_wrapper_uses_012() -> None:
    ticks = stamp_two_ticks(
        [{"trend_regime_strength": 0.13}, {"trend_regime_strength": -0.13}],
        slope_abs=PHYSICS_SLOPE_ABS,
    )
    assert ticks[0]["regime"] == "TREND_UP"
    assert ticks[1]["regime"] == "TREND_DOWN"
    assert classify_conv_regime(0.13) == "TREND_UP"
    assert classify_conv_regime(-0.13) == "TREND_DOWN"
    assert PHYSICS_SLOPE_ABS == 0.12
    sig = inspect.signature(enrich_ticks_for_conv)
    assert "slope_abs" not in sig.parameters
    proto = inspect_conv_protocol()
    assert not str(proto["physics_slope_abs_012"]).endswith(":-1")


def test_no_second_knob() -> None:
    src = Path("lumina_core/birth/awakening_conv_enrich.py").read_text(encoding="utf-8")
    assert "PHYSICS_SLOPE_ABS = 0.12" in src
    assert "no second knob" in src
    assert "LOOKBACK" not in src
    sig = inspect.signature(enrich_ticks_for_conv)
    assert "lookback" not in sig.parameters
    assert MIN_TREND_LOOKBACK == 60
    prod = Path("lumina_core/rl/trend_features_core.py").read_text(encoding="utf-8")
    assert "MIN_TREND_LOOKBACK = 60" in prod


def test_exam_seed_20260912() -> None:
    assert CONV_SEED == 20260912
    proto = inspect_conv_protocol()
    assert not str(proto["exam_seed_20260912"]).endswith(":-1")
    assert not str(proto["per_phase_60_40_import"]).endswith(":-1")


def test_body_not_called_without_world_ok() -> None:
    assert body_exam_enabled(False) is False
    assert body_exam_enabled(True) is True
    licensed = license_conv({}, {}, world_ok=False)
    assert licensed["tag"] == TAG_CONV_WORLD_FAIL
    flags = compose_conv_flags(
        {
            "tag": TAG_CONV_OK,
            "world_ok": False,
            "MOVED_A": True,
            "MOVED_B": True,
            "learn_called": True,
            "child_sha256": "deadbeef",
            "actual_timesteps": 10_000,
        }
    )
    assert flags["tag"] == TAG_CONV_WORLD_FAIL
    assert flags["learn_called"] is False
    assert flags["child_sha256"] == ""
    proto = inspect_conv_protocol()
    assert not str(proto["body_skipped"]).endswith(":-1")


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_conv_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both_legs() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_conv_leg(base, child)
    b = compute_conv_leg(base, child)
    licensed = license_conv(a, b, world_ok=True)
    assert licensed["tag"] == TAG_CONV_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_conv(a, compute_conv_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)), world_ok=True)
    assert only_a["tag"] == TAG_CONV_BODY
    assert only_a["tag"] != TAG_CONV_OK
    proto = inspect_conv_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_conv_flags(
        {"GENESIS_EYES_OK": True, "tag": TAG_CONV_OK, "MOVED_A": True, "MOVED_B": True, "world_ok": True}
    )
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_conv_flags({"tag": TAG_CONV_OK, "MOVED_A": True, "MOVED_B": False, "world_ok": True})
    assert flags_a_only["tag"] == TAG_CONV_BODY


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0


def test_no_oracle_regime() -> None:
    banned = ("stamp_oracle_regime", "inject_oracle_regime", "write_regime_after_enrich")
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        for name in banned:
            assert f"def {name}" not in text, f"{rel} defines {name}"
        assert 'tick["regime"] = gen' not in text
        assert "tick['regime'] = phase" not in text
        assert 'tick["regime"] = intended' not in text
        assert 'tick["regime"] = labels' not in text
    proto = inspect_conv_protocol()
    assert not str(proto["no_oracle_regime"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_conv_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    assert MIN_TREND_UP_FRAC == 0.25
    assert MIN_TREND_DOWN_FRAC == 0.25
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    assert not str(proto["fracs_25_25"]).endswith(":-1")
    assert not str(proto["genesis_eyes_ok_false"]).endswith(":-1")
    prod = Path("lumina_core/birth/tick_enricher.py").read_text(encoding="utf-8")
    assert prod.count("slope_abs: float | None = None") == 1
    net = sum(1 for line in prod.splitlines() if "slope_abs" in line)
    assert net <= 20


def test_wrapper_enrich_calls_prod_with_012() -> None:
    ticks = [{"last": 5000.0 + i * 2.0, "volume": 100, "source": "synthetic_cloud_fixture"} for i in range(80)]
    prod = enrich_ticks_for_sim([dict(t) for t in ticks])
    conv = enrich_ticks_for_conv([dict(t) for t in ticks])
    via_kw = enrich_ticks_for_sim([dict(t) for t in ticks], slope_abs=PHYSICS_SLOPE_ABS)
    assert prod[70]["regime"] == "TREND_UP"
    assert conv[70]["regime"] == "TREND_UP"
    assert via_kw[70]["regime"] == "TREND_UP"
    assert enrich_ticks_for_sim([]) == []


def test_tables_report_and_tape_guards() -> None:
    from lumina_core.birth.awakening_conv_enrich import ConvProtocolError
    from lumina_core.birth.awakening_conv_report import render_audit, render_verdict
    from lumina_core.birth.awakening_conv_run import origin_guard_paths, snapshot_origin_artifacts
    from lumina_core.birth.awakening_conv_tables import table_t0_identity, table_t1_honesty, table_t2_leg, table_t3_license
    from lumina_core.birth.awakening_conv_tape import assert_forbidden_init, refuse_this_tape_hash

    t0 = table_t0_identity(origin_main="abc", train_hash="b1f16c99", baseline_sha="a9ffa852", child_sha="")
    t1 = table_t1_honesty()
    t2 = table_t2_leg("A", {"n_policy_base": 160, "MOVED": False})
    t3 = table_t3_license({"tag": "S_HARM", "law": "NONE"})
    assert t0["prod_enricher_default_changed"] is False
    assert t1["G6_tag"] == "REAL_DOOR_LOCKED"
    assert t2["leg"] == "A"
    assert t3["GENESIS_EYES_OK"] is False
    flags = compose_conv_flags({"tag": "S_HARM", "world_ok": True, "A": {}, "B": {}})
    audit = render_audit(gate0={}, proto={}, t0=t0, t1=t1, t2_a=t2, t2_b=t2, t3=t3, flags=flags, g6={})
    verdict = render_verdict(flags=flags, t2_a=t2, t2_b=t2)
    assert "AWAKENING_ENRICHER_CONVERSION_AUDIT" in audit
    assert "S_HARM" in verdict
    assert refuse_this_tape_hash("b1f16c99deadbeef") == "b1f16c99deadbeef"
    with pytest.raises(ConvProtocolError, match="refused old tape hash"):
        refuse_this_tape_hash("7923fa61deadbeef")
    with pytest.raises(ConvProtocolError, match="forbidden init"):
        assert_forbidden_init("baseline_a9ffa852_pi_star.zip", sha="a9ffa852dead")
    assert "awakening_strat_flags.json" in origin_guard_paths()
    assert isinstance(snapshot_origin_artifacts(), dict)
