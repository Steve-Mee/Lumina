"""Coverage for awakening_select_path / _run / _env. Does not train. Does not move floors."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from lumina_core.birth.awakening_select import (
    INIT_SHA256,
    SelectProtocolError,
    child_sidecar_payload,
    child_zip_path,
    isolated_workspace,
    price_sha16,
    reports_dir,
    select_ledger_path,
)
from lumina_core.birth.awakening_select_env import (
    SelectPhysicsEnv,
    make_select_train_env,
    select_runtime,
)
from lumina_core.birth.awakening_select_path import inspect_select_protocol
from lumina_core.birth.awakening_select_run import (
    dump_learn_traceback,
    run_select_eval_leg,
    run_select_train,
    select_leg_table,
)
from lumina_core.birth import awakening_select_run as run_mod


def test_inspect_select_protocol_gate0_sites() -> None:
    dump = inspect_select_protocol()
    assert dump["missing_sites"] == []
    assert dump["gate0_complete"] is True
    assert "awakening_select.py" in dump["budget_pin"]
    assert "awakening_grind_run.py" in dump["policy_path_eval"]


def test_path_helpers_and_sidecar(tmp_path: Path) -> None:
    ws = isolated_workspace(tmp_path)
    assert ws.as_posix().endswith("awakening_select/workspace")
    assert child_zip_path(tmp_path).name == "awakening_select_pi_star.zip"
    assert select_ledger_path(tmp_path, leg="A").name == "select_A_close_ledger.jsonl"
    assert select_ledger_path(tmp_path, leg="B").name == "select_B_close_ledger.jsonl"
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    assert select_ledger_path(artifacts, leg="A").parent == artifacts
    birth_ws = tmp_path / "birth_cloud_run" / "workspace"
    birth_ws.mkdir(parents=True)
    assert select_ledger_path(birth_ws, leg="A").as_posix().endswith("artifacts/select_A_close_ledger.jsonl")
    child = tmp_path / "child.zip"
    child.write_bytes(b"PK\x03\x04child-bytes")
    payload = child_sidecar_payload(
        zip_path=child,
        init_path=tmp_path / "birth_exit_pi_star.zip",
        train_ticks_sha16="abcd",
        train_price_sha16="ef01",
    )
    assert payload["schema"] == "awakening_select_pi_star_v1"
    assert payload["init_sha256"] == INIT_SHA256
    assert payload["gitignored_ppo_fallback"] is False
    assert price_sha16([{"last": 1.0}, {"close": 2.0}]) == price_sha16([{"last": 1.0}, {"close": 2.0}])
    assert reports_dir().as_posix().endswith("reports/birth_cloud_run")


def test_select_runtime_and_empty_env() -> None:
    rt = select_runtime()
    assert rt.detect_market_regime(None) == "NEUTRAL"
    with pytest.raises(RuntimeError, match="select train tape empty"):
        make_select_train_env([], workspace_root=".", reports_dir=".", max_steps=8)


class _StubInner:
    def __init__(self) -> None:
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
        self.closed = False
        self.reset_calls = 0
        self.close_calls = 0

    def reset(self, **kwargs: Any) -> tuple[np.ndarray, dict[str, Any]]:
        self.reset_calls += 1
        return np.zeros(4, dtype=np.float32), {}

    def close(self) -> None:
        self.close_calls += 1

    def step(self, action: Any) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        _ = action
        return np.zeros(4, dtype=np.float32), 0.0, False, False, {"trade_closed": self.closed}


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


def test_select_physics_env_reset_render_close_step() -> None:
    inner = _StubInner()
    geo = SimpleNamespace(hold_bars=120, stop_pct=0.00268, target_pct=0.00483)
    row = {"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL", "high": 21151.0, "low": 21149.0}
    env = SelectPhysicsEnv(inner, geometry=geo, envelope=_envelope(), enriched=[row])
    env.render()
    obs, _info = env.reset()
    assert inner.reset_calls == 1
    assert obs.shape == (4,)
    assert len(env.step(np.array([0.0, 0.5, 0.002, 0.003], dtype=np.float32))) == 5
    inner._position = 1
    inner.closed = True
    env.step(np.array([1.0, 0.2, 0.002, 0.003], dtype=np.float32))
    env.close()
    assert inner.close_calls == 1


def test_select_physics_env_rolling_window() -> None:
    inner = _StubInner()
    geo = SimpleNamespace(hold_bars=120, stop_pct=0.00268, target_pct=0.00483)
    row = {"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL", "high": 21151.0, "low": 21149.0}
    env = SelectPhysicsEnv(
        inner,
        geometry=geo,
        envelope=_envelope(stage_range_flat_bars=0, occupancy_in_band_seen=False),
        enriched=[row],
    )
    env._occ_win = [1] * 50
    env.step(np.array([0.0, 0.5, 0.002, 0.003], dtype=np.float32))
    assert env.range_total_signals >= 200


def test_run_select_eval_refuses_ppo_zip(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04decoy")
    with pytest.raises(SelectProtocolError, match="gitignored ppo"):
        run_select_eval_leg(
            holdout=[{"last": 1.0}],
            workspace_root=tmp_path,
            reports_dir=tmp_path,
            ledger_path=tmp_path / "x.jsonl",
            policy_path=ppo,
        )


def test_select_leg_table_and_traceback() -> None:
    rows = [
        {
            "plant": False,
            "force_open": False,
            "close_reason": "stop",
            "regime": "NEUTRAL",
            "trade_r": -1.04,
            "pnl": -117.0,
            "gap": False,
            "cap_hit": False,
        },
        {
            "plant": False,
            "force_open": False,
            "close_reason": "target",
            "regime": "NEUTRAL",
            "trade_r": 1.21,
            "pnl": 136.0,
            "gap": False,
            "cap_hit": False,
        },
        {
            "plant": True,
            "force_open": True,
            "close_reason": "stop",
            "regime": "NEUTRAL",
            "trade_r": -1.5,
            "pnl": -180.0,
            "gap": False,
            "cap_hit": True,
        },
    ]
    metrics = SimpleNamespace(
        oos_sharpe=-4.5, oos_dd_pct=33.0, occupancy=0.76, force_open=10, classification="GRIND_REGRESS"
    )
    table = select_leg_table(
        rows,
        grind_metrics=metrics,
        ticks_sha16="t",
        bars_sha16="b",
        price_sha16_value="p",
        frozen_sha256="f",
    )
    assert table["n"] == 3
    assert table["plant_n"] == 1
    assert table["train"] is False
    text = dump_learn_traceback(SelectProtocolError("boom"))
    assert "boom" in text


class _FakeModel:
    def __init__(self, steps: int = 10_000) -> None:
        self.num_timesteps = steps
        self._n_updates = 3

    def learn(self, **kwargs: Any) -> _FakeModel:
        return self


def test_run_select_train_mocked_one_learn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    init = tmp_path / "artifacts" / "birth_exit_pi_star.zip"
    init.parent.mkdir(parents=True)
    init.write_bytes(b"PK\x03\x04parent")

    class _Tape:
        split = SimpleNamespace(train=[{"last": 21150.0, "close": 21150.0, "regime": "NEUTRAL"}] * 8)
        fixture_manifest = {"hash": "abc", "raw_ticks_hash": "def"}

    monkeypatch.setattr(run_mod, "persist_cloud_fixture", lambda *a, **k: _Tape())
    monkeypatch.setattr(run_mod, "resolve_select_init_path", lambda *_a, **_k: init)
    monkeypatch.setattr(run_mod, "assert_init_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(run_mod, "make_select_train_env", lambda *a, **k: SimpleNamespace())

    class _FakeTrainer:
        def __init__(self, engine: Any = None, model_dir: Any = None) -> None:
            self.engine = engine

        def save_weights(self, path: str) -> None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"PK\x03\x04child-different")

    monkeypatch.setattr(run_mod, "PPOTrainer", _FakeTrainer)

    out = run_select_train(
        seed=20260901,
        timesteps=10_000,
        workspace_root=tmp_path,
        reports=tmp_path,
        learn_fn=lambda **_k: None,
        ppo_load_fn=lambda *_a, **_k: _FakeModel(),
    )
    assert Path(out["child_path"]).is_file()
    assert out["init_sha256"] == INIT_SHA256
    assert out["actual_timesteps"] == 10_000
    assert out["select_noop"] is False
    assert Path(out["child_path"]).with_suffix(".json").is_file()


def test_run_select_train_learn_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    init = tmp_path / "artifacts" / "birth_exit_pi_star.zip"
    init.parent.mkdir(parents=True)
    init.write_bytes(b"PK\x03\x04parent")

    class _Tape:
        split = SimpleNamespace(train=[{"last": 1.0, "close": 1.0}])
        fixture_manifest = {"hash": "h", "raw_ticks_hash": "r"}

    monkeypatch.setattr(run_mod, "persist_cloud_fixture", lambda *a, **k: _Tape())
    monkeypatch.setattr(run_mod, "resolve_select_init_path", lambda *_a, **_k: init)
    monkeypatch.setattr(run_mod, "assert_init_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(run_mod, "make_select_train_env", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(run_mod, "PPOTrainer", lambda **_k: SimpleNamespace(save_weights=lambda _p: None))

    def _boom(**_k: Any) -> None:
        raise RuntimeError("cuda exploded")

    with pytest.raises(SelectProtocolError, match="SELECT_INCONCLUSIVE"):
        run_select_train(
            seed=20260901,
            timesteps=10_000,
            workspace_root=tmp_path,
            reports=tmp_path,
            learn_fn=_boom,
            ppo_load_fn=lambda *_a, **_k: _FakeModel(),
        )
