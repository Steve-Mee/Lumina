"""Twin birth/SIM accept_champion freeze resolve (never wipe)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.birth_control_plane import twin_accept_champion_eligible
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.organism_autonomy import (
    OrganismAutonomyState,
    RecoveryDispatch,
    evaluate_terminal_stall,
)
from lumina_core.birth.death_spiral_guard import DeathSpiralState
from lumina_core.birth.phoenix_loop import PhoenixLoopState


@pytest.mark.unit
def test_twin_accept_champion_eligible_happy_path() -> None:
    cfg = BirthCurriculumConfig(birth_twin_freeze_resolve_enabled=True)
    assert twin_accept_champion_eligible(
        cfg=cfg,
        twin_confidence=0.85,
        twin_recommendation=True,
        constitution_violations=0,
        champion_path_exists=True,
        swarm_rejected_no_lift=True,
        twin_mode="shadow",
    )


@pytest.mark.unit
def test_twin_accept_champion_blocked_low_conf() -> None:
    cfg = BirthCurriculumConfig(birth_twin_freeze_resolve_enabled=True)
    assert not twin_accept_champion_eligible(
        cfg=cfg,
        twin_confidence=0.5,
        twin_recommendation=True,
        constitution_violations=0,
        champion_path_exists=True,
        swarm_rejected_no_lift=True,
        twin_mode="shadow",
    )


@pytest.mark.unit
def test_twin_accept_champion_never_with_constitution() -> None:
    cfg = BirthCurriculumConfig(birth_twin_freeze_resolve_enabled=True)
    assert not twin_accept_champion_eligible(
        cfg=cfg,
        twin_confidence=0.99,
        twin_recommendation=True,
        constitution_violations=1,
        champion_path_exists=True,
        swarm_rejected_no_lift=True,
        twin_mode="full_auto",
    )


@pytest.mark.unit
def test_evaluate_terminal_stall_twin_accept_champion(tmp_path: Path) -> None:
    champ = tmp_path / "champ.zip"
    champ.write_bytes(b"pk")
    cfg = BirthCurriculumConfig(
        autonomous_recovery_enabled=True,
        phoenix_loop_enabled=True,
        phoenix_max_cycles=1,
        birth_twin_freeze_resolve_enabled=True,
    )
    twin = MagicMock()
    twin.mode = "shadow"
    twin.evaluate_dna_promotion.return_value = {
        "confidence": 0.90,
        "recommendation": True,
        "effective_recommendation": True,
        "executable": False,
        "mode": "shadow",
        "risk_flags": [],
    }
    state = OrganismAutonomyState(
        phoenix=PhoenixLoopState(phoenix_count=5),  # past phoenix budget
        death_spiral=DeathSpiralState(),
    )
    decision = evaluate_terminal_stall(
        cfg=cfg,
        autonomy_state=state,
        pending={"terminal_stall_reason": "swarm_no_lift", "blocker_metric": "expectancy"},
        curriculum_stage="stage2_range",
        approval_twin=twin,
        stage_trades=500,
        required=300,
        constitution_violations=0,
        fitness_signal=0.3,
        recommended_recovery_action="accept_champion",
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
        recovery_no_lift_brake=True,
        swarm_tournament_resolved=False,
        starship_context={
            "best_edgescore_policy_path": str(champ),
            "swarm_rejected_no_lift": True,
        },
    )
    assert decision.dispatch == RecoveryDispatch.ACCEPT_CHAMPION_RESUME
    assert decision.recommended_action == "accept_champion"
    assert decision.needs_attention is False
