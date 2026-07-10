"""SIM evolution zero-touch approval tests."""

from __future__ import annotations

import pytest

from lumina_core.engine.self_evolution_promotion_gates import should_auto_approve_sim_evolution


@pytest.mark.unit
def test_sim_auto_approve_when_approval_not_required() -> None:
    assert should_auto_approve_sim_evolution(
        mode="sim",
        twin_confidence=0.5,
        approval_required=False,
    )


@pytest.mark.unit
def test_sim_auto_approve_high_twin() -> None:
    assert should_auto_approve_sim_evolution(
        mode="sim",
        twin_confidence=0.92,
        approval_required=True,
    )


@pytest.mark.unit
def test_real_never_auto_approve() -> None:
    assert not should_auto_approve_sim_evolution(
        mode="real",
        twin_confidence=0.99,
        approval_required=False,
    )