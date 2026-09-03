"""Awakening selection: floors pinned, split refuse, budget pin, init path, eval wrap."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.awakening_grind import (
    BIRTH_MEAN_USD,
    BIRTH_N,
    EvaluateOnlyPolicy,
    REGRESS_MEAN_USD,
    TRAIN,
)
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_select import (
    AWAKENING_SELECT_PPO_TIMESTEPS,
    BUDGET_MAX,
    BUDGET_MIN,
    EVAL_B_SEED,
    INIT_SHA256,
    TRAIN_SEED,
    SelectProtocolError,
    assert_budget,
    assert_init_sha,
    assert_isolated_write,
    assert_not_holdout_b_path,
    assert_train_seed,
    overall_select_string,
    resolve_select_init_path,
    select_overfit,
)
from lumina_core.birth.awakening_select_run import load_select_train_tape, run_select_train
from lumina_core.birth.birth_exit_policy_export import (
    is_gitignored_ppo_zip,
    resolve_frozen_policy_path,
)
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import birth_gym_point_value
from lumina_core.rl.gym_stop_fill import birth_force_qty_one


def test_a_floors_and_settlement_still_pinned() -> None:
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_DD_MAX_PCT == pytest.approx(25.0)
    assert S5_DD_EQUITY_USD == pytest.approx(50_000.0)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert birth_gym_point_value() == pytest.approx(5.0)
    assert birth_force_qty_one("stage5_probe_handoff") is True
    assert BIRTH_N == 172
    assert BIRTH_MEAN_USD == pytest.approx(-20.7)
    assert REGRESS_MEAN_USD == pytest.approx(-62.0)
    metrics = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "POLICY_EDGE_MIN_TRADES = 150" in metrics
    tree_files = [
        "lumina_core/birth/awakening_select.py",
        "lumina_core/birth/awakening_select_run.py",
        "lumina_core/birth/awakening_select_env.py",
        "lumina_core/birth/awakening_grind.py",
    ]
    for rel in tree_files:
        src = Path(rel).read_text(encoding="utf-8")
        for token in ("S5_IDLE_REGIMES", "MAX_PLANT", "MAX_TIME_STOP", "if synthetic"):
            assert token not in src


def test_b_train_split_refuse(tmp_path: Path) -> None:
    with pytest.raises(SelectProtocolError, match="holdout seed 20260903"):
        assert_train_seed(EVAL_B_SEED)
    with pytest.raises(SelectProtocolError, match="holdout seed 20260902"):
        assert_train_seed(20260902)
    with pytest.raises(SelectProtocolError, match="holdout B path"):
        assert_not_holdout_b_path(tmp_path / "holdout_b" / "tape.jsonl")
    with pytest.raises(SelectProtocolError, match="holdout B path"):
        assert_not_holdout_b_path("/tmp/workspace_grind_b")
    with pytest.raises(SelectProtocolError, match="20260903"):
        load_select_train_tape(seed=20260903, workspace=tmp_path)
    with pytest.raises(SelectProtocolError, match="holdout B"):
        load_select_train_tape(seed=TRAIN_SEED, workspace=tmp_path, holdout_b_path=tmp_path / "holdout_b")
    with pytest.raises(SelectProtocolError, match="holdout seed"):
        run_select_train(seed=20260903, workspace_root=tmp_path, reports=tmp_path)


def test_c_budget_pin() -> None:
    assert isinstance(AWAKENING_SELECT_PPO_TIMESTEPS, int)
    assert BUDGET_MIN <= AWAKENING_SELECT_PPO_TIMESTEPS <= BUDGET_MAX
    assert assert_budget(AWAKENING_SELECT_PPO_TIMESTEPS) == 10_000
    with pytest.raises(SelectProtocolError, match="outside pin window"):
        assert_budget(100_000)
    with pytest.raises(SelectProtocolError, match="outside pin window"):
        run_select_train(timesteps=100_000)


def test_e_init_child_path_refuses_ppo_zip(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04post_polish_decoy")
    assert is_gitignored_ppo_zip(ppo) is True
    assert resolve_frozen_policy_path(tmp_path) is None
    with pytest.raises(SelectProtocolError, match="refused gitignored ppo"):
        assert_init_sha(ppo)
    dest = resolve_select_init_path(tmp_path)
    assert dest.name == "birth_exit_pi_star.zip"
    assert "lumina_agents/ppo" not in dest.as_posix()
    with pytest.raises(SelectProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "birth_exit_pi_star.zip")
    with pytest.raises(SelectProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "grind_A_close_ledger.jsonl")
    with pytest.raises(SelectProtocolError, match="gitignored ppo"):
        assert_isolated_write(ppo)


class _StubPolicy:
    def __init__(self) -> None:
        self.learn_calls = 0

    def predict(self, observation, *, deterministic: bool = True):
        _ = observation, deterministic
        import numpy as np

        return np.array([1.0, 0.0, 0.0012, 0.002], dtype=np.float32), None

    def learn(self, *args: object, **kwargs: object) -> None:
        self.learn_calls += 1


def test_f_eval_wrapper_learn_raises(tmp_path: Path) -> None:
    assert TRAIN is False
    inner = _StubPolicy()
    wrapped = EvaluateOnlyPolicy(inner)
    with pytest.raises(RuntimeError, match="train=False"):
        wrapped.learn(timesteps=1)
    assert inner.learn_calls == 0

    def _stub_rollout(**kwargs: object) -> SimpleNamespace:
        pol = kwargs["policy"]
        assert isinstance(pol, EvaluateOnlyPolicy)
        with pytest.raises(RuntimeError, match="train=False"):
            pol.learn(timesteps=1)
        return SimpleNamespace(
            trades=0,
            wins=0,
            trajectories=[],
            pnl_series=[],
            r_series=[],
            plant_trades=0,
            plant_wins=0,
            policy_trades=0,
            policy_wins=0,
            participation_force_open=0,
            range_flat_bars=30,
            range_total_signals=100,
            closes_stop=0,
            closes_target=0,
            closes_time_stop=0,
            closes_flatten=0,
            closes_unknown=0,
            rollout_steps=1,
        )

    child = tmp_path / "artifacts" / "awakening_select_pi_star.zip"
    child.parent.mkdir(parents=True)
    child.write_bytes(b"PK\x03\x04child")
    ticks = [
        {
            "timestamp": "2026-09-02T00:00:00Z",
            "last": 21150.0,
            "close": 21150.0,
            "bid": 21149.75,
            "ask": 21150.25,
            "volume": 10,
            "regime": "NEUTRAL",
            "source": "synthetic_cloud_fixture",
        }
        for _ in range(40)
    ]
    result = run_evaluate_only(
        runtime=SimpleNamespace(),
        holdout=ticks,
        workspace_root=tmp_path,
        reports_dir=tmp_path,
        ledger_path=tmp_path / "select_A_close_ledger.jsonl",
        policy=inner,
        policy_path=child,
        rollout_fn=_stub_rollout,
    )
    assert result.train is False
    assert result.optimizer_steps == 0
    assert inner.learn_calls == 0


def test_overfit_rule_and_overall_tag() -> None:
    assert select_overfit(wr_policy_a=0.40, wr_policy_b=0.29) is True
    assert select_overfit(wr_policy_a=0.40, wr_policy_b=0.31) is False
    assert select_overfit(wr_policy_a=0.34, wr_policy_b=0.28) is False
    tagged = overall_select_string("GRIND_REGRESS", "INCONCLUSIVE", overfit=False, noop=False)
    assert "GRIND_REGRESS_AWAKENING_OPEN" in tagged
    assert "SELECT_SHOT" in tagged
    assert "SELECT_OVERFIT=false" in tagged
    assert "SELECT_NOOP=false" in tagged


def test_init_sha_constant_matches_birth_exit_sidecar() -> None:
    sidecar = Path("reports/birth_cloud_run/artifacts/birth_exit_pi_star.json")
    if sidecar.is_file():
        import json

        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload.get("sha256") == INIT_SHA256
    zip_path = Path("reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip")
    if zip_path.is_file():
        assert_init_sha(zip_path) == INIT_SHA256
