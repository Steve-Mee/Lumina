"""Organism Autonomy Engine — never-stop recovery orchestration for birth phase."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.death_spiral_guard import (
    DeathSpiralState,
    consume_novelty_budget,
    record_stall_signature,
    reset_after_novelty,
    should_widen_data_horizon,
)
from lumina_core.birth.phoenix_loop import (
    PHOENIX_CYCLE_REASON,
    PhoenixLoopState,
    PhoenixNoveltyAction,
    begin_phoenix_cycle,
    build_phoenix_checkpoint_patch,
    can_start_phoenix,
    select_phoenix_novelty,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.organism_autonomy")


class RecoveryDispatch(str, Enum):
    CONTINUE_LOOP = "continue_loop"
    PHOENIX_RESUME = "phoenix_resume"
    PROVISIONAL_GRADUATE = "provisional_graduate"
    TERMINAL_NOTIFY_ONLY = "terminal_notify_only"


@dataclass(slots=True)
class AutonomyDecision:
    dispatch: RecoveryDispatch
    needs_attention: bool = False
    retryable: bool = True
    stall_reason: str = ""
    recommended_action: str = ""
    checkpoint_patch: dict[str, Any] | None = None
    autonomy_metrics: dict[str, Any] | None = None
    message: str = ""


@dataclass(slots=True)
class OrganismAutonomyState:
    phoenix: PhoenixLoopState
    death_spiral: DeathSpiralState
    last_recommended_action: str = ""
    autonomous_recovery_count: int = 0

    def to_metrics(self) -> dict[str, Any]:
        return {
            **self.phoenix.to_metrics(),
            **self.death_spiral.to_metrics(),
            "autonomous_recovery_count": int(self.autonomous_recovery_count),
            "last_recommended_action": str(self.last_recommended_action),
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> OrganismAutonomyState:
        if not isinstance(metrics, dict):
            return cls(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
        return cls(
            phoenix=PhoenixLoopState.from_metrics(metrics),
            death_spiral=DeathSpiralState.from_metrics(metrics),
            last_recommended_action=str(metrics.get("last_recommended_action", "") or ""),
            autonomous_recovery_count=int(metrics.get("autonomous_recovery_count", 0) or 0),
        )


def map_recommended_to_service_action(recommended: str) -> str:
    """Map plateau audit recommendation to birth_service recovery method."""
    action = str(recommended or "").strip().lower()
    mapping = {
        "continue_evolution": "resume_stalled_stage",
        "policy_rollback": "resume_stalled_stage",
        "explore_boost_anti_hold": "resume_stalled_stage",
        "range_patience_recovery": "resume_stalled_stage",
        "phoenix_reset": "phoenix_recovery",
        "expand_and_retry": "expand_and_retry",
        "expand_data": "expand_and_retry",
        "widen_horizon": "expand_and_retry",
    }
    return mapping.get(action, "resume_stalled_stage")


def evaluate_terminal_stall(
    *,
    cfg: BirthCurriculumConfig,
    autonomy_state: OrganismAutonomyState,
    pending: dict[str, Any],
    curriculum_stage: str,
    stage_trades: int,
    required: int,
    constitution_violations: int,
    fitness_signal: float,
    recommended_recovery_action: str = "",
    remediation_cycles_exhausted: bool = False,
    plateau_exhausted: bool = False,
) -> AutonomyDecision:
    """Decide how to handle a terminal stall without human gate when autonomy enabled."""
    if not cfg.autonomous_recovery_enabled:
        stall_reason = str(
            pending.get("terminal_stall_reason") or pending.get("blocker_reason") or "stage_stalled"
        )
        return AutonomyDecision(
            dispatch=RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
            needs_attention=True,
            retryable=False,
            stall_reason=stall_reason,
            message="Autonomous recovery disabled — operator attention required.",
        )

    blocker_metric = str(pending.get("blocker_metric") or "unknown")
    blocker_value = float(pending.get("blocker_value") or 0.0)
    stall_reason = str(
        pending.get("terminal_stall_reason") or pending.get("blocker_reason") or "stage_stalled"
    )
    recommended = str(recommended_recovery_action or autonomy_state.last_recommended_action or "").strip()
    autonomy_state.last_recommended_action = recommended

    circuit_breaker = record_stall_signature(
        autonomy_state.death_spiral,
        curriculum_stage=curriculum_stage,
        blocker_metric=blocker_metric,
        blocker_value=blocker_value,
        cfg=cfg,
    )

    provisional_ok = (
        cfg.allow_provisional_pass
        and cfg.graduation_mode == "evolution_deferred"
        and constitution_violations == 0
        and stage_trades >= required
        and fitness_signal >= float(cfg.provisional_oos_floor)
        and (plateau_exhausted or remediation_cycles_exhausted)
    )
    if provisional_ok:
        return AutonomyDecision(
            dispatch=RecoveryDispatch.PROVISIONAL_GRADUATE,
            needs_attention=False,
            retryable=True,
            stall_reason=stall_reason,
            recommended_action=recommended or "provisional_graduation",
            autonomy_metrics=autonomy_state.to_metrics(),
            message="Provisional graduation granted — evolution deferred path.",
        )

    if can_start_phoenix(autonomy_state.phoenix, cfg=cfg) and (
        remediation_cycles_exhausted or plateau_exhausted or stall_reason in {
            "plateau_evolution_exhausted",
            "stall_remediation_exhausted",
            PHOENIX_CYCLE_REASON,
        }
    ):
        widen = should_widen_data_horizon(
            autonomy_state.death_spiral,
            phoenix_count=autonomy_state.phoenix.phoenix_count,
            cfg=cfg,
        )
        novelty = select_phoenix_novelty(
            autonomy_state.phoenix,
            cfg=cfg,
            circuit_breaker=widen or circuit_breaker,
        )
        if consume_novelty_budget(autonomy_state.death_spiral) or widen:
            begin_phoenix_cycle(
                autonomy_state.phoenix,
                novelty=novelty,
                stall_reason=stall_reason,
            )
            reset_after_novelty(autonomy_state.death_spiral, cfg=cfg)
            autonomy_state.autonomous_recovery_count += 1
            patch = build_phoenix_checkpoint_patch(
                novelty=novelty,
                curriculum_stage=curriculum_stage,
                cfg=cfg,
            )
            service_action = map_recommended_to_service_action(
                "widen_horizon" if novelty == PhoenixNoveltyAction.WIDEN_HORIZON else recommended
            )
            if novelty in {PhoenixNoveltyAction.EXPAND_DATA, PhoenixNoveltyAction.WIDEN_HORIZON}:
                service_action = "expand_and_retry"
            return AutonomyDecision(
                dispatch=RecoveryDispatch.PHOENIX_RESUME,
                needs_attention=False,
                retryable=True,
                stall_reason=PHOENIX_CYCLE_REASON,
                recommended_action=service_action,
                checkpoint_patch=patch,
                autonomy_metrics=autonomy_state.to_metrics(),
                message=f"Phoenix cycle {autonomy_state.phoenix.phoenix_count}: {novelty.value}",
            )

    if recommended:
        autonomy_state.autonomous_recovery_count += 1
        return AutonomyDecision(
            dispatch=RecoveryDispatch.CONTINUE_LOOP,
            needs_attention=False,
            retryable=True,
            stall_reason=stall_reason,
            recommended_action=map_recommended_to_service_action(recommended),
            autonomy_metrics=autonomy_state.to_metrics(),
            message=f"Autonomous recovery: {recommended}",
        )

    return AutonomyDecision(
        dispatch=RecoveryDispatch.PHOENIX_RESUME,
        needs_attention=False,
        retryable=True,
        stall_reason=PHOENIX_CYCLE_REASON,
        recommended_action="resume_stalled_stage",
        autonomy_metrics=autonomy_state.to_metrics(),
        message="Autonomous resume after stall.",
    )