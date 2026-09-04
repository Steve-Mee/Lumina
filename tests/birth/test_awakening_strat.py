"""AWAKENING_STRATIFIED_SPLIT: per-phase 60/40, 25/25 both, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_occupancy_tape import generator_labels
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_strat_flags import (
    TAG_STRAT_BODY,
    TAG_STRAT_OK,
    TAG_STRAT_WORLD_FAIL,
    compose_strat_flags,
    compute_strat_leg,
    license_strat,
)
from lumina_core.birth.awakening_strat_run import body_exam_enabled
from lumina_core.birth.awakening_strat_split import (
    STRAT_TRAIN_PCT,
    StratProtocolError,
    phase_runs,
    split_per_phase_60_40,
)
from lumina_core.birth.awakening_strat_tape import (
    MIN_TREND_DOWN_FRAC,
    MIN_TREND_UP_FRAC,
    STRAT_SEED,
    inspect_strat_protocol,
)
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_strat_tape.py",
    "lumina_core/birth/awakening_strat_split.py",
    "lumina_core/birth/awakening_strat_flags.py",
    "lumina_core/birth/awakening_strat_eval.py",
    "lumina_core/birth/awakening_strat_train.py",
    "lumina_core/birth/awakening_strat_tables.py",
    "lumina_core/birth/awakening_strat_report.py",
    "lumina_core/birth/awakening_strat_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def _fake_222(n: int = 90) -> tuple[list[dict[str, object]], list[str]]:
    phases = generator_labels(n, 6)
    ticks = [{"i": i, "timestamp": f"2026-01-05T{i:06d}"} for i in range(n)]
    return ticks, phases


def _chronological_tail(ticks: list[dict[str, object]], *, hold_pct: float = 0.40) -> tuple[list[object], list[object]]:
    cut = int(len(ticks) * (1.0 - hold_pct))
    return list(ticks[:cut]), list(ticks[cut:])


def test_per_block_cut_not_tail() -> None:
    ticks, phases = _fake_222(90)
    split = split_per_phase_60_40(ticks, phases)
    _train_tail, hold_tail = _chronological_tail(ticks)
    assert [row["i"] for row in split.holdout] != [row["i"] for row in hold_tail]
    assert STRAT_TRAIN_PCT == 0.60
    for start, end, _label in phase_runs(phases):
        length = end - start
        cut = int(length * 0.60)
        block_idx = set(range(start, end))
        train_in = [i for i in split.train_idx if i in block_idx]
        hold_in = [i for i in split.hold_idx if i in block_idx]
        assert train_in == list(range(start, start + cut))
        assert hold_in == list(range(start + cut, end))
    proto = inspect_strat_protocol()
    assert not str(proto["per_block_cut_060"]).endswith(":-1")


def test_reproduces_not_942_hold_up_on_fake_cycle() -> None:
    ticks, phases = _fake_222(90)
    _train_tail, hold_tail = _chronological_tail(ticks)
    hold_tail_up = sum(1 for row in hold_tail if phases[int(row["i"])] == "UP") / len(hold_tail)
    assert hold_tail_up == pytest.approx(0.162, abs=0.01)
    split = split_per_phase_60_40(ticks, phases)
    hold_up = split.hold_gen["UP"] / sum(split.hold_gen.values())
    assert hold_up != pytest.approx(0.162, abs=0.01)
    assert hold_up == pytest.approx(1.0 / 3.0, abs=0.02)


def test_gen_counts_balanced_per_split() -> None:
    for n in (90, 91, 92, 600, 213120):
        ticks, phases = _fake_222(n)
        split = split_per_phase_60_40(ticks, phases)
        for counts in (split.train_gen, split.hold_gen):
            vals = [counts["UP"], counts["DOWN"], counts["RANGE"]]
            side_n = sum(vals)
            assert max(vals) - min(vals) <= 2
            assert all(abs(v - side_n // 3) <= 2 for v in vals)
    proto = inspect_strat_protocol()
    assert not str(proto["gen_counts_per_split"]).endswith(":-1")


def test_no_shuffle() -> None:
    ticks, phases = _fake_222(90)
    split = split_per_phase_60_40(ticks, phases)
    assert split.train_idx == sorted(split.train_idx)
    assert split.hold_idx == sorted(split.hold_idx)
    assert [row["i"] for row in split.train] == split.train_idx
    assert [row["i"] for row in split.holdout] == split.hold_idx
    proto = inspect_strat_protocol()
    assert not str(proto["no_shuffle"]).endswith(":-1")


def test_exam_seed_20260911() -> None:
    assert STRAT_SEED == 20260911
    proto = inspect_strat_protocol()
    assert not str(proto["exam_seed_start_et"]).endswith(":-1")
    assert not str(proto["drift_00024_frozen"]).endswith(":-1")


def test_body_not_called_without_world_ok() -> None:
    assert body_exam_enabled(False) is False
    assert body_exam_enabled(True) is True
    licensed = license_strat({}, {}, world_ok=False)
    assert licensed["tag"] == TAG_STRAT_WORLD_FAIL
    flags = compose_strat_flags(
        {
            "tag": TAG_STRAT_OK,
            "world_ok": False,
            "MOVED_A": True,
            "MOVED_B": True,
            "learn_called": True,
            "child_sha256": "deadbeef",
            "actual_timesteps": 10_000,
        }
    )
    assert flags["tag"] == TAG_STRAT_WORLD_FAIL
    assert flags["learn_called"] is False
    assert flags["child_sha256"] == ""
    proto = inspect_strat_protocol()
    assert not str(proto["body_skipped"]).endswith(":-1")


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_strat_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both_legs() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_strat_leg(base, child)
    b = compute_strat_leg(base, child)
    licensed = license_strat(a, b, world_ok=True)
    assert licensed["tag"] == TAG_STRAT_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_strat(
        a, compute_strat_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)), world_ok=True
    )
    assert only_a["tag"] == TAG_STRAT_BODY
    assert only_a["tag"] != TAG_STRAT_OK
    proto = inspect_strat_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_strat_flags(
        {"GENESIS_EYES_OK": True, "tag": TAG_STRAT_OK, "MOVED_A": True, "MOVED_B": True, "world_ok": True}
    )
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_strat_flags(
        {"tag": TAG_STRAT_OK, "MOVED_A": True, "MOVED_B": False, "world_ok": True}
    )
    assert flags_a_only["tag"] == TAG_STRAT_BODY


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    proto = inspect_strat_protocol()
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
    proto = inspect_strat_protocol()
    assert not str(proto["no_oracle_regime"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_strat_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    assert MIN_TREND_UP_FRAC == 0.25
    assert MIN_TREND_DOWN_FRAC == 0.25
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    assert not str(proto["fracs_25_25"]).endswith(":-1")
    assert not str(proto["hooks_default_false"]).endswith(":-1")
    assert not str(proto["genesis_eyes_ok_false"]).endswith(":-1")
    assert not str(proto["enrich_full_then_slice"]).endswith(":-1")


def test_block_too_short_is_missing() -> None:
    ticks = [{"i": i} for i in range(4)]
    phases = ["UP", "UP", "UP", "UP"]
    with pytest.raises(StratProtocolError, match="S_MISSING"):
        split_per_phase_60_40(ticks, phases)
