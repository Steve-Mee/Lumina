"""PPO neuro multi-reality: metric stress op één rollout (:func:`aggregate_ppo_eval_worst_reality`)."""

from __future__ import annotations

from lumina_core.evolution.reality_generator import aggregate_ppo_eval_worst_reality


def test_aggregate_ppo_single_reality_returns_unchanged_ok() -> None:
    base = {
        "ok": True,
        "backtest_fitness": 10.0,
        "shadow_equity_delta": 1.0,
        "shadow_total_reward": 2.0,
        "backtest_equity_delta": 0.5,
    }
    out = aggregate_ppo_eval_worst_reality(base, 1, stress_seed="t")
    assert out["backtest_fitness"] == 10.0
    assert "_reality_id" not in out


def test_aggregate_ppo_not_ok_passthrough() -> None:
    base = {"ok": False, "backtest_fitness": 0.0}
    out = aggregate_ppo_eval_worst_reality(base, 5, stress_seed="t")
    assert out["ok"] is False


def test_aggregate_ppo_multireality_picks_worst_fitness() -> None:
    base = {
        "ok": True,
        "backtest_fitness": 100.0,
        "shadow_equity_delta": 10.0,
        "shadow_total_reward": 50.0,
        "backtest_equity_delta": 2.0,
    }
    out = aggregate_ppo_eval_worst_reality(base, 8, stress_seed="deterministic_test_seed")
    assert out["ok"] is True
    assert "_reality_name" in out
    assert float(out["backtest_fitness"]) < float(base["backtest_fitness"])
    assert int(out["_reality_id"]) >= 0
