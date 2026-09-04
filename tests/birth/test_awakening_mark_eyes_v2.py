"""AWAKENING_MARK_EYES_V2: new 48-dim eyes, scratch, new tape, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_mark_eyes_v2 import (
    BASELINE_SHA256,
    FORBIDDEN_TAPE_HASHES,
    MARK_EYES_V2_EXTRA,
    MARK_EYES_V2_OBS_DIM,
    TRAIN_SEED,
    V2_HOLDOUT_PCT,
    V2_START_ET_ISO,
    V2_TIMESTEPS,
    MarkEyesV2ProtocolError,
    assert_forbidden_init,
    inspect_v2_protocol,
    refuse_this_tape_hash,
)
from lumina_core.birth.awakening_mark_eyes_v2_flags import (
    TAG_V2_FAIL,
    TAG_V2_OK,
    TAG_V2_THIN,
    compose_v2_flags,
    compute_v2_leg,
    license_v2,
)
from lumina_core.birth.awakening_mark_eyes_v2_obs import MarkEyesV2State, concat_mark_eyes_v2
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_mark_eyes_v2.py",
    "lumina_core/birth/awakening_mark_eyes_v2_obs.py",
    "lumina_core/birth/awakening_mark_eyes_v2_env.py",
    "lumina_core/birth/awakening_mark_eyes_v2_train.py",
    "lumina_core/birth/awakening_mark_eyes_v2_eval.py",
    "lumina_core/birth/awakening_mark_eyes_v2_flags.py",
    "lumina_core/birth/awakening_mark_eyes_v2_tables.py",
    "lumina_core/birth/awakening_mark_eyes_v2_report.py",
    "lumina_core/birth/awakening_mark_eyes_v2_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_v2_dim_48() -> None:
    assert MARK_EYES_V2_OBS_DIM == 48
    assert MARK_EYES_V2_EXTRA == 5
    src = Path("lumina_core/birth/awakening_mark_eyes_v2.py").read_text(encoding="utf-8")
    assert "MARK_EYES_V2_OBS_DIM = 48" in src
    out = concat_mark_eyes_v2([0.0] * 43, (0.1, -0.2, 0.5, 0.3, 0.05))
    assert out.shape == (48,)
    proto = inspect_v2_protocol()
    assert not str(proto["mark_eyes_v2_obs_dim_48"]).endswith(":-1")
    assert not str(proto["extra_length_5"]).endswith(":-1")


def test_v1_dim_still_46() -> None:
    assert MARK_EYES_OBS_DIM == 46
    src = Path("lumina_core/birth/awakening_mark_eyes.py").read_text(encoding="utf-8")
    assert "MARK_EYES_OBS_DIM = 46" in src


def test_obs_dim_global_43() -> None:
    assert OBSERVATION_DIM == 43
    src = Path("lumina_core/rl/observation_builder.py").read_text(encoding="utf-8")
    assert "OBSERVATION_DIM = 43" in src


def test_mfe_is_max_unreal() -> None:
    state = MarkEyesV2State()
    state.on_step(position=1, unreal_r=-0.10)
    state.on_step(position=1, unreal_r=0.40)
    state.on_step(position=1, unreal_r=0.15)
    extra = state.extra_vec()
    assert extra[0] == pytest.approx(0.15)
    assert extra[1] == pytest.approx(-0.10)
    assert extra[3] == pytest.approx(0.40)
    src = Path("lumina_core/birth/awakening_mark_eyes_v2_obs.py").read_text(encoding="utf-8")
    start = src.index("def on_step")
    end = src.index("\n    def extra_vec")
    body = src[start:end]
    assert "high" not in body
    assert "low" not in body
    assert "mfe is max unreal, not wick" in body
    proto = inspect_v2_protocol()
    assert not str(proto["mfe_is_max_unreal_not_wick"]).endswith(":-1")


def test_d_unreal_zero_on_first_bar() -> None:
    state = MarkEyesV2State()
    state.on_step(position=1, unreal_r=-0.20)
    extra = state.extra_vec()
    assert extra[4] == pytest.approx(0.0)
    state.on_step(position=1, unreal_r=-0.05)
    extra = state.extra_vec()
    assert extra[4] == pytest.approx(0.15)
    proto = inspect_v2_protocol()
    assert not str(proto["d_unreal_first_bar_0"]).endswith(":-1")


def test_flat_extra_zero() -> None:
    state = MarkEyesV2State()
    state.on_step(position=1, unreal_r=-0.50)
    state.on_step(position=0, unreal_r=-0.50)
    assert state.extra_vec() == (0.0, 0.0, 0.0, 0.0, 0.0)


def test_forbids_loading_baseline_as_init() -> None:
    with pytest.raises(MarkEyesV2ProtocolError, match="a9ffa852"):
        assert_forbidden_init("baseline_mark_eyes_v1_pi_star.zip", BASELINE_SHA256)
    with pytest.raises(MarkEyesV2ProtocolError, match="forbidden init"):
        assert_forbidden_init("genesis_mark_eyes_pi_star.zip")
    proto = inspect_v2_protocol()
    assert not str(proto["forbidden_load_a9ffa852"]).endswith(":-1")
    assert not str(proto["scratch_init_only"]).endswith(":-1")


def test_forbids_polish_zip_as_init() -> None:
    with pytest.raises(MarkEyesV2ProtocolError, match="cebe1804"):
        assert_forbidden_init("awakening_mark_eyes_polish_pi_star.zip", "cebe1804" + ("ab" * 28))
    with pytest.raises(MarkEyesV2ProtocolError, match="8cc435c6"):
        assert_forbidden_init("birth_exit_pi_star.zip", "8cc435c6" + ("cd" * 28))
    proto = inspect_v2_protocol()
    assert not str(proto["forbidden_load_cebe1804"]).endswith(":-1")
    assert not str(proto["forbidden_load_8cc435c6"]).endswith(":-1")


def test_forbids_old_tape_hashes() -> None:
    assert "5726ae7e83ff3d48" in FORBIDDEN_TAPE_HASHES
    assert "e963d1ce7d726ebf" in FORBIDDEN_TAPE_HASHES
    assert "afcea4fa72734337" in FORBIDDEN_TAPE_HASHES
    assert "7e86c2bb1c71d514" in FORBIDDEN_TAPE_HASHES
    with pytest.raises(MarkEyesV2ProtocolError, match="5726ae7e"):
        refuse_this_tape_hash("5726ae7e83ff3d48")
    with pytest.raises(MarkEyesV2ProtocolError, match="e963d1ce"):
        refuse_this_tape_hash("e963d1ce7d726ebf")
    with pytest.raises(MarkEyesV2ProtocolError, match="afcea4fa"):
        refuse_this_tape_hash("afcea4fa72734337")
    with pytest.raises(MarkEyesV2ProtocolError, match="7e86c2bb"):
        refuse_this_tape_hash("7e86c2bb1c71d514")
    assert refuse_this_tape_hash("abc123def4567890") == "abc123def4567890"


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_v2_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_v2_ok_requires_both() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_v2_leg(base, child)
    b = compute_v2_leg(base, child)
    assert a["MOVED"] is True
    assert a["HOLE_OK"] is True
    licensed = license_v2(a, b)
    assert licensed["tag"] == TAG_V2_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES_V2"
    proto = inspect_v2_protocol()
    assert not str(proto["license_both_legs"]).endswith(":-1")


def test_a_only_is_fail() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_v2_leg(base, child)
    b = compute_v2_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160))
    assert a["MOVED"] is True
    assert b["MOVED"] is False
    licensed = license_v2(a, b)
    assert licensed["tag"] == TAG_V2_FAIL
    assert licensed["tag"] != TAG_V2_OK


def test_genesis_eyes_ok_forced_false() -> None:
    flags = compose_v2_flags({"GENESIS_EYES_OK": True, "tag": TAG_V2_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["GENESIS_EYES_OK"] is False
    proto = inspect_v2_protocol()
    assert not str(proto["genesis_eyes_ok_forced_false"]).endswith(":-1")


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    assert real_data_percentage([{"source": "real_historical"}]) == 0.0
    proto = inspect_v2_protocol()
    assert not str(proto["honesty_synthetic_0"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"


def test_protocol_pins_and_hooks() -> None:
    assert TRAIN_SEED == 20260907
    assert V2_HOLDOUT_PCT == 0.40
    assert V2_TIMESTEPS == 10_000
    assert V2_START_ET_ISO.startswith("2026-05-04")
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    proto = inspect_v2_protocol()
    assert proto["gate0_complete"] is True
    thin = compute_v2_leg(_thick(n_policy=160), _thick(n_policy=113, mean_r=0.2))
    assert thin["S_THIN"] is True
    assert license_v2(thin, thin)["tag"] == TAG_V2_THIN
    harm = compute_v2_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.04, n_policy=160))
    assert harm["S_HARM"] is True
    assert license_v2(harm, harm)["tag"] == "S_HARM"
    miss = compute_v2_leg({}, {}, missing=True)
    assert license_v2(miss, miss, missing=True)["tag"] == "S_MISSING"
    blow = compute_v2_leg(_thick(n_h=10, mean_r=-0.20), _thick(n_h=16, mean_r=-0.10))
    assert blow["HOLE_OK"] is False
    assert blow["MOVED"] is False
