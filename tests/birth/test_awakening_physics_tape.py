"""AWAKENING_PHYSICS_TAPE: payable world, scratch V1, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_physics_flags import (
    TAG_PHYSICS_FAIL,
    TAG_PHYSICS_OK,
    TAG_PHYSICS_THIN,
    TAG_PHYSICS_WORLD_FAIL,
    compose_physics_flags,
    compute_physics_leg,
    license_physics,
)
from lumina_core.birth.awakening_physics_tape import (
    BASELINE_SHA256,
    FORBIDDEN_TAPE_PREFIXES,
    MIN_TREND_DOWN_FRAC,
    MIN_TREND_UP_FRAC,
    PHYSICS_DRIFT_ETH,
    PHYSICS_DRIFT_RTH,
    PHYSICS_PHASE_BLOCKS,
    PHYSICS_RANGE_KAPPA,
    PhysicsProtocolError,
    PhysicsTapeSpec,
    assert_forbidden_init,
    generate_physics_tape_ticks,
    inspect_physics_protocol,
    refuse_this_tape_hash,
)
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_physics_tape.py",
    "lumina_core/birth/awakening_physics_flags.py",
    "lumina_core/birth/awakening_physics_eval.py",
    "lumina_core/birth/awakening_physics_train.py",
    "lumina_core/birth/awakening_physics_tables.py",
    "lumina_core/birth/awakening_physics_report.py",
    "lumina_core/birth/awakening_physics_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_drift_literals_pinned() -> None:
    src = Path("lumina_core/birth/awakening_physics_tape.py").read_text(encoding="utf-8")
    assert "PHYSICS_DRIFT_RTH = 0.00012" in src
    assert PHYSICS_DRIFT_RTH == 0.00012
    assert PHYSICS_DRIFT_ETH == 0.00003
    assert PHYSICS_RANGE_KAPPA == 0.04
    assert PHYSICS_PHASE_BLOCKS == 6
    proto = inspect_physics_protocol()
    assert not str(proto["physics_drift_rth"]).endswith(":-1")


def test_frac_floors_025() -> None:
    assert MIN_TREND_UP_FRAC == 0.25
    assert MIN_TREND_DOWN_FRAC == 0.25
    src = Path("lumina_core/birth/awakening_physics_tape.py").read_text(encoding="utf-8")
    assert "MIN_TREND_UP_FRAC = 0.25" in src
    assert "MIN_TREND_DOWN_FRAC = 0.25" in src
    proto = inspect_physics_protocol()
    assert not str(proto["min_trend_up_frac"]).endswith(":-1")
    assert not str(proto["min_trend_down_frac"]).endswith(":-1")


def test_counts_are_post_enrich() -> None:
    src = Path("lumina_core/birth/awakening_physics_tape.py").read_text(encoding="utf-8")
    assert "counts use post-enrich regime" in src
    ticks = generate_physics_tape_ticks(PhysicsTapeSpec(days=2))
    assert ticks
    assert all("regime" not in row for row in ticks)
    proto = inspect_physics_protocol()
    assert not str(proto["counts_post_enrich"]).endswith(":-1")


def test_forbids_oracle_regime_helper_if_you_wrote_one() -> None:
    banned = ("stamp_oracle_regime", "inject_oracle_regime", "write_regime_after_enrich")
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        for name in banned:
            assert f"def {name}" not in text, f"{rel} defines {name}"
    proto = inspect_physics_protocol()
    assert not str(proto["no_oracle_stamp"]).endswith(":-1")
    tape = Path("lumina_core/birth/awakening_physics_tape.py").read_text(encoding="utf-8")
    assert "No oracle regime stamp" in tape


def test_forbids_old_hashes() -> None:
    assert "5726ae7e" in FORBIDDEN_TAPE_PREFIXES
    assert "e963d1ce" in FORBIDDEN_TAPE_PREFIXES
    assert "afcea4fa" in FORBIDDEN_TAPE_PREFIXES
    assert "5e7eae98" in FORBIDDEN_TAPE_PREFIXES
    assert "7e86c2bb" in FORBIDDEN_TAPE_PREFIXES
    with pytest.raises(PhysicsProtocolError, match="5726ae7e"):
        refuse_this_tape_hash("5726ae7e83ff3d48")
    with pytest.raises(PhysicsProtocolError, match="5e7eae98"):
        refuse_this_tape_hash("5e7eae98d1b4d228")
    assert refuse_this_tape_hash("abc123def4567890") == "abc123def4567890"
    proto = inspect_physics_protocol()
    assert not str(proto["forbidden_hashes"]).endswith(":-1")


def test_forbids_v1_load_as_init() -> None:
    with pytest.raises(PhysicsProtocolError, match="a9ffa852"):
        assert_forbidden_init("baseline_a9ffa852_pi_star.zip", BASELINE_SHA256)
    with pytest.raises(PhysicsProtocolError, match="forbidden init"):
        assert_forbidden_init("genesis_mark_eyes_pi_star.zip")
    with pytest.raises(PhysicsProtocolError, match="1123282f"):
        assert_forbidden_init("awakening_mark_eyes_v2_pi_star.zip", "1123282f" + ("ab" * 28))
    proto = inspect_physics_protocol()
    assert not str(proto["scratch_init"]).endswith(":-1")


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_physics_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_physics_leg(base, child)
    b = compute_physics_leg(base, child)
    assert a["MOVED"] is True
    licensed = license_physics(a, b, world_ok=True)
    assert licensed["tag"] == TAG_PHYSICS_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_physics(a, compute_physics_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)), world_ok=True)
    assert only_a["tag"] == TAG_PHYSICS_FAIL
    assert only_a["tag"] != TAG_PHYSICS_OK
    proto = inspect_physics_protocol()
    assert not str(proto["license_both_legs"]).endswith(":-1")


def test_world_fail_skips_fake_ok() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_physics_leg(base, child)
    b = compute_physics_leg(base, child)
    licensed = license_physics(a, b, world_ok=False)
    assert licensed["tag"] == TAG_PHYSICS_WORLD_FAIL
    assert licensed["tag"] != TAG_PHYSICS_OK
    flags = compose_physics_flags(
        {"tag": TAG_PHYSICS_OK, "world_ok": False, "MOVED_A": True, "MOVED_B": True, "learn_called": True}
    )
    assert flags["tag"] != TAG_PHYSICS_OK
    assert flags["tag"] == TAG_PHYSICS_WORLD_FAIL
    assert flags["learn_called"] is True
    assert flags["GENESIS_EYES_OK"] is False


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    assert real_data_percentage([{"source": "real_historical"}]) == 0.0
    proto = inspect_physics_protocol()
    assert not str(proto["honesty_synthetic_0"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


def test_protocol_pins_and_hooks() -> None:
    assert MARK_EYES_OBS_DIM == 46
    assert OBSERVATION_DIM == 43
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    proto = inspect_physics_protocol()
    assert proto["gate0_complete"] is True
    flags = compose_physics_flags({"GENESIS_EYES_OK": True, "tag": TAG_PHYSICS_OK, "MOVED_A": True, "MOVED_B": True, "world_ok": True})
    assert flags["GENESIS_EYES_OK"] is False
    thin = compute_physics_leg(_thick(n_policy=160), _thick(n_policy=113, mean_r=0.2))
    assert thin["S_THIN"] is True
    assert license_physics(thin, thin, world_ok=True)["tag"] == TAG_PHYSICS_THIN
    harm = compute_physics_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.04, n_policy=160))
    assert harm["S_HARM"] is True
    assert license_physics(harm, harm, world_ok=True)["tag"] == "S_HARM"
    miss = compute_physics_leg({}, {}, missing=True)
    assert license_physics(miss, miss, missing=True, world_ok=True)["tag"] == "S_MISSING"
    blow = compute_physics_leg(_thick(n_h=10, mean_r=-0.20), _thick(n_h=16, mean_r=-0.10))
    assert blow["HOLE_OK"] is False
    assert blow["MOVED"] is False
