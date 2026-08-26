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


@pytest.mark.unit
def test_twin_expand_data_eligible_and_dispatch(tmp_path: Path) -> None:
    from lumina_core.birth.birth_control_plane import twin_expand_data_eligible

    cfg = BirthCurriculumConfig(
        autonomous_recovery_enabled=True,
        phoenix_loop_enabled=True,
        phoenix_max_cycles=1,
        birth_twin_freeze_resolve_enabled=True,
    )
    assert twin_expand_data_eligible(
        cfg=cfg,
        twin_confidence=0.88,
        twin_recommendation=True,
        constitution_violations=0,
        twin_mode="shadow",
        plateau_exhausted=True,
    )
    assert not twin_expand_data_eligible(
        cfg=cfg,
        twin_confidence=0.5,
        twin_recommendation=True,
        constitution_violations=0,
        twin_mode="shadow",
        plateau_exhausted=True,
    )
    twin = MagicMock()
    twin.mode = "shadow"

    def _eval(dna: object) -> dict[str, object]:
        prompt = str(getattr(dna, "prompt_id", "") or "")
        content = getattr(dna, "content", {}) or {}
        if "expand" in prompt or str(content.get("action") or "") == "expand_data":
            return {
                "confidence": 0.91,
                "recommendation": True,
                "effective_recommendation": True,
                "executable": True,
                "mode": "shadow",
                "risk_flags": [],
            }
        # Mid-ladder twin gate: not confident enough to CONTINUE past exhaustion.
        return {
            "confidence": 0.40,
            "recommendation": False,
            "effective_recommendation": False,
            "executable": False,
            "mode": "shadow",
            "risk_flags": [],
        }

    twin.evaluate_dna_promotion.side_effect = _eval
    state = OrganismAutonomyState(
        phoenix=PhoenixLoopState(phoenix_count=3),
        death_spiral=DeathSpiralState(),
    )
    decision = evaluate_terminal_stall(
        cfg=cfg,
        autonomy_state=state,
        pending={"terminal_stall_reason": "plateau_evolution_exhausted"},
        curriculum_stage="stage2_range",
        approval_twin=twin,
        stage_trades=712,
        required=300,
        constitution_violations=0,
        fitness_signal=0.27,
        plateau_exhausted=True,
        remediation_cycles_exhausted=True,
        recovery_no_lift_brake=False,
        swarm_tournament_resolved=True,
    )
    assert decision.dispatch == RecoveryDispatch.PHOENIX_RESUME
    assert decision.recommended_action == "expand_and_retry"
    assert decision.needs_attention is False
    assert "Twin expand_data" in decision.message


@pytest.mark.unit
def test_terminal_freeze_restore_identity() -> None:
    from lumina_core.birth.terminal_freeze import (
        build_terminal_freeze,
        restore_identity_from_freeze,
        freeze_blocks_curriculum_grind,
        mark_freeze_resolved,
    )

    freeze = build_terminal_freeze(
        reason="plateau_evolution_exhausted",
        curriculum_stage="stage2_range",
        stages_passed=["stage1_trend"],
        evolution_step=4,
        stage_trades=712,
        stage_wins=194,
    )
    assert freeze_blocks_curriculum_grind(freeze) is True
    stages, stage = restore_identity_from_freeze(
        stages_passed=[],
        curriculum_stage="stage1_trend",
        freeze=freeze,
    )
    assert stages == ["stage1_trend"]
    assert stage == "stage2_range"
    resolved = mark_freeze_resolved(freeze, action="expand_data", resolved_by="twin")
    assert freeze_blocks_curriculum_grind(resolved) is False
