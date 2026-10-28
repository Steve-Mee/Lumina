"""Evolution expand no-op must not advance the ladder step."""

from __future__ import annotations

import pytest

from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    PlateauState,
    begin_evolution_step,
    revert_evolution_step_on_noop,
)


@pytest.mark.unit
def test_expand_noop_reverts_ladder_step() -> None:
    state = PlateauState(active=True, evolution_step=0)
    action = begin_evolution_step(state, stage_trades=5000, stage_wins=1500)
    assert action == EvolutionAction.EXPAND_DATA
    assert state.evolution_step == 1

    applied = False
    if not applied:
        revert_evolution_step_on_noop(state)
        state.evolution_noop_count += 1

    assert state.evolution_step == 0
    assert state.evolution_noop_count == 1
    assert state.evolution_rollouts_this_step == 0


@pytest.mark.unit
def test_quarantine_progress_payload_computes_remaining_trades() -> None:
    from lumina_core.birth.config import BirthCurriculumConfig
    from lumina_core.birth.plateau_escalator import (
        apply_plateau_quarantine_on_resume,
        quarantine_progress_payload,
    )

    cfg = BirthCurriculumConfig(plateau_quarantine_rollouts=4, plateau_quarantine_min_trades=500)
    q = apply_plateau_quarantine_on_resume(cfg=cfg, stage_trades=10_000)
    payload = quarantine_progress_payload(q, stage_trades=10_200, cfg=cfg)
    assert payload["plateau_quarantine_trades_new"] == 200
    assert payload["plateau_quarantine_trades_remaining_count"] == 300
    assert payload["plateau_quarantine_blocking"] is True
