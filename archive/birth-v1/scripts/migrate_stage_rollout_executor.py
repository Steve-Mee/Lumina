"""One-shot migration helper for stage_rollout_executor bus decoupling."""

from __future__ import annotations

from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "lumina_core" / "birth" / "stage_rollout_executor.py"

_NEW_HEADER = '''"""Stage rollout executor — training loop I/O + EventBus choreography only."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.checkpoint import (
    apply_plateau_quarantine_on_checkpoint_resume,
    load_checkpoint_state,
)
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    evaluate_stage_pass,
    filter_ticks_for_stage,
    is_runway_stage,
    should_gen0_soft_pass,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
    stage1_intra_state_from_metrics,
    stage2_intra_state_from_metrics,
    stage1_winrate_pass_threshold,
    stage_pass_trades,
    update_stage1_intra_state,
    update_stage2_intra_state,
)
from lumina_core.birth.data_expansion import expand_birth_data, expansion_ladder_at_max
from lumina_core.birth.meta_controller import (
    BirthMetaController,
    LearningHealth,
    MetaActionPlan,
    RecoveryStrategy,
)
from lumina_core.birth.meta_self_eval import SelfEvalPhase
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.organism_autonomy import RecoveryDispatch
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    EvolutionAction,
    adaptation_stuck_escape_allowed,
    build_plateau_audit,
    can_force_never_stop_recovery,
    evolution_ladder_exhausted,
    is_plateau_quarantine_blocking,
    is_valid_best_policy_snapshot,
    maybe_update_best_winrate,
    plateau_min_stage_trades,
    progress_fields as plateau_progress_fields,
    quarantine_progress_payload,
    remediation_is_exhausted,
    rolling_winrate_last_n_trades,
    sanitize_plateau_best_snapshot,
    sanitize_phantom_evolution_steps,
    sanitize_stuck_plateau_evolution,
    should_block_plateau_recovery,
    should_phoenix_reset,
    should_terminal_plateau_stall,
    should_trades_beyond_gate_hard_stop,
    update_plateau_quarantine_after_rollout,
)
from lumina_core.birth.policy_swarm import (
    PolicySwarmState,
    build_swarm_variants,
    record_swarm_rollout,
    select_swarm_winner,
    swarm_rollout_target,
)
from lumina_core.birth.progress import merge_birth_progress_extra, read_birth_progress, write_birth_progress
from lumina_core.birth.remediation import filter_train_ticks_for_holdout_profile
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stage_pass_receipt import receipt_from_stage_result
from lumina_core.birth.stage_scorecard import (
    build_scorecard_payload,
    calculate_simple_slope,
    compute_stage_blocker,
    enrich_adaptation_payload,
    learning_metric_target,
    pass_criteria_for_stage,
)
from lumina_core.birth.stall_remediation import (
    HUMAN_GATE_REASON,
    StallRemediationAction,
    curate_buffer_bottom_half,
    curate_buffer_top_quartile,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_rollout_executor")

PHOENIX_CYCLE_REASON = "phoenix_cycle"

'''

