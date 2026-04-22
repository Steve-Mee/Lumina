from __future__ import annotations

from lumina_core.evolution.meta_swarm import MetaSwarm, meta_swarm_governance_enabled, parallel_realities_from_config


def test_meta_swarm_deliberate_returns_consensus_with_five_votes() -> None:
    swarm = MetaSwarm()
    ctx = {
        "winner_fitness": 10.0,
        "previous_fitness": 5.0,
        "nightly_report": {
            "net_pnl": 100.0,
            "max_drawdown": 800.0,
            "sharpe": 0.5,
            "account_equity": 50_000.0,
        },
        "mode": "sim",
        "sim_days": 7,
        "parallel_realities": 1,
        "generation": 0,
        "neuro_winner_accepted": False,
        "winner_prompt_id": "p1",
    }
    out = swarm.deliberate(ctx)
    assert len(out.round_one) == 5
    assert len(out.round_two) == 5
    assert out.collective_score > 0.0
    roles = {v.agent_id for v in out.round_two}
    assert roles == {"creativity", "risk_guardian", "execution", "reflection", "dream"}


def test_meta_swarm_config_helpers_are_defined() -> None:
    assert isinstance(meta_swarm_governance_enabled(), bool)
    assert 1 <= parallel_realities_from_config() <= 50


def test_meta_swarm_risk_veto_blocks_promotion_on_extreme_drawdown() -> None:
    swarm = MetaSwarm()
    ctx = {
        "winner_fitness": 100.0,
        "previous_fitness": 1.0,
        "nightly_report": {
            "net_pnl": -50_000.0,
            "max_drawdown": 60_000.0,
            "sharpe": -1.0,
            "account_equity": 50_000.0,
        },
        "mode": "sim",
        "sim_days": 3,
        "parallel_realities": 2,
        "generation": 0,
        "neuro_winner_accepted": False,
        "winner_prompt_id": "p1",
    }
    out = swarm.deliberate(ctx)
    assert out.risk_veto is True
    assert out.allow_promotion is False
