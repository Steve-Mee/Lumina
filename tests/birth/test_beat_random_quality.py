"""Beat-random remediation: anti-edge locks quality/mine, defers swarm."""

from __future__ import annotations

import pytest

from lumina_core.birth.expectancy_stall import (
    build_expectancy_quality_meta_fields,
    recommended_expectancy_recovery_action,
    stage2_should_defer_swarm_for_expectancy,
)


@pytest.mark.unit
def test_anti_edge_defers_swarm() -> None:
    # Anti-edge + quality budget remaining → defer swarm (beat-random lock).
    assert (
        stage2_should_defer_swarm_for_expectancy(
            expectancy_stall=True,
            remediation_step=2,
            max_quality_steps=4,
            evolution_step=5,
            edge_vs_random=-0.10,
        )
        is True
    )
    assert (
        stage2_should_defer_swarm_for_expectancy(
            expectancy_stall=True,
            remediation_step=3,
            max_quality_steps=4,
            edge_vs_random=-0.05,
        )
        is True
    )
    # Quality steps exhausted: beat-random lock releases (swarm may run).
    assert (
        stage2_should_defer_swarm_for_expectancy(
            expectancy_stall=True,
            remediation_step=4,
            max_quality_steps=4,
            evolution_step=10,
            edge_vs_random=-0.10,
        )
        is False
    )
    # Positive edge + steps exhausted + evolution past defer → not deferred.
    assert (
        stage2_should_defer_swarm_for_expectancy(
            expectancy_stall=True,
            remediation_step=5,
            max_quality_steps=4,
            evolution_step=10,
            edge_vs_random=0.01,
        )
        is False
    )


@pytest.mark.unit
def test_anti_edge_keeps_pattern_inject_not_swarm() -> None:
    action = recommended_expectancy_recovery_action(
        range_flat_ratio=0.45,
        remediation_step=5,
        edge_vs_random=-0.12,
    )
    assert action == "expectancy_quality_reward"


@pytest.mark.unit
def test_quality_fields_beat_random_rationale() -> None:
    fields = build_expectancy_quality_meta_fields(
        range_flat_ratio=0.45,
        remediation_step=2,
        base_explore_steps=2000,
        exploration_steps=2000,
        edge_vs_random=-0.12,
    )
    assert "beat_random" in str(fields.get("rationale") or "")
    assert fields.get("mine") is True
