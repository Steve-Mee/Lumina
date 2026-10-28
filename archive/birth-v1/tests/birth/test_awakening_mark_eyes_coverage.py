"""Coverage for MARK_EYES inspect, state machine, concat, license, report, tiny env."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
from gymnasium.spaces import Box

from lumina_core.birth.awakening_mark_eyes import HOLD_NORM, honesty_paragraph, isolated_workspace
from lumina_core.birth.awakening_mark_eyes_env import MarkEyesEnv
from lumina_core.birth.awakening_mark_eyes_flags import compute_mark_eyes_leg, empty_leg, license_eyes
from lumina_core.birth.awakening_mark_eyes_obs import MarkEyesState, concat_mark_eyes, unreal_r_from_rl
from lumina_core.birth.awakening_mark_eyes_path import inspect_mark_eyes_protocol
from lumina_core.birth.awakening_mark_eyes_report import write_mark_eyes_reports
from lumina_core.rl.observation_builder import OBSERVATION_DIM


class _TinyInner:
    observation_space = Box(-1.0, 1.0, shape=(43,), dtype=np.float32)
    action_space = Box(-1.0, 1.0, shape=(4,), dtype=np.float32)

    def __init__(self) -> None:
        self._position = 0
        self._entry_price = 0.0
        self._entry_stop_pct = 0.002
        self._idx = 0
        self._bars_held = 0
        self.entry_is_plant = False
        self.data = [{"close": 5000.0, "last": 5000.0, "regime": "NEUTRAL"}]

    def reset(self, **kwargs: Any) -> Any:
        _ = kwargs
        self._position = 0
        self._entry_price = 0.0
        return np.zeros(43, dtype=np.float32), {}

    def step(self, action: Any) -> Any:
        _ = action
        self._position = 1
        self._entry_price = 5000.0
        self._bars_held = 1
        info = {"trade_closed": False, "regime": "NEUTRAL"}
        return np.zeros(43, dtype=np.float32), 0.0, False, False, info

    def close(self) -> None:
        return None


def test_coverage_inspect_complete() -> None:
    dump = inspect_mark_eyes_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    assert OBSERVATION_DIM == 43
    assert HOLD_NORM == 120.0


def test_coverage_state_and_concat() -> None:
    state = MarkEyesState()
    state.on_flat()
    assert state.extra_vec() == (0.0, 0.0, 0.0)
    state.on_step(1, 0.10)
    state.on_step(1, -0.30)
    extra = state.extra_vec()
    assert extra[1] == pytest.approx(-0.30)
    vec = concat_mark_eyes(np.zeros(43, dtype=np.float32), extra)
    assert vec.shape == (46,)
    assert float(vec[44]) == pytest.approx(-0.30)


def test_coverage_license_and_honesty() -> None:
    ok = {"HOLE_MOVED": True, "S_HARM": False, "S_MISSING": False, "S_MISSING_HOOK": False}
    fail = {"HOLE_MOVED": False, "S_HARM": False, "S_MISSING": False, "S_MISSING_HOOK": False}
    assert license_eyes(ok, ok)["tag"] == "EYES_OK"
    assert license_eyes(ok, fail)["tag"] == "EYES_FAIL"
    text = honesty_paragraph(tag="EYES_FAIL", law="NONE", licensed_next_family="H_NONE")
    assert "Promoting T_LOCK is forbidden." in text
    assert "T_FP=-0.25 TRANSFER_FAIL" in text
    assert "BOUNCE_WEAK=0.50" in text
    assert isolated_workspace(Path("reports") / "birth_cloud_run").as_posix().endswith(
        "awakening_mark_eyes/workspace"
    )


def test_coverage_report_writers(tmp_path: Path) -> None:
    reports = tmp_path / "birth_cloud_run"
    (reports / "artifacts").mkdir(parents=True)
    proto = inspect_mark_eyes_protocol()
    flags = write_mark_eyes_reports(
        reports=reports,
        overall="GRIND_REGRESS_AWAKENING_OPEN MARK_EYES_WINDOW EYES_MEASURE",
        proto=proto,
        parent_sha="8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
        child_sha="",
        actual_timesteps=0,
        optimizer_steps=0,
        ticks_sha16="7e86c2bb1c71d514",
        init_policy="scratch",
        learn_called=False,
        path_early_present=True,
        hooks_false=True,
        workspace_isolated=True,
        forbidden_init_refused=True,
        leg_a=empty_leg(missing=False, leg="A"),
        leg_b=empty_leg(missing=False, leg="B"),
    )
    assert flags["evolution_proof_stamped"] is False
    assert flags["init_policy"] == "scratch"
    assert (reports / "AWAKENING_MARK_EYES_AUDIT.md").is_file()
    assert (reports / "AWAKENING_MARK_EYES_VERDICT.md").is_file()
    log = (reports / "LUMINA_BIRTH_EXPERIMENT_LOG.md").read_text(encoding="utf-8")
    assert "paper-MAE / T_LOCK / T_FP / DEAD / BOUNCE families are closed" in log


def test_coverage_tiny_env_reset_step() -> None:
    env = MarkEyesEnv(_TinyInner())
    assert env.observation_space.shape == (46,)
    obs, _info = env.reset()
    assert np.asarray(obs).shape == (46,)
    assert float(np.asarray(obs)[43]) == 0.0
    obs2, _r, _t, _tr, info = env.step(np.zeros(4, dtype=np.float32))
    assert np.asarray(obs2).shape == (46,)
    assert "trade_closed" in info
    env.close()


def test_coverage_unreal_from_rl_fail_closed() -> None:
    inner = _TinyInner()
    inner._position = 1
    inner._entry_stop_pct = 0.0
    assert unreal_r_from_rl(inner) is None
    inner._entry_stop_pct = 0.002
    inner._entry_price = 5000.0
    got = unreal_r_from_rl(inner)
    assert got is None or isinstance(got, float)


def test_coverage_leg_flags_thin() -> None:
    rows = [
        {
            "pnl": -1.0,
            "trade_r": -1.04,
            "close_reason": "stop",
            "regime": "NEUTRAL",
            "entry_regime": "NEUTRAL",
            "plant": False,
            "force_open": False,
        }
    ]
    out = compute_mark_eyes_leg(
        rows,
        baseline={"n_H": 78, "mean_r_policy": -0.3093, "present": True},
    )
    assert out["S_THIN"] is True
    assert out["HOLE_MOVED"] is False
