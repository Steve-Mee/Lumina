from __future__ import annotations

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner
from lumina_core.evolution.reality_generator import build_parallel_reports


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


def test_multi_day_sim_runner_shadow_mode_emits_hypothetical_fills() -> None:
    runner = MultiDaySimRunner(max_workers=2, drawdown_limit_ratio=0.05)
    results = runner.evaluate_variants(
        [_dna("shadow")],
        days=3,
        nightly_report={
            "net_pnl": 75.0,
            "sharpe": 0.6,
            "max_drawdown": 50.0,
            "account_equity": 50000.0,
        },
        shadow_mode=True,
    )

    assert len(results) == 1
    result = results[0]
    assert result.shadow_mode is True
    assert result.hypothetical_fills is not None
    assert len(result.hypothetical_fills) == 3
    assert all(fill.reason == "shadow_validation_no_order_execution" for fill in result.hypothetical_fills)


def test_test_generated_strategy_returns_finite_on_safe_snippet() -> None:
    runner = MultiDaySimRunner(max_workers=2, drawdown_limit_ratio=0.05)
    code = (
        "def generated_strategy(context: dict) -> dict:\n"
        '    """Simple deterministic generated strategy."""\n'
        "    close = list(context.get('close', []) or [])\n"
        "    if len(close) < 3:\n"
        "        return {'name': 'g1', 'regime_focus': 'neutral', 'signal_bias': 'neutral', 'confidence': 0.0, 'rules': ['insufficient_history']}\n"
        "    signal_bias = 'buy' if close[-1] >= close[-2] else 'sell'\n"
        "    return {'name': 'g1', 'regime_focus': 'trending', 'signal_bias': signal_bias, 'confidence': 0.6, 'rules': ['close_momentum']}\n"
    )

    fitness = runner._test_generated_strategy(code)

    assert fitness != float("-inf")


def test_test_generated_strategy_fail_closed_on_unsafe_snippet() -> None:
    runner = MultiDaySimRunner(max_workers=2, drawdown_limit_ratio=0.05)
    unsafe = "import os\ndef generated_strategy(context):\n    return {}\n"

    fitness = runner._test_generated_strategy(unsafe)

    assert fitness == float("-inf")


def test_build_parallel_reports_length_and_stress_names() -> None:
    base = {"net_pnl": 100.0, "max_drawdown": 80.0, "sharpe": 0.5, "account_equity": 50_000.0}
    reps = build_parallel_reports(base, 12, seed="unit")
    assert len(reps) == 12
    names = {r.get("_reality_name") for r in reps}
    assert len(names) >= 3
    assert any(float(r["max_drawdown"]) >= float(base["max_drawdown"]) for r in reps[1:])


def test_multi_day_sim_runner_parallel_realities_aggregates_one_per_variant() -> None:
    runner = MultiDaySimRunner(max_workers=8, drawdown_limit_ratio=0.35)
    results = runner.evaluate_variants(
        [_dna("pr-a"), _dna("pr-b")],
        days=2,
        nightly_report={
            "net_pnl": 200.0,
            "sharpe": 0.7,
            "max_drawdown": 90.0,
            "account_equity": 50_000.0,
        },
        parallel_realities=5,
    )
    assert len(results) == 2
    assert all(r.day_count == 2 for r in results)
    assert results[0].fitness >= results[-1].fitness
    assert all(r.fitness > float("-inf") for r in results)


def test_multi_day_sim_runner_shadow_ignores_parallel_realities() -> None:
    runner = MultiDaySimRunner(max_workers=4, drawdown_limit_ratio=0.05)
    results = runner.evaluate_variants(
        [_dna("shadow-pr")],
        days=3,
        nightly_report={
            "net_pnl": 75.0,
            "sharpe": 0.6,
            "max_drawdown": 50.0,
            "account_equity": 50_000.0,
        },
        shadow_mode=True,
        parallel_realities=20,
    )
    assert len(results) == 1
    assert results[0].shadow_mode is True
    assert len(results[0].hypothetical_fills or []) == 3
