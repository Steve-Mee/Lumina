"""AWAKENING_PRICE_BAND: in-band gate, no clip-as-success, floor 150, both legs."""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from lumina_core.birth.awakening_band_flags import (
    TAG_BAND_BODY,
    TAG_BAND_HARM,
    TAG_BAND_OK,
    TAG_BAND_THIN,
    TAG_BAND_WORLD_FAIL,
    compose_band_flags,
    compute_band_leg,
    empty_band_flags,
    license_band,
)
from lumina_core.birth.awakening_band_tape import (
    BAND_SEEDS,
    FORBIDDEN_TAPE_PREFIXES,
    NQ_MAX,
    NQ_MIN,
    BandProtocolError,
    assert_forbidden_init,
    decide_world_ok,
    inspect_band_protocol,
    next_band_seed,
    refuse_this_tape_hash,
    tape_in_band,
)
from lumina_core.birth.awakening_mark_eyes import MarkEyesProtocolError
from lumina_core.birth.awakening_mark_eyes_env import make_mark_eyes_eval_env, make_mark_eyes_train_env
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_band_tape.py",
    "lumina_core/birth/awakening_band_flags.py",
    "lumina_core/birth/awakening_band_eval.py",
    "lumina_core/birth/awakening_band_train.py",
    "lumina_core/birth/awakening_band_tables.py",
    "lumina_core/birth/awakening_band_report.py",
    "lumina_core/birth/awakening_band_run.py",
)
GUARD = "lumina_core/birth/birth_constitution_guard.py"


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def _git_ref_exists(ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def test_out_of_band_is_dead_seed() -> None:
    dead_hi, mn, mx = tape_in_band([{"last": 30000.0}, {"last": 21150.0}])
    assert dead_hi is False
    assert mx > NQ_MAX
    dead_lo, mn, _ = tape_in_band([{"last": 11999.0}, {"last": 21150.0}])
    assert dead_lo is False
    assert mn < NQ_MIN
    ok, _, _ = tape_in_band([{"last": 21150.0}, {"last": 18000.0}])
    assert ok is True
    assert decide_world_ok(in_band=False, fracs_ok=True, clipped=False) is False


def test_clip_is_not_world_ok() -> None:
    raw = [{"last": 1.46e7}, {"last": 21150.0}]
    clipped = [{"last": min(max(float(t["last"]), NQ_MIN), NQ_MAX)} for t in raw]
    raw_ok, _, _ = tape_in_band(raw)
    clip_ok, _, _ = tape_in_band(clipped)
    assert raw_ok is False
    assert clip_ok is True
    assert decide_world_ok(in_band=clip_ok, fracs_ok=True, clipped=True) is False
    assert decide_world_ok(in_band=raw_ok, fracs_ok=True, clipped=False) is False
    proto = inspect_band_protocol()
    assert not str(proto["no_clip_as_success"]).endswith(":-1")


def test_max_three_seeds() -> None:
    assert BAND_SEEDS == (20260914, 20260915, 20260916)
    assert len(BAND_SEEDS) == 3
    attempts = [{"seed": int(s), "min": 1.0, "max": 1.46e7, "in_band": False} for s in BAND_SEEDS]
    assert next_band_seed([]) == 20260914
    assert next_band_seed(attempts[:1]) == 20260915
    assert next_band_seed(attempts[:2]) == 20260916
    assert next_band_seed(attempts) is None
    licensed = license_band(compute_band_leg({}, {}), compute_band_leg({}, {}), world_fail=True)
    assert licensed["tag"] == TAG_BAND_WORLD_FAIL
    proto = inspect_band_protocol()
    assert not str(proto["at_most_three_seeds"]).endswith(":-1")
    assert not str(proto["nq_min_max"]).endswith(":-1")


def test_guard_not_patched() -> None:
    proto = inspect_band_protocol()
    loc = str(proto["guard_1pct_unedited"])
    assert loc.startswith(f"{GUARD}:")
    assert not loc.endswith(":-1")
    guard_src = Path(GUARD).read_text(encoding="utf-8")
    assert "BIRTH_MAX_RISK_STOP_PCT = 0.01" in guard_src
    assert "risk_exceeds_1pct" in guard_src
    porcelain = subprocess.check_output(["git", "status", "--porcelain", "--", GUARD], text=True)
    assert porcelain.strip() == ""
    for ref in ("origin/main", "main"):
        if not _git_ref_exists(ref):
            continue
        diff = subprocess.check_output(["git", "diff", ref, "--", GUARD], text=True)
        assert diff == "", f"1% guard patched versus {ref}"
        break
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        assert "def risk_exceeds_1pct" not in text
        assert "guard_bypassed = True" not in text
        assert "BIRTH_MAX_RISK_STOP_PCT = " not in text
    flags = empty_band_flags()
    assert flags["guard_bypassed"] is False
    composed = compose_band_flags({"guard_bypassed": True})
    assert composed["guard_bypassed"] is False


def test_eval_rejects_force_open() -> None:
    with pytest.raises(MarkEyesProtocolError, match="FORCE_OPEN must stay False at eval"):
        make_mark_eyes_eval_env([], workspace_root=".", reports_dir=".", max_steps=1, force_open=True)
    proto = inspect_band_protocol()
    assert not str(proto["eval_refuses_true"]).endswith(":-1")
    assert not str(proto["force_open_train_only"]).endswith(":-1")
    sig = inspect.signature(make_mark_eyes_train_env)
    assert sig.parameters["force_open"].default is False


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    flags = compose_band_flags({"floor_waived": True, "tag": TAG_BAND_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["floor_waived"] is False
    thin_child = compute_band_leg(_thick(n_policy=40, mean_r=-0.20), _thick(n_policy=40, mean_r=-0.10))
    licensed = license_band(thin_child, thin_child)
    assert licensed["tag"] == TAG_BAND_THIN
    assert licensed["tag"] != TAG_BAND_OK
    assert licensed["floor_waived"] is False
    proto = inspect_band_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_band_leg(base, child)
    b = compute_band_leg(base, child)
    licensed = license_band(a, b)
    assert licensed["tag"] == TAG_BAND_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_band(a, compute_band_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)))
    assert only_a["tag"] == TAG_BAND_BODY
    assert only_a["tag"] != TAG_BAND_OK
    proto = inspect_band_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_band_flags({"GENESIS_EYES_OK": True, "tag": TAG_BAND_OK, "MOVED_A": True, "MOVED_B": True})
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_band_flags({"tag": TAG_BAND_OK, "MOVED_A": True, "MOVED_B": False})
    assert flags_a_only["tag"] == TAG_BAND_BODY
    harm = compute_band_leg(_thick(mean_r=0.10, n_policy=160), _thick(mean_r=0.00, n_policy=40))
    assert license_band(harm, harm)["tag"] == TAG_BAND_HARM


def test_forbidden_hashes() -> None:
    for prefix in FORBIDDEN_TAPE_PREFIXES:
        with pytest.raises(BandProtocolError, match="refused old tape hash"):
            refuse_this_tape_hash(prefix + "deadbeef")
    with pytest.raises(BandProtocolError, match="refused forbidden init"):
        assert_forbidden_init("x.zip", "a9ffa852" + ("0" * 56))
    with pytest.raises(BandProtocolError, match="refused forbidden init"):
        assert_forbidden_init("x.zip", "cf70ae5b" + ("0" * 56))
    with pytest.raises(BandProtocolError, match="refused forbidden init"):
        assert_forbidden_init("awakening_obj_v1_pi_star.zip")


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    proto = inspect_band_protocol()
    assert proto["gate0_complete"] is True


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_band_protocol()
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