_REPLACEMENTS: list[tuple[str, str]] = [
    ("plateau_state = PlateauState.from_metrics", "# plateau_state restored via bus"),
    ("remediation_state = StallRemediationState.from_metrics", "# remediation_state restored via bus"),
    ("organism_autonomy_state = OrganismAutonomyState.from_metrics", "# autonomy_state restored via bus"),
    ("meta_controller = BirthMetaController(cur_cfg, host.birth_config.reward)", "# meta via bus"),
    ("meta_controller.restore_state(stage_metrics if isinstance(stage_metrics, dict) else None)", "bus.restore_states(stage=stage, stage_metrics=stage_metrics if isinstance(stage_metrics, dict) else None)"),
    ("return meta_controller.observe(", "return bus.meta_observe(stage, "),
    ("meta_controller.metrics_payload()", "bus.meta_metrics_payload(stage)"),
    ("meta_controller.scorecard_fields(meta_last_plan)", "bus.meta_scorecard_fields(stage, meta_last_plan)"),
    ("BirthMetaController.format_decision_log(plan, trigger=trigger)", "BirthMetaController.format_decision_log(plan, trigger=trigger)"),
    ("meta_controller.explore_multiplier = max(", "bus.meta_patch_state(stage, explore_multiplier=max("),
    ("meta_controller.explore_multiplier = 1.0", "bus.meta_patch_state(stage, explore_multiplier=1.0)"),
    ("meta_controller.active_reward = plan.reward_tweak", "bus.meta_patch_state(stage, active_reward=plan.reward_tweak.__dict__ if plan.reward_tweak else None)"),
    ("meta_controller.active_reward = winner.reward", "bus.meta_patch_state(stage, active_reward=winner.reward.__dict__)"),
    ("meta_controller.format_self_eval_suffix()", "bus.meta_format_self_eval_suffix(stage)"),
    ("meta_controller.record_inject(", "bus.meta_record_inject(stage, "),
    ("return str(meta_controller.self_eval.phase.value)", "return str(bus.meta_self_eval_state(stage).get('phase', ''))"),
    ("meta_controller.active_reward", "bus.meta_controller.active_reward"),
    ("adapt_plan = meta_controller.decide_adaptation(", "adapt_plan = bus.meta_decide_adaptation(stage, "),
    ("meta_controller.maybe_start_self_eval(", "bus.meta_maybe_start_self_eval(stage, "),
    ("meta_controller.is_self_eval_active()", "bool(bus.meta_self_eval_state(stage).get('active', False))"),
    ("meta_controller.self_eval.phase == SelfEvalPhase.PROBING", "bus.meta_self_eval_state(stage).get('phase') == SelfEvalPhase.PROBING.value"),
    ("meta_controller.self_eval.phase == SelfEvalPhase.COMMITTED", "bus.meta_self_eval_state(stage).get('phase') == SelfEvalPhase.COMMITTED.value"),
    ("meta_controller.self_eval.phase == SelfEvalPhase.EXHAUSTED", "bus.meta_self_eval_state(stage).get('phase') == SelfEvalPhase.EXHAUSTED.value"),
    ("meta_controller.self_eval.phase", "SelfEvalPhase(bus.meta_self_eval_state(stage).get('phase', 'idle'))"),
    ("pre_plan = meta_controller.decide_probe_rollout(pre_snap)", "pre_plan = bus.meta_decide_probe_rollout(stage, pre_snap)"),
    ("pre_plan = meta_controller.decide_committed_rollout(pre_snap)", "pre_plan = bus.meta_decide_committed_rollout(stage, pre_snap)"),
    ("pre_plan = meta_controller.decide_review(", "pre_plan = bus.meta_decide(stage, "),
    ("explore_steps = meta_controller.apply_explore_multiplier(", "explore_steps = bus.meta_apply_explore_multiplier(stage, "),
    ("meta_controller.reward_tweak_active", "bool(bus.meta_self_eval_state(stage).get('reward_tweak_active', False))"),
    ("meta_controller.rollouts_since_review += 1", "bus.meta_patch_state(stage, increment_rollouts=True)"),
    ("complete_plan = meta_controller.on_probe_rollout_complete(", "complete_plan = bus.meta_on_probe_complete(stage, "),
    ("prov = meta_controller.evaluate_provisional_fallback(", "prov = bus.meta_evaluate_provisional_fallback(stage, "),
    ("committed_plan = meta_controller.decide_committed_rollout(snap)", "committed_plan = bus.meta_decide_committed_rollout(stage, snap)"),
    ("review_plan = meta_controller.decide_review(", "review_plan = bus.meta_decide(stage, "),
    ("autonomy_decision = evaluate_terminal_stall(", "autonomy_decision = bus.autonomy_evaluate_terminal_stall(stage, "),
    ("if should_enter_plateau(ctx, cfg=cur_cfg):", "if bus.plateau_check_enter(stage, stage_trades=ctx.stage_trades, stage_wins=ctx.stage_wins, required=ctx.required, winrate_trend_slope=ctx.winrate_trend_slope, velocity_stall_attempts=ctx.velocity_stall_attempts, meta_self_eval_phase=ctx.meta_self_eval_phase, range_flat_ratio=0.0, range_round_trips=0, velocity_stall=False):"),
    ("enter_plateau(\n                plateau_state,", "bus.plateau_enter(stage, stage_trades=stage_trades, stage_wins=stage_wins)\n                _plateau_enter_legacy(\n                plateau_state,"),
    ("if not should_run_remediation_instead_of_human_gate(", "if not bus.remediation_should_run(stage, "),
    ("if can_start_remediation(remediation_state, cfg=cur_cfg):", "if bus.remediation_can_start(stage):"),
    ("begin_remediation_cycle(\n                remediation_state,", "bus.remediation_begin_cycle(stage, "),
    ("if is_remediation_exhausted(remediation_state, cfg=cur_cfg):", "if bus.remediation_is_exhausted(stage):"),
    ("action = begin_remediation_step(\n            remediation_state,", "action_raw = bus.remediation_begin_step(stage, "),
    ("record_remediation_outcome(\n            remediation_state,", "# record via bus\n            bus.remediation_record_outcome(stage, "),
    ("if not should_advance_remediation_step(", "if not bus.remediation_should_advance(stage, "),
    ("increment_remediation_rollout(remediation_state)", "bus.remediation_increment_rollout(stage)"),
    ("increment_evolution_rollout(plateau_state)", "bus.plateau_increment_rollout(stage)"),
    ("from lumina_core.birth.phoenix_loop import (\n            begin_phoenix_cycle,\n", "# phoenix via bus\n        from lumina_core.birth.phoenix_loop import (\n            "),
]


