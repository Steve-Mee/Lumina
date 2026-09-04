"""AWAKENING_ENRICHER_COUPLING: one cause, one fix, 25/25, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_coupling_diagnose import (
    CAUSE_RULES_ORDER,
    DIAGNOSE_SEED,
    EXAM_SEED,
    MIN_TREND_DOWN_FRAC,
    MIN_TREND_UP_FRAC,
    inspect_coupling_protocol,
    pin_cause,
)
from lumina_core.birth.awakening_coupling_flags import (
    TAG_COUPLING_FAIL,
    TAG_COUPLING_OK,
    TAG_COUPLING_UNKNOWN,
    TAG_COUPLING_WORLD,
    compose_coupling_flags,
    compute_coupling_leg,
    license_coupling,
)
from lumina_core.birth import awakening_coupling_fix as coupling_fix
from lumina_core.birth.awakening_coupling_fix import (
    NotUsed,
    apply_floor_clip_kwargs,
    apply_gen_asym_kwargs,
    bind_fix_kind,
    refuse_oracle_regime,
)
from lumina_core.birth.awakening_coupling_run import body_exam_enabled
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM
from lumina_core.rl.trend_features import regime_from_strength

MODULES = (
    "lumina_core/birth/awakening_coupling_diagnose.py",
    "lumina_core/birth/awakening_coupling_fix.py",
    "lumina_core/birth/awakening_coupling_flags.py",
    "lumina_core/birth/awakening_coupling_eval.py",
    "lumina_core/birth/awakening_coupling_train.py",
    "lumina_core/birth/awakening_coupling_tables.py",
    "lumina_core/birth/awakening_coupling_report.py",
    "lumina_core/birth/awakening_coupling_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def _base_meas(**over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "drift_up_used": 0.00024,
        "drift_down_used": 0.00024,
        "enr_threshold_pos": 0.15,
        "enr_threshold_neg": -0.15,
        "mean_slope_emitted_up": 0.2,
        "mean_slope_emitted_down": -0.2,
        "down_near_floor_n": 0,
        "up_near_cap_n": 0,
    }
    row.update(over)
    return row


def test_cause_rule_order() -> None:
    assert CAUSE_RULES_ORDER == ("GEN_ASYM", "ENR_ASYM", "FLOOR_CLIP", "OTHER")
    assert pin_cause(_base_meas(drift_down_used=0.0001)) == "GEN_ASYM"
    assert pin_cause(_base_meas(enr_threshold_neg=-0.22)) == "ENR_ASYM"
    assert pin_cause(_base_meas(mean_slope_emitted_down=-0.55)) == "ENR_ASYM"
    assert pin_cause(_base_meas(down_near_floor_n=12, up_near_cap_n=3)) == "FLOOR_CLIP"
    assert pin_cause(_base_meas()) == "OTHER"
    assert (
        pin_cause(_base_meas(drift_down_used=0.00005, enr_threshold_neg=-0.4, down_near_floor_n=99)) == "GEN_ASYM"
    )
    proto = inspect_coupling_protocol()
    assert not str(proto["cause_rules_order"]).endswith(":-1")


def test_no_oracle_regime_assign() -> None:
    banned = ("stamp_oracle_regime", "inject_oracle_regime", "write_regime_after_enrich")
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        for name in banned:
            assert f"def {name}" not in text, f"{rel} defines {name}"
        assert 'tick["regime"] = gen' not in text
        assert "tick['regime'] = phase" not in text
        assert 'tick["regime"] = intended' not in text
    with pytest.raises(Exception, match="forbidden"):
        refuse_oracle_regime({}, "down")
    proto = inspect_coupling_protocol()
    assert not str(proto["no_oracle_regime"]).endswith(":-1")
    bind_fix_kind("FLOOR_CLIP")
    with pytest.raises(NotUsed):
        apply_gen_asym_kwargs({"drift_rth": 0.00024, "drift_down_rth": 0.0001})
    bind_fix_kind("GEN_ASYM")
    with pytest.raises(NotUsed):
        apply_floor_clip_kwargs({"start_price": 1.0})


def test_diagnose_seed_20260908() -> None:
    assert DIAGNOSE_SEED == 20260908
    proto = inspect_coupling_protocol()
    assert not str(proto["diagnose_seed"]).endswith(":-1")


def test_exam_seed_20260909() -> None:
    assert EXAM_SEED == 20260909
    proto = inspect_coupling_protocol()
    assert not str(proto["exam_seed"]).endswith(":-1")
    bind_fix_kind("ENR_ASYM")
    assert coupling_fix.FIX_KIND == "ENR_ASYM"


def test_body_not_called_without_world_ok() -> None:
    assert body_exam_enabled(False, "FLOOR_CLIP") is False
    assert body_exam_enabled(True, "OTHER") is False
    assert body_exam_enabled(True, "FLOOR_CLIP") is True
    licensed = license_coupling({}, {}, world_ok=False, cause="FLOOR_CLIP")
    assert licensed["tag"] == TAG_COUPLING_FAIL
    flags = compose_coupling_flags(
        {"tag": TAG_COUPLING_OK, "world_ok": False, "MOVED_A": True, "MOVED_B": True, "learn_called": True, "cause": "FLOOR_CLIP"}
    )
    assert flags["tag"] == TAG_COUPLING_FAIL
    assert flags["learn_called"] is True
    proto = inspect_coupling_protocol()
    assert not str(proto["body_skipped"]).endswith(":-1")


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_coupling_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both_legs() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_coupling_leg(base, child)
    b = compute_coupling_leg(base, child)
    licensed = license_coupling(a, b, world_ok=True, cause="FLOOR_CLIP")
    assert licensed["tag"] == TAG_COUPLING_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_coupling(
        a, compute_coupling_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)), world_ok=True, cause="FLOOR_CLIP"
    )
    assert only_a["tag"] == TAG_COUPLING_WORLD
    assert only_a["tag"] != TAG_COUPLING_OK
    unknown = license_coupling(a, b, world_ok=True, cause="OTHER")
    assert unknown["tag"] == TAG_COUPLING_UNKNOWN
    proto = inspect_coupling_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_coupling_flags({"GENESIS_EYES_OK": True, "tag": TAG_COUPLING_OK, "MOVED_A": True, "MOVED_B": True, "world_ok": True, "cause": "FLOOR_CLIP"})
    assert flags["GENESIS_EYES_OK"] is False


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    assert real_data_percentage([{"source": "real_historical"}]) == 0.0
    proto = inspect_coupling_protocol()
    assert not str(proto["honesty_synthetic_0"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_coupling_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    assert MIN_TREND_UP_FRAC == 0.25
    assert MIN_TREND_DOWN_FRAC == 0.25
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    default = float(regime_from_strength.__defaults__[0]) if regime_from_strength.__defaults__ else 0.15
    assert default == 0.15
    assert abs(default - abs(-default)) < 1e-12
