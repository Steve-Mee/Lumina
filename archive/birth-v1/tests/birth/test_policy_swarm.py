"""Policy swarm variant selection."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.policy_swarm import (
    PolicySwarmState,
    PolicySwarmVariant,
    PolicySwarmVariantResult,
    build_swarm_variants,
    record_swarm_rollout,
    select_swarm_winner,
    swarm_rollout_target,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_build_swarm_variants_returns_distinct_rewards() -> None:
    baseline = BirthRewardConfig()
    variants = build_swarm_variants(baseline, cfg=_cfg(policy_swarm_variants=3))
    assert len(variants) == 3
    coeffs = {variant.reward.expectancy_coeff for variant in variants}
    assert len(coeffs) >= 2


@pytest.mark.unit
def test_select_swarm_winner_prefers_higher_winrate() -> None:
    state = PolicySwarmState(
        active=False,
        variants=[
            PolicySwarmVariant("a", "A", BirthRewardConfig()),
            PolicySwarmVariant("b", "B", BirthRewardConfig()),
        ],
        results={
            "a": PolicySwarmVariantResult("a", rollouts=4, trades=40, wins=12),
            "b": PolicySwarmVariantResult("b", rollouts=4, trades=40, wins=20),
        },
    )
    winner = select_swarm_winner(state)
    assert winner is not None
    assert winner.variant_id == "b"


@pytest.mark.unit
def test_swarm_rollout_target_from_config() -> None:
    assert swarm_rollout_target(_cfg(policy_swarm_rollouts_per_variant=6)) == 6


@pytest.mark.unit
def test_record_swarm_rollout_accumulates() -> None:
    state = PolicySwarmState(active=True, variants=[PolicySwarmVariant("x", "X", BirthRewardConfig())])
    record_swarm_rollout(state, variant_id="x", trades=10, wins=4, total_pnl=12.5)
    record_swarm_rollout(state, variant_id="x", trades=5, wins=3, total_pnl=-2.0)
    row = state.results["x"]
    assert row.trades == 15
    assert row.wins == 7
    assert row.rollouts == 2