def _strip_handler_class(text: str) -> str:
    marker = "\nclass CurriculumStageHandler:"
    idx = text.find(marker)
    if idx == -1:
        return text
    tail = text[idx:]
    all_marker = "\n__all__ = ["
    all_idx = tail.find(all_marker)
    if all_idx == -1:
        return text[:idx]
    return text[:idx] + '\n\n__all__ = ["run_stage_research_loop"]\n'


def main() -> None:
    text = _PATH.read_text(encoding="utf-8")
    # Replace header through logger line
    end_header = text.find("TOPIC_REQUESTED")
    if end_header == -1:
        end_header = text.find("def run_stage_research_loop")
    body = text[end_header:]
    body = body.replace("TOPIC_REQUESTED = ", "# TOPIC_REQUESTED = ")
    body = body.replace("TOPIC_STARTED = ", "# TOPIC_STARTED = ")
    body = body.replace("TOPIC_COMPLETED = ", "# TOPIC_COMPLETED = ")
    body = body.replace("TOPIC_ABORTED = ", "# TOPIC_ABORTED = ")
    for old, new in _REPLACEMENTS:
        body = body.replace(old, new)
    # Inject bus client after cur_cfg assignment
    inject = """
    bus: BirthBusClient | None = getattr(host, "_birth_bus_client", None)
    if bus is None and getattr(host, "event_bus", None) is not None:
        bus = BirthBusClient(
            host.event_bus,
            cur_cfg,
            host.birth_config.reward,
        )
    if bus is None:
        raise RuntimeError("BirthBusClient required for stage rollout executor")
    plateau_state = bus.plateau_state
    remediation_state = bus.remediation_state
    organism_autonomy_state = bus.autonomy_state
    meta_controller = bus.meta_controller
"""
    anchor = "    cur_cfg = host.birth_config.curriculum"
    if anchor in body and "bus: BirthBusClient" not in body:
        body = body.replace(anchor, anchor + inject, 1)
    text = _NEW_HEADER + body
    text = _strip_handler_class(text)
    _PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {_PATH} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
