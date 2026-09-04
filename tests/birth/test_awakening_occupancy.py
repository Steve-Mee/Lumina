"""AWAKENING_OCCUPANCY_BALANCE: equal %3 blocks, 25/25, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_occupancy_flags import (
    TAG_OCCUPANCY_BODY,
    TAG_OCCUPANCY_OK,
    TAG_OCCUPANCY_WORLD_FAIL,
    compose_occupancy_flags,
    compute_occupancy_leg,
    license_occupancy,
)
from lumina_core.birth.awakening_occupancy_run import body_exam_enabled
from lumina_core.birth.awakening_occupancy_tape import (
    ALLOWED_PHASE_BLOCKS,
    MIN_TREND_DOWN_FRAC,
    MIN_TREND_UP_FRAC,
    OCCUPANCY_SEED,
    OccupancyProtocolError,
    assert_gen_counts_balanced,
    assert_phase_blocks,
    count_generator_labels,
    generator_labels,
    inspect_occupancy_protocol,
    phase_index,
)
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_occupancy_tape.py",
    "lumina_core/birth/awakening_occupancy_flags.py",
    "lumina_core/birth/awakening_occupancy_eval.py",
    "lumina_core/birth/awakening_occupancy_train.py",
    "lumina_core/birth/awakening_occupancy_tables.py",
    "lumina_core/birth/awakening_occupancy_report.py",
    "lumina_core/birth/awakening_occupancy_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_phase_wraps_mod_3() -> None:
    assert phase_index(0, 90, 6) == 0
    assert {(i * 6 // 90) % 3 for i in range(90)} == {0, 1, 2}
    for n in (90, 91, 92, 213120):
        seen = {phase_index(i, n, 6) for i in range(n)}
        assert seen == {0, 1, 2}
        for i in range(min(n, 40)):
            assert phase_index(i, n, 6) == (i * 6 // n) % 3
            assert phase_index(i, n, 12) == (i * 12 // n) % 3
    proto = inspect_occupancy_protocol()
    assert not str(proto["phase_formula_mod_3"]).endswith(":-1")


def test_blocks_only_6_or_12() -> None:
    assert ALLOWED_PHASE_BLOCKS == frozenset({6, 12})
    assert assert_phase_blocks(6) == 6
    assert assert_phase_blocks(12) == 12
    with pytest.raises(OccupancyProtocolError, match=r"PHASE_BLOCKS in \{6,12\}"):
        assert_phase_blocks(3)
    with pytest.raises(OccupancyProtocolError, match=r"PHASE_BLOCKS in \{6,12\}"):
        assert_phase_blocks(18)
    proto = inspect_occupancy_protocol()
    assert not str(proto["phase_blocks_6_or_12"]).endswith(":-1")


def test_gen_counts_balanced() -> None:
    for n, blocks in ((90, 6), (91, 6), (92, 6), (213120, 6), (213120, 12)):
        counts = count_generator_labels(generator_labels(n, blocks))
        assert_gen_counts_balanced(counts)
        vals = [counts["UP"], counts["DOWN"], counts["RANGE"]]
        assert max(vals) - min(vals) <= 2
        assert all(abs(v - n // 3) <= 2 for v in vals)
    proto = inspect_occupancy_protocol()
    assert not str(proto["gen_counts_n3"]).endswith(":-1")


def test_forbids_3_2_1() -> None:
    with pytest.raises(OccupancyProtocolError, match="3/2/1"):
        assert_gen_counts_balanced({"UP": 106560, "DOWN": 71040, "RANGE": 35520})
    with pytest.raises(OccupancyProtocolError, match="3/2/1"):
        assert_gen_counts_balanced({"UP": 3, "DOWN": 2, "RANGE": 1})


def test_exam_seed_20260910() -> None:
    assert OCCUPANCY_SEED == 20260910
    proto = inspect_occupancy_protocol()
    assert not str(proto["exam_seed_20260910"]).endswith(":-1")
    assert not str(proto["start_et_2026_02_02"]).endswith(":-1")
    assert not str(proto["drift_kappa_attempt2"]).endswith(":-1")


def test_body_not_called_without_world_ok() -> None:
    assert body_exam_enabled(False) is False
    assert body_exam_enabled(True) is True
    licensed = license_occupancy({}, {}, world_ok=False)
    assert licensed["tag"] == TAG_OCCUPANCY_WORLD_FAIL
    flags = compose_occupancy_flags(
        {
            "tag": TAG_OCCUPANCY_OK,
            "world_ok": False,
            "MOVED_A": True,
            "MOVED_B": True,
            "learn_called": True,
            "child_sha256": "deadbeef",
            "actual_timesteps": 10_000,
        }
    )
    assert flags["tag"] == TAG_OCCUPANCY_WORLD_FAIL
    assert flags["learn_called"] is False
    assert flags["child_sha256"] == ""
    proto = inspect_occupancy_protocol()
    assert not str(proto["body_skipped"]).endswith(":-1")


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_occupancy_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both_legs() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_occupancy_leg(base, child)
    b = compute_occupancy_leg(base, child)
    licensed = license_occupancy(a, b, world_ok=True)
    assert licensed["tag"] == TAG_OCCUPANCY_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_occupancy(
        a, compute_occupancy_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)), world_ok=True
    )
    assert only_a["tag"] == TAG_OCCUPANCY_BODY
    assert only_a["tag"] != TAG_OCCUPANCY_OK
    proto = inspect_occupancy_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_occupancy_flags(
        {"GENESIS_EYES_OK": True, "tag": TAG_OCCUPANCY_OK, "MOVED_A": True, "MOVED_B": True, "world_ok": True}
    )
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_occupancy_flags(
        {"tag": TAG_OCCUPANCY_OK, "MOVED_A": True, "MOVED_B": False, "world_ok": True}
    )
    assert flags_a_only["tag"] == TAG_OCCUPANCY_BODY


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    proto = inspect_occupancy_protocol()
    assert not str(proto["honesty_synthetic_0"]).endswith(":-1")


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
    proto = inspect_occupancy_protocol()
    assert not str(proto["no_oracle_regime"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_occupancy_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    assert MIN_TREND_UP_FRAC == 0.25
    assert MIN_TREND_DOWN_FRAC == 0.25
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    assert not str(proto["fracs_25_25"]).endswith(":-1")
    assert not str(proto["hooks_default_false"]).endswith(":-1")
    assert not str(proto["genesis_eyes_ok_forced_false"]).endswith(":-1")
