"""Birth milestone event taxonomy (ADR-0025) — M5 façade.

Types: ``milestone_event_types``; builders: ``milestone_events_birth`` /
``milestone_events_plateau``.
"""
from __future__ import annotations

from lumina_core.notifications.milestone_event_types import (
    MilestoneCategory,
    MilestoneEvent,
)
from lumina_core.notifications.milestone_events_birth import *  # noqa: F403
from lumina_core.notifications.milestone_events_plateau import *  # noqa: F403

__all__ = [
    "MilestoneCategory",
    "MilestoneEvent",
    "birth_started_event",
    "history_loaded_event",
    "regime_map_ready_event",
    "curriculum_stage4_polish_passed_event",
    "curriculum_stage_passed_event",
    "refinement_started_event",
    "oos_evaluation_passed_event",
    "birth_certificate_issued_event",
    "plateau_evolution_step_event",
    "plateau_evolution_forced_advance_event",
    "plateau_entered_event",
    "hold_trap_detected_event",
    "stall_remediation_step_event",
    "stall_remediation_cycle_event",
    "phoenix_reset_event",
    "learning_breakthrough_event",
    "trade_budget_milestone_event",
    "best_policy_updated_event",
    "evolution_proof_passed_event",
    "evolution_proof_failed_event",
    "birth_gate_warning_event",
    "practice_birth_completed_event",
    "milestone_ids_for_stage",
]
