"""AWAKENING_MARK_EYES_POLISH: continue a9ffa852, new tape, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.awakening_mark_eyes_polish import (
    FORBIDDEN_TAPE_HASHES,
    INIT_SHA256,
    POLISH_FIXTURE_SEED,
    POLISH_HOLDOUT_PCT,
    POLISH_START_ET_ISO,
    POLISH_TIMESTEPS,
    PolishProtocolError,
    assert_init_sha,
    inspect_polish_protocol,
    refuse_forbidden_init,
    refuse_scratch_init,
    refuse_this_tape_hash,
)
from lumina_core.birth.awakening_mark_eyes_polish_flags import (
    TAG_POLISH_FAIL,
    TAG_POLISH_OK,
    TAG_POLISH_THIN,
    TAG_S_HARM,
    compose_polish_flags,
    compute_polish_leg,
    license_polish,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_mark_eyes_polish.py",
    "lumina_core/birth/awakening_mark_eyes_polish_train.py",
    "lumina_core/birth/awakening_mark_eyes_polish_eval.py",
    "lumina_core/birth/awakening_mark_eyes_polish_flags.py",
    "lumina_core/birth/awakening_mark_eyes_polish_tables.py",
    "lumina_core/birth/awakening_mark_eyes_polish_report.py",
    "lumina_core/birth/awakening_mark_eyes_polish_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


@pytest.mark.unit
def test_init_must_be_a9ffa852() -> None:
    assert INIT_SHA256.startswith("a9ffa852")
    proto = inspect_polish_protocol()
    assert not str(proto["init_sha_a9ffa852"]).endswith(":-1")
    with pytest.raises(PolishProtocolError, match="a9ffa852"):
        assert_init_sha("init_mark_eyes_pi_star.zip", "deadbeef" * 8)


@pytest.mark.unit
def test_forbids_parent_and_newborn_and_scratch() -> None:
    with pytest.raises(PolishProtocolError, match="8cc435c6"):
        refuse_forbidden_init("birth_exit_pi_star.zip", "8cc435c6" + ("ab" * 28))
    with pytest.raises(PolishProtocolError, match="d313b107"):
        refuse_forbidden_init("genesis_birth_exit_pi_star.zip", "d313b107" + ("cd" * 28))
    with pytest.raises(PolishProtocolError, match="53df2d78"):
        refuse_forbidden_init("awakening_mark_eyes_pi_star.zip", "53df2d78" + ("ef" * 28))
    with pytest.raises(PolishProtocolError, match="scratch"):
        refuse_scratch_init("scratch_policy.zip")
    with pytest.raises(PolishProtocolError, match="scratch"):
        refuse_scratch_init(init_policy="scratch")
    with pytest.raises(PolishProtocolError, match="forbidden init"):
        refuse_forbidden_init("lumina_agents/ppo/lumina_ppo_policy.zip", INIT_SHA256)
    proto = inspect_polish_protocol()
    for key in ("forbidden_init_8cc435c6", "forbidden_init_d313b107", "forbidden_init_53df2d78", "forbidden_init_scratch"):
        assert not str(proto[key]).endswith(":-1")


@pytest.mark.unit
def test_forbids_old_tape_hashes() -> None:
    assert "5726ae7e83ff3d48" in FORBIDDEN_TAPE_HASHES
    assert "e963d1ce7d726ebf" in FORBIDDEN_TAPE_HASHES
    assert "7e86c2bb1c71d514" in FORBIDDEN_TAPE_HASHES
    with pytest.raises(PolishProtocolError, match="5726ae7e"):
        refuse_this_tape_hash("5726ae7e83ff3d48")
    with pytest.raises(PolishProtocolError, match="e963d1ce"):
        refuse_this_tape_hash("e963d1ce7d726ebf")
    with pytest.raises(PolishProtocolError, match="7e86c2bb"):
        refuse_this_tape_hash("7e86c2bb1c71d514")
    assert refuse_this_tape_hash("abc123def4567890") == "abc123def4567890"


@pytest.mark.unit
def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_polish_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


@pytest.mark.unit
def test_polish_ok_requires_both() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_polish_leg(base, child)
    b = compute_polish_leg(base, child)
    assert a["MOVED"] is True
    assert a["HOLE_OK"] is True
    licensed = license_polish(a, b)
    assert licensed["tag"] == TAG_POLISH_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    proto = inspect_polish_protocol()
    assert not str(proto["license_requires_both_legs"]).endswith(":-1")


@pytest.mark.unit
def test_a_only_is_fail() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_polish_leg(base, child)
    b = compute_polish_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160))
    assert a["MOVED"] is True
    assert b["MOVED"] is False
    licensed = license_polish(a, b)
    assert licensed["tag"] == TAG_POLISH_FAIL
    assert licensed["tag"] != TAG_POLISH_OK


@pytest.mark.unit
def test_genesis_eyes_ok_forced_false() -> None:
    flags = compose_polish_flags({"GENESIS_EYES_OK": True, "tag": TAG_POLISH_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["GENESIS_EYES_OK"] is False
    proto = inspect_polish_protocol()
    assert not str(proto["genesis_eyes_ok_forced_false"]).endswith(":-1")


@pytest.mark.unit
def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    assert real_data_percentage([{"source": "real_historical"}]) == 0.0
    proto = inspect_polish_protocol()
    assert not str(proto["synthetic_pct_zero"]).endswith(":-1")


@pytest.mark.unit
def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


@pytest.mark.unit
def test_protocol_pins_and_hooks() -> None:
    assert POLISH_FIXTURE_SEED == 20260906
    assert POLISH_HOLDOUT_PCT == 0.40
    assert POLISH_TIMESTEPS == 10000
    assert POLISH_START_ET_ISO.startswith("2026-08-03")
    assert OBSERVATION_DIM == 43
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    proto = inspect_polish_protocol()
    assert proto["gate0_complete"] is True
    thin = compute_polish_leg(_thick(n_policy=160), _thick(n_policy=113, mean_r=0.2))
    assert thin["S_THIN"] is True
    assert license_polish(thin, thin)["tag"] == TAG_POLISH_THIN
    harm = compute_polish_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.04, n_policy=160))
    assert harm["S_HARM"] is True
    assert license_polish(harm, harm)["tag"] == TAG_S_HARM
    miss = compute_polish_leg({}, {}, missing=True)
    assert license_polish(miss, miss, missing=True)["tag"] == "S_MISSING"
    blow = compute_polish_leg(_thick(n_h=10, mean_r=-0.20), _thick(n_h=16, mean_r=-0.10))
    assert blow["HOLE_OK"] is False
    assert blow["MOVED"] is False
