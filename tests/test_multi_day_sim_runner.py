from __future__ import annotations

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner


def _dna(hash_seed: str = "a") -> PolicyDNA:
    return PolicyDNA.create(
        prompt_id="self_evolution_policy",
        version="candidate",
        content=f"prompt:{hash_seed}",
        fitness_score=0.0,
        generation=1,
        lineage_hash="L1",
    )


def test_multi_day_sim_runner_applies_hard_drawdown_guard() -> None:
    runner = MultiDaySimRunner(max_workers=2, drawdown_limit_ratio=0.02)
    results = runner.evaluate_variants(
        [_dna("high-dd")],
        days=3,
        nightly_report={
            "net_pnl": 100.0,
            "sharpe": 0.2,
            "max_drawdown": 1500.0,
            "account_equity": 50000.0,
        },
    )

    assert len(results) == 1
    assert results[0].max_drawdown_ratio > 0.02
    assert results[0].fitness == float("-inf")


def test_multi_day_sim_runner_returns_ranked_results() -> None:
    runner = MultiDaySimRunner(max_workers=4, drawdown_limit_ratio=0.02)
    results = runner.evaluate_variants(
        [_dna("x"), _dna("y"), _dna("z")],
        days=2,
        nightly_report={
            "net_pnl": 250.0,
            "sharpe": 0.8,
            "max_drawdown": 120.0,
            "account_equity": 50000.0,
        },
    )

    assert len(results) == 3
    assert results[0].fitness >= results[-1].fitness
    assert all(item.day_count == 2 for item in results)
