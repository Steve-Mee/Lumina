"""Coverage for awakening_hole_tax / _run / SelectPhysicsEnv tax hook. Does not train."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from lumina_core.birth.awakening_hole_tax import (
    AWAKENING_HOLE_TAX_R,
    CONTROL_SHA256,
    INIT_SHA256,
    HoleTaxProtocolError,
    apply_hole_tax,
    child_sidecar_payload,
    child_zip_path,
    hole_tax_ledger_path,
    isolated_workspace,
)
from lumina_core.birth.awakening_hole_tax_path import inspect_hole_tax_protocol
from lumina_core.birth.awakening_hole_tax_run import run_hole_tax_train
from lumina_core.birth.awakening_select_env import SelectPhysicsEnv
from lumina_core.birth import awakening_hole_tax_run as run_mod


def test_inspect_hole_tax_protocol_gate0_sites() -> None:
    dump = inspect_hole_tax_protocol()
    assert dump["missing_sites"] == []
    assert dump["gate0_complete"] is True
    assert dump["apply_hole_tax"].startswith("lumina_core/birth/awakening_hole_tax.py:")
    assert not dump["apply_hole_tax"].endswith(":-1")
    assert "awakening_select_env.py" in dump["env_hook"]


def test_path_helpers_and_sidecar(tmp_path: Path) -> None:
    ws = isolated_workspace(tmp_path)
    assert ws.as_posix().endswith("awakening_hole_tax/workspace")
    assert child_zip_path(tmp_path).name == "awakening_hole_tax_pi_star.zip"
    assert hole_tax_ledger_path(tmp_path, leg="A").name == "hole_tax_A_close_ledger.jsonl"
    assert hole_tax_ledger_path(tmp_path, leg="B").name == "hole_tax_B_close_ledger.jsonl"
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    assert hole_tax_ledger_path(artifacts, leg="A").parent == artifacts
    child = tmp_path / "child.zip"
    child.write_bytes(b"PK\x03\x04child-bytes")
    payload = child_sidecar_payload(
        zip_path=child,
        init_path=tmp_path / "birth_exit_pi_star.zip",
        train_ticks_sha16="abcd",
        train_price_sha16="ef01",
    )
    assert payload["schema"] == "awakening_hole_tax_pi_star_v1"
    assert payload["init_sha256"] == INIT_SHA256
    assert payload["control_sha256"] == CONTROL_SHA256
    assert payload["hole_tax_r"] == pytest.approx(1.0)
    assert payload["gitignored_ppo_fallback"] is False
    assert payload["timesteps"] == 10_000


class _StubInner:
    def __init__(self, *, reward: float = -1.038, reason: str = "stop") -> None:
        self.observation_space = SimpleNamespace()
        self.action_space = SimpleNamespace()
        self.config = SimpleNamespace(
            suppress_random_flatten=False,
            participation_min_dwell_bars=0,
            force_flatten_this_step=False,
            force_time_stop_this_step=False,
            soft_prior_stops=True,
            participation_mode="",
        )
        self._position = 0
        self._idx = 0
        self._equity = 50_000.0
        self.closed = True
        self.reward = reward
        self.reason = reason
        self.reset_calls = 0
        self.close_calls = 0

    def reset(self, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        self.reset_calls += 1
        return np.zeros(4, dtype=np.float32), {}

    def close(self) -> None:
        self.close_calls += 1

    def step(self, action: Any) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        _ = action
        info: dict[str, Any] = {
            "trade_closed": self.closed,
            "close_reason": self.reason,
            "training_reward": self.reward,
        }
        return np.zeros(4, dtype=np.float32), float(self.reward), False, False, info


def _envelope(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "participation_stop_pct": 0.00268,
        "participation_target_pct": 0.00483,
        "participation_min_dwell_bars": 8,
        "participation_band_lo": 0.25,
        "participation_band_hi": 0.75,
        "occupancy_control_window_bars": 50,
        "participation_envelope_enabled": True,
        "range_patience_active": True,
        "participation_min_signals": 50,
        "participation_hysteresis": 0.0,
        "participation_under_band_release_hysteresis": 0.0,
        "stage_range_flat_bars": 95,
        "stage_range_total_signals": 200,
        "occupancy_in_band_seen": True,
    }
    base.update(over)
    return base


def test_select_physics_env_tax_r_zero_unchanged() -> None:
    inner = _StubInner()
    geo = SimpleNamespace(hold_bars=120, stop_pct=0.00268, target_pct=0.00483)
    row = {"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL", "high": 21151.0, "low": 21149.0}
    env = SelectPhysicsEnv(inner, geometry=geo, envelope=_envelope(), enriched=[row], tax_r=0.0)
    _obs, reward, _term, _trunc, info = env.step(np.array([1.0, 0.2, 0.002, 0.003], dtype=np.float32))
    assert reward == pytest.approx(-1.038)
    assert info["regime"] == "NEUTRAL"
    assert info["close_reason"] == "stop"


def test_select_physics_env_tax_r_one_stop_neutral() -> None:
    inner = _StubInner()
    geo = SimpleNamespace(hold_bars=120, stop_pct=0.00268, target_pct=0.00483)
    row = {"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL", "high": 21151.0, "low": 21149.0}
    env = SelectPhysicsEnv(
        inner, geometry=geo, envelope=_envelope(), enriched=[row], tax_r=AWAKENING_HOLE_TAX_R
    )
    _obs, reward, _term, _trunc, info = env.step(np.array([1.0, 0.2, 0.002, 0.003], dtype=np.float32))
    assert reward == pytest.approx(-2.038)
    assert info["select_step_r"] == pytest.approx(-2.038)
    assert info["regime"] == "NEUTRAL"


def test_select_physics_env_tax_skips_target_and_trend() -> None:
    geo = SimpleNamespace(hold_bars=120, stop_pct=0.00268, target_pct=0.00483)
    row_n = {"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL", "high": 21151.0, "low": 21149.0}
    inner_t = _StubInner(reward=1.212, reason="target")
    env_t = SelectPhysicsEnv(
        inner_t, geometry=geo, envelope=_envelope(), enriched=[row_n], tax_r=1.0
    )
    _o, reward_t, *_rest = env_t.step(np.array([0.0, 0.5, 0.002, 0.003], dtype=np.float32))
    assert reward_t == pytest.approx(1.212)
    row_d = {"last": 21150.0, "close": 21150.0, "regime": "TREND_DOWN", "high": 21151.0, "low": 21149.0}
    inner_d = _StubInner(reward=-1.038, reason="stop")
    env_d = SelectPhysicsEnv(
        inner_d, geometry=geo, envelope=_envelope(), enriched=[row_d], tax_r=1.0
    )
    _o, reward_d, *_r = env_d.step(np.array([1.0, 0.2, 0.002, 0.003], dtype=np.float32))
    assert reward_d == pytest.approx(-1.038)


def test_train_reward_fn_hook() -> None:
    inner = _StubInner()
    geo = SimpleNamespace(hold_bars=120, stop_pct=0.00268, target_pct=0.00483)
    row = {"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL", "high": 21151.0, "low": 21149.0}

    def _fn(process_r: float, reason: str, regime: str) -> float:
        return apply_hole_tax(process_r, reason, regime)

    env = SelectPhysicsEnv(
        inner, geometry=geo, envelope=_envelope(), enriched=[row], tax_r=0.0, train_reward_fn=_fn
    )
    _obs, reward, *_rest = env.step(np.array([1.0, 0.2, 0.002, 0.003], dtype=np.float32))
    assert reward == pytest.approx(-2.038)


class _FakeModel:
    def __init__(self, steps: int = 10_000) -> None:
        self.num_timesteps = steps
        self._n_updates = 3

    def learn(self, **kwargs: Any) -> _FakeModel:
        return self


def test_run_hole_tax_train_mocked_one_learn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    init = tmp_path / "artifacts" / "birth_exit_pi_star.zip"
    init.parent.mkdir(parents=True)
    init.write_bytes(b"PK\x03\x04parent")

    class _Tape:
        split = SimpleNamespace(train=[{"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL"}] * 8)
        fixture_manifest = {"hash": "abc", "raw_ticks_hash": "def"}

    monkeypatch.setattr(run_mod, "load_select_train_tape", lambda **_k: {
        "train": [{"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL"}] * 8,
        "ticks_sha16": "abc",
        "bars_sha16": "def",
        "price_sha16": "price",
        "manifest": {},
    })
    monkeypatch.setattr(run_mod, "resolve_hole_tax_init_path", lambda *_a, **_k: init)
    monkeypatch.setattr(run_mod, "assert_init_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(run_mod, "make_select_train_env", lambda *a, **k: SimpleNamespace())

    class _FakeTrainer:
        def __init__(self, engine: Any = None, model_dir: Any = None) -> None:
            self.engine = engine

        def save_weights(self, path: str) -> None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"PK\x03\x04child-different")

    monkeypatch.setattr(run_mod, "PPOTrainer", _FakeTrainer)

    out = run_hole_tax_train(
        seed=20260901,
        timesteps=10_000,
        workspace_root=tmp_path,
        reports=tmp_path,
        learn_fn=lambda **_k: None,
        ppo_load_fn=lambda *_a, **_k: _FakeModel(),
    )
    assert Path(out["child_path"]).is_file()
    assert Path(out["child_path"]).name == "awakening_hole_tax_pi_star.zip"
    assert out["init_sha256"] == INIT_SHA256
    assert out["actual_timesteps"] == 10_000
    assert out["select_noop"] is False
    assert out["hole_tax_r"] == pytest.approx(1.0)
    sidecar = json_load(Path(out["child_path"]).with_suffix(".json"))
    assert sidecar["control_sha256"] == CONTROL_SHA256
    assert sidecar["hole_tax_r"] == pytest.approx(1.0)


def json_load(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def test_run_hole_tax_train_learn_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    init = tmp_path / "artifacts" / "birth_exit_pi_star.zip"
    init.parent.mkdir(parents=True)
    init.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "load_select_train_tape", lambda **_k: {
        "train": [{"last": 1.0, "close": 1.0}],
        "ticks_sha16": "h",
        "bars_sha16": "r",
        "price_sha16": "p",
        "manifest": {},
    })
    monkeypatch.setattr(run_mod, "resolve_hole_tax_init_path", lambda *_a, **_k: init)
    monkeypatch.setattr(run_mod, "assert_init_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(run_mod, "make_select_train_env", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(run_mod, "PPOTrainer", lambda **_k: SimpleNamespace(save_weights=lambda _p: None))

    def _boom(**_k: Any) -> None:
        raise RuntimeError("cuda exploded")

    with pytest.raises(HoleTaxProtocolError, match="HOLE_TAX_INCONCLUSIVE"):
        run_hole_tax_train(
            seed=20260901,
            timesteps=10_000,
            workspace_root=tmp_path,
            reports=tmp_path,
            learn_fn=_boom,
            ppo_load_fn=lambda *_a, **_k: _FakeModel(),
        )


def test_parent_b_hole_n_from_grind_jsonl() -> None:
    from lumina_core.birth.awakening_hole_tax import PARENT_B_HOLE_N, PARENT_B_PLANT_FO
    from lumina_core.birth.awakening_mech import load_close_jsonl, row_is_plant

    path = Path("reports/birth_cloud_run/artifacts/grind_B_close_ledger.jsonl")
    if not path.is_file():
        pytest.skip("grind_B JSONL not in checkout")
    rows = load_close_jsonl(path)
    hole = [
        r
        for r in rows
        if not row_is_plant(r)
        and str(r.get("close_reason") or "") == "stop"
        and str(r.get("regime") or "").upper() == "NEUTRAL"
    ]
    plant = [r for r in rows if row_is_plant(r)]
    assert len(hole) == PARENT_B_HOLE_N
    assert len(plant) == PARENT_B_PLANT_FO
