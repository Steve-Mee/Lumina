"""Birth curriculum stage training loop (extracted from engine)."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

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
    AdaptationDecision,
    BirthMetaController,
    LearningHealth,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
    get_adaptation_decision,
)
from lumina_core.birth.meta_self_eval import SelfEvalPhase
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.organism_autonomy import (
    OrganismAutonomyState,
    RecoveryDispatch,
    evaluate_terminal_stall,
)
from lumina_core.birth.pattern_miner import mine_winning_patterns
from lumina_core.birth.phoenix_loop import PHOENIX_CYCLE_REASON, PhoenixNoveltyAction
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    EvolutionAction,
    PlateauEnterContext,
    PlateauState,
    adaptation_stuck_escape_allowed,
    begin_evolution_step,
    build_plateau_audit,
    can_force_never_stop_recovery,
    detect_hold_trap,
    detect_over_trading_trap,
    enter_plateau,
    evolution_ladder_exhausted,
    increment_evolution_rollout,
    is_plateau_quarantine_blocking,
    is_valid_best_policy_snapshot,
    maybe_update_best_winrate,
    plateau_min_stage_trades,
    progress_fields as plateau_progress_fields,
    quarantine_progress_payload,
    record_evolution_outcome,
    record_forced_recovery,
    remediation_is_exhausted,
    reset_plateau_for_new_cycle,
    revert_evolution_step_on_noop,
    rolling_winrate_last_n_trades,
    sanitize_plateau_best_snapshot,
    sanitize_phantom_evolution_steps,
    sanitize_stuck_plateau_evolution,
    should_block_plateau_recovery,
    should_enter_plateau,
    should_force_advance_evolution_step,
    should_phoenix_reset,
    should_terminal_plateau_stall,
    should_trades_beyond_gate_hard_stop,
    should_trigger_plateau_evolution_step,
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
from lumina_core.birth.remediation import (
    filter_train_ticks_for_holdout_profile,
)
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stage_pass_receipt import (
    receipt_from_stage_result,
)
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
    StallRemediationState,
    begin_remediation_cycle,
    begin_remediation_step,
    can_start_remediation,
    curate_buffer_bottom_half,
    curate_buffer_top_quartile,
    increment_remediation_rollout,
    is_remediation_exhausted,
    record_remediation_outcome,
    should_advance_remediation_step,
    should_run_remediation_instead_of_human_gate,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_training_loop")


def run_stage_research_loop(
    host: Any,
    *,
    stage: CurriculumStage,
    stage_index: int,
    stage_ticks: list[dict[str, Any]],
    train_ticks: list[dict[str, Any]],
    holdout_ticks: list[dict[str, Any]],
    target: int,
    stage_progress_pct: float,
    training_mode: str,
    ppo_steps_per_update: int,
    polish_ppo_timesteps: int,
    trade_budget_cap: int,
    prefer_real: bool,
    start_price: float,
) -> dict[str, Any] | None:
    """BRO stage loop: oracle mine, expand data, rollout — never stop on underperformance."""
    holdout_ticks_ref = list(holdout_ticks)
    cur_cfg = host.birth_config.curriculum
    news_cfg = host.birth_config.news
    required = stage_pass_trades(stage, cur_cfg)
    stage_pass_criteria = pass_criteria_for_stage(stage, cfg=cur_cfg)
    pass_metric_target = learning_metric_target(
        stage,
        cfg=cur_cfg,
        pass_criteria=stage_pass_criteria,
    )
    allow_provisional = training_mode == "practice" or cur_cfg.allow_provisional_pass
    max_rollouts = (
        cur_cfg.max_rollouts_per_stage
        if allow_provisional
        else min(cur_cfg.max_rollouts_per_stage, cur_cfg.certified_max_rollouts_per_stage)
    )
    stage_trades = 0
    stage_wins = 0
    stage_hold_signals = 0
    stage_total_signals = 0
    stage_range_hold_signals = 0
    stage_range_total_signals = 0
    stage_range_flat_bars = 0
    stage_range_round_trips = 0
    attempt = 0
    escalation_level = 0
    gen0_provisional = False
    patterns_mined = 0
    oracle_wins = 0
    expansion_step = 0
    data_days_loaded = host.birth_config.max_real_days
    hold_stagnation_count = 0
    winrate_stagnation_count = 0
    wall_budget_exhausted = False
    winrate_history: list[float] = []
    stage_val_pnl: list[float] = []
    budget_milestones_notified: set[int] = set()
    hold_trap_milestone_sent = False
    over_trading_milestone_sent = False
    last_range_flat_ratio = 0.0
    last_policy_rollback_attempt = -999
    reward_history: list[float] = []
    low_velocity_attempts = 0
    strong_recovery_mode = False
    strong_recovery_attempts = 0
    plateau_quarantine: dict[str, Any] = {
        "plateau_quarantine_active": False,
        "plateau_quarantine_rollouts_remaining": 0,
        "plateau_quarantine_trades_remaining": 0,
        "plateau_quarantine_trades_at_resume": 0,
    }
    ppo_steps_at_plateau_evolution_step = 0
    wins_at_trade_milestones: dict[int, int] = {}
    sim_ticks_processed_cumulative = 0
    rollout_wall_clock_total_sec = 0.0
    rollout_wall_clock_samples = 0
    evolution_last_action_applied: bool | None = None
    evolution_last_action_detail = ""
    provisional_pass_considered = False
    retries_this_stage = 0
    adaptation_tier = 0
    adaptation_history: list[dict[str, Any]] = []
    last_adaptation_stage_trades = -1
    adaptation_stuck_escapes = 0
    swarm_state = PolicySwarmState()
    oos_proxy_history: list[float] = []
    last_oos_proxy_at_trades = 0
    original_rollout_chunk = cur_cfg.rollout_chunk_trades
    stage_started_at = time.time()
    effective_trade_budget_cap = trade_budget_cap
    checkpoint_state = load_checkpoint_state(host.workspace_root)
    checkpoint_curriculum = str(checkpoint_state.get("curriculum_stage", "") or "").strip().lower()
    stage_metrics = checkpoint_state.get("stage_metrics")
    metrics_match_stage = (
        isinstance(stage_metrics, dict)
        and checkpoint_curriculum == stage.value
        and str(stage_metrics.get("curriculum_stage_scope", stage.value) or stage.value).strip().lower()
        == stage.value
    )
    if metrics_match_stage:
        patterns_mined = max(0, int(stage_metrics.get("patterns_mined", patterns_mined) or patterns_mined))
        stage_trades = max(0, int(stage_metrics.get("stage_trades", stage_trades) or stage_trades))
        stage_wins = max(0, int(stage_metrics.get("stage_wins", stage_wins) or stage_wins))
        stage_hold_signals = max(
            0, int(stage_metrics.get("stage_hold_signals", stage_hold_signals) or stage_hold_signals)
        )
        stage_total_signals = max(
            0, int(stage_metrics.get("stage_total_signals", stage_total_signals) or stage_total_signals)
        )
        stage_range_hold_signals = max(
            0,
            int(stage_metrics.get("stage_range_hold_signals", stage_range_hold_signals) or stage_range_hold_signals),
        )
        stage_range_total_signals = max(
            0,
            int(
                stage_metrics.get("stage_range_total_signals", stage_range_total_signals)
                or stage_range_total_signals
            ),
        )
        stage_range_flat_bars = max(
            0,
            int(stage_metrics.get("stage_range_flat_bars", stage_range_flat_bars) or stage_range_flat_bars),
        )
        stage_range_round_trips = max(
            0,
            int(
                stage_metrics.get("stage_range_round_trips", stage_range_round_trips)
                or stage_range_round_trips
            ),
        )
        raw_history = stage_metrics.get("winrate_history")
        if isinstance(raw_history, list):
            winrate_history = [float(x) for x in raw_history if isinstance(x, (int, float))]
        raw_reward_history = stage_metrics.get("reward_history")
        if isinstance(raw_reward_history, list):
            reward_history = [float(x) for x in raw_reward_history if isinstance(x, (int, float))]
        low_velocity_attempts = max(
            0, int(stage_metrics.get("velocity_stall_attempts", low_velocity_attempts) or 0)
        )
        strong_recovery_mode = bool(stage_metrics.get("strong_recovery_mode", False))
        strong_recovery_attempts = max(
            0, int(stage_metrics.get("strong_recovery_attempts", 0) or 0)
        )
        retries_this_stage = max(0, int(stage_metrics.get("retries_this_stage", 0) or 0))
        adaptation_tier = max(0, int(stage_metrics.get("adaptation_tier", 0) or 0))
        raw_adaptations = stage_metrics.get("adaptation_history")
        if isinstance(raw_adaptations, list):
            adaptation_history = [dict(x) for x in raw_adaptations if isinstance(x, dict)]
        if adaptation_history:
            last_adaptation_stage_trades = stage_trades
        if stage_metrics.get("escalation_level") is not None:
            escalation_level = max(0, int(stage_metrics.get("escalation_level", 0) or 0))
    plateau_state = PlateauState.from_metrics(stage_metrics if metrics_match_stage else {})
    remediation_state = StallRemediationState.from_metrics(
        stage_metrics if metrics_match_stage else {}
    )
    organism_autonomy_state = OrganismAutonomyState.from_metrics(
        stage_metrics if metrics_match_stage else {}
    )
    prev_progress = read_birth_progress(host.workspace_root)
    if str(prev_progress.get("curriculum_stage", "") or "").strip().lower() == stage.value:
        stage_trades = max(0, int(prev_progress.get("stage_trades", 0) or 0))
        if prev_progress.get("stage_wins") is not None:
            stage_wins = max(0, int(prev_progress.get("stage_wins", 0) or 0))
        stage_hold_signals = max(0, int(prev_progress.get("stage_hold_signals", 0) or 0))
        stage_total_signals = max(0, int(prev_progress.get("stage_total_signals", 0) or 0))
        stage_range_flat_bars = max(0, int(prev_progress.get("stage_range_flat_bars", 0) or 0))
        stage_range_round_trips = max(0, int(prev_progress.get("stage_range_round_trips", 0) or 0))
        stage_range_total_signals = max(
            0, int(prev_progress.get("stage_range_total_signals", 0) or 0)
        )
        patterns_mined = max(0, int(prev_progress.get("patterns_mined", 0) or 0))
        oracle_wins = max(0, int(prev_progress.get("oracle_wins", 0) or 0))
        attempt = max(0, int(prev_progress.get("learning_attempt", 0) or 0) - 1)
        escalation_level = max(0, int(prev_progress.get("escalation_level", 0) or 0))
        gen0_provisional = bool(prev_progress.get("gen0_provisional", False))
        expansion_step = max(0, int(prev_progress.get("expansion_step", 0) or 0))
        data_days_loaded = max(
            0,
            int(prev_progress.get("data_days_loaded", data_days_loaded) or data_days_loaded),
        )
    if adaptation_history:
        last_chunk = adaptation_history[-1].get("chunk_target")
        if last_chunk is not None:
            cur_cfg.rollout_chunk_trades = max(
                cur_cfg.exploration_chunk_size,
                int(last_chunk),
            )
    elif strong_recovery_mode:
        cur_cfg.rollout_chunk_trades = max(
            cur_cfg.exploration_chunk_size,
            cur_cfg.exploration_chunk_size * 2,
        )
    if plateau_state.active:
        sanitize_plateau_best_snapshot(
            plateau_state,
            cfg=cur_cfg,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        stage_winrate = float(stage_wins) / float(max(1, stage_trades))
        sanitize_stuck_plateau_evolution(
            plateau_state,
            cfg=cur_cfg,
            current_winrate=stage_winrate,
            pass_target=stage1_winrate_pass_threshold(cur_cfg),
        )
        sanitize_phantom_evolution_steps(plateau_state)
    if metrics_match_stage and isinstance(stage_metrics, dict):
        for key in (
            "plateau_quarantine_active",
            "plateau_quarantine_rollouts_remaining",
            "plateau_quarantine_trades_remaining",
            "plateau_quarantine_trades_at_resume",
        ):
            if key in stage_metrics:
                plateau_quarantine[key] = stage_metrics[key]
        plateau_quarantine.update(
            apply_plateau_quarantine_on_checkpoint_resume(
                cfg=cur_cfg,
                stage_trades=stage_trades,
            )
        )
        low_velocity_attempts = 0
        plateau_state.active = False
        plateau_state.evolution_step = 0
        plateau_state.evolution_rollouts_this_step = 0
        logger.warning(
            "birth.plateau.quarantine resume trades=%s rollouts=%s min_trades=%s",
            stage_trades,
            plateau_quarantine.get("plateau_quarantine_rollouts_remaining"),
            plateau_quarantine.get("plateau_quarantine_trades_remaining"),
        )
    last_stage_trades = -1
    stagnation_count = 0
    chunk_budget = max(5_000, cur_cfg.rollout_chunk_trades * cur_cfg.rollout_step_budget_multiplier)
    active_train = list(train_ticks)
    active_stage_ticks = list(stage_ticks)
    data_exhausted = False
    scorecard_snapshot_trades = stage_trades
    scorecard_snapshot_patterns = patterns_mined
    scorecard_snapshot_at = time.time()
    last_progress_write_at = 0.0
    last_hold_ratio = 0.0

    def _trade_budget_remaining() -> int:
        return max(0, int(effective_trade_budget_cap) - int(host.cumulative_trades))

    def _remediation_exhausted_now() -> bool:
        return remediation_is_exhausted(
            remediation_active=remediation_state.active,
            remediation_step=remediation_state.remediation_step,
            remediation_cycle=remediation_state.remediation_cycle,
            cfg=cur_cfg,
        )

    intra_state: Stage1IntraCurriculumState | None = None
    intra_easy_pool: list[dict[str, Any]] = []
    intra_hard_pool: list[dict[str, Any]] = []
    intra_meta: dict[str, Any] = {}
    intra_s2_state: Stage2IntraCurriculumState | None = None
    intra_s2_easy_pool: list[dict[str, Any]] = []
    intra_s2_hard_pool: list[dict[str, Any]] = []
    intra_s2_meta: dict[str, Any] = {}
    current_intra_sample_pool: list[dict[str, Any]] = []

    def _rebuild_intra_pools(ticks: list[dict[str, Any]]) -> None:
        nonlocal intra_easy_pool, intra_hard_pool, intra_meta
        nonlocal intra_s2_easy_pool, intra_s2_hard_pool, intra_s2_meta
        if stage != CurriculumStage.STAGE1_TREND or not cur_cfg.intra_stage1_enabled:
            intra_easy_pool = []
            intra_hard_pool = []
            intra_meta = {}
        else:
            intra_easy_pool, intra_hard_pool, intra_meta = split_stage1_trend_ticks(
                ticks,
                easy_percentile=cur_cfg.intra_easy_percentile,
                hard_percentile=cur_cfg.intra_hard_percentile,
            )
        if stage != CurriculumStage.STAGE2_RANGE or not cur_cfg.intra_stage2_enabled:
            intra_s2_easy_pool = []
            intra_s2_hard_pool = []
            intra_s2_meta = {}
        else:
            intra_s2_easy_pool, intra_s2_hard_pool, intra_s2_meta = split_stage2_range_ticks(
                ticks,
                easy_percentile=cur_cfg.intra_stage2_easy_percentile,
                hard_percentile=cur_cfg.intra_stage2_hard_percentile,
            )

    if stage == CurriculumStage.STAGE1_TREND and cur_cfg.intra_stage1_enabled:
        if isinstance(stage_metrics, dict) and stage_metrics.get("intra_stage1_hard_pct") is not None:
            intra_state = stage1_intra_state_from_metrics(
                stage_metrics,
                default_hard_pct=cur_cfg.intra_initial_hard_pct,
            )
        else:
            intra_state = Stage1IntraCurriculumState(hard_pct=cur_cfg.intra_initial_hard_pct)
        _rebuild_intra_pools(active_stage_ticks)
    if stage == CurriculumStage.STAGE2_RANGE and cur_cfg.intra_stage2_enabled:
        if isinstance(stage_metrics, dict) and stage_metrics.get("intra_stage2_hard_pct") is not None:
            intra_s2_state = stage2_intra_state_from_metrics(
                stage_metrics,
                default_hard_pct=cur_cfg.intra_stage2_initial_hard_pct,
            )
        else:
            intra_s2_state = Stage2IntraCurriculumState(
                hard_pct=cur_cfg.intra_stage2_initial_hard_pct
            )
        _rebuild_intra_pools(active_stage_ticks)
    last_winrate = 0.0
    meta_controller = BirthMetaController(cur_cfg, host.birth_config.reward)
    meta_controller.restore_state(stage_metrics if isinstance(stage_metrics, dict) else None)
    meta_last_plan: MetaActionPlan | None = None
    meta_message_suffix = ""

    def _apply_oracle_distill() -> str:
        removed = curate_buffer_top_quartile(
            host.buffer,
            keep_pct=float(cur_cfg.plateau_oracle_distill_top_pct),
        )
        if len(host.buffer) >= 256:
            polish = max(1000, int(getattr(cur_cfg, "polish_ppo_timesteps", 10_000)))
            batch = min(5000, polish)
            host.ppo_trainer.update_from_buffer(
                buffer=host.buffer,
                timesteps=batch,
                birth_phase=True,
            )
            host.ppo_steps += batch
        return f"oracle distill (removed {removed} low-reward trajectories)"

    def _apply_phoenix_reset() -> tuple[str, bool]:
        nonlocal escalation_level, strong_recovery_mode
        host.current_policy = host._create_birth_policy(
            allow_load_existing=False,
            force_reinit=True,
        )
        removed = curate_buffer_top_quartile(
            host.buffer,
            keep_pct=float(cur_cfg.plateau_oracle_distill_top_pct),
        )
        if intra_state is not None:
            intra_state.hard_pct = 0.0
            intra_state.easy_trades = 0
            intra_state.easy_wins = 0
            intra_state.easy_winrate_history.clear()
            _rebuild_intra_pools(active_stage_ticks)
        escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 2)
        strong_recovery_mode = True
        detail = f"phoenix reset (policy reinit, buffer curated, removed {removed})"
        try:
            from lumina_core.notifications.milestone_events import phoenix_reset_event

            host._notify_milestone(
                phoenix_reset_event(
                    cycle=plateau_state.full_recovery_cycles,
                    winrate=float(stage_wins) / float(max(1, stage_trades)),
                    detail=detail,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_phoenix_failed: %s", exc)
        return detail, True

    def _rolling_winrate_500() -> float:
        return rolling_winrate_last_n_trades(
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            wins_at_trade=wins_at_trade_milestones,
        )

    def _ppo_steps_since_evolution_step() -> int:
        return max(0, int(host.ppo_steps) - int(ppo_steps_at_plateau_evolution_step))

    def _apply_plateau_evolution_action(action: EvolutionAction) -> tuple[str, bool]:
        nonlocal intra_state
        if action == EvolutionAction.EXPAND_DATA:
            if not cur_cfg.auto_expand_on_adaptation:
                return "expand skipped — auto_expand_on_adaptation disabled", False
            if _maybe_expand_data():
                return "expanded data window", True
            return "expand skipped — data window at max", False
        if action == EvolutionAction.POLICY_ROLLBACK:
            if not is_valid_best_policy_snapshot(plateau_state, cfg=cur_cfg):
                return "rollback skipped — no valid best policy snapshot (min trades)", False
            rollback_path = str(plateau_state.best_policy_path or "").strip()
            if rollback_path and Path(rollback_path).is_file():
                host.current_policy = host._create_birth_policy(
                    allow_load_existing=True,
                    policy_path=rollback_path,
                )
                return f"rollback to {plateau_state.best_winrate:.1%} winrate", True
            return "rollback skipped — no best policy snapshot", False
        if action == EvolutionAction.INTRA_EASY_ONLY:
            if intra_state is not None:
                intra_state.hard_pct = 0.0
                intra_state.easy_trades = 0
                intra_state.easy_wins = 0
                intra_state.easy_winrate_history.clear()
                _rebuild_intra_pools(active_stage_ticks)
                return "intra stage1 easy-only pool", True
            return "intra easy-only skipped — not stage1", False
        if action == EvolutionAction.FRESH_POLICY:
            host.current_policy = host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            return "fresh policy (reinitialized weights, buffer/oracle retained)", True
        if action == EvolutionAction.ORACLE_DISTILL:
            return _apply_oracle_distill(), True
        if action == EvolutionAction.PHOENIX_RESET:
            return _apply_phoenix_reset()
        return "", False

    def _observe_snapshot() -> tuple[Any, StallDetectionResult]:
        return meta_controller.observe(
            winrate_history=winrate_history,
            reward_history=reward_history,
            stage_trades=stage_trades,
            required_trades=required,
            patterns_mined=patterns_mined,
            buffer_size=len(host.buffer),
            escalation_level=escalation_level,
            strong_recovery_mode=strong_recovery_mode,
            strong_recovery_attempts=strong_recovery_attempts,
            low_velocity_attempts=low_velocity_attempts,
            data_exhausted=data_exhausted,
            stage=stage,
            intra_hard_pct=intra_state.hard_pct if intra_state else None,
            attempt=attempt,
            range_flat_ratio=float(stage_range_flat_bars)
            / float(max(1, stage_range_total_signals)),
            range_round_trips=stage_range_round_trips,
            oos_proxy_history=oos_proxy_history,
        )

    def _maybe_run_oos_proxy() -> None:
        nonlocal last_oos_proxy_at_trades
        from lumina_core.birth.oos_proxy import run_oos_proxy_eval, should_run_oos_proxy

        if not should_run_oos_proxy(
            host.cumulative_trades,
            last_oos_proxy_at_trades,
            cfg=cur_cfg,
        ):
            return
        if not holdout_ticks_ref:
            return
        try:
            result = run_oos_proxy_eval(
                runtime=host.runtime,
                holdout_ticks=holdout_ticks_ref,
                policy=host.current_policy,
                workspace_root=host.workspace_root,
                constitution_guard=host._constitution_guard,
                cfg=cur_cfg,
            )
        except Exception as exc:
            logger.debug("birth.oos_proxy_failed: %s", exc)
            return
        proxy_wr = float(result.get("oos_proxy_winrate", 0.0) or 0.0)
        oos_proxy_history.append(proxy_wr)
        if len(oos_proxy_history) > cur_cfg.winrate_trend_window:
            oos_proxy_history.pop(0)
        last_oos_proxy_at_trades = int(host.cumulative_trades)
        logger.info(
            "birth.oos_proxy winrate=%.2f%% trades=%s cumulative=%s",
            proxy_wr * 100.0,
            result.get("oos_proxy_trades", 0),
            host.cumulative_trades,
        )

    def _stage_metrics_payload() -> dict[str, Any]:
        payload = host._stage_metrics_snapshot(
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            stage_hold_signals=stage_hold_signals,
            stage_total_signals=stage_total_signals,
            stage_range_hold_signals=stage_range_hold_signals,
            stage_range_total_signals=stage_range_total_signals,
            stage_range_flat_bars=stage_range_flat_bars,
            stage_range_round_trips=stage_range_round_trips,
            patterns_mined=patterns_mined,
        )
        payload["winrate_history"] = list(winrate_history)
        payload["reward_history"] = list(reward_history)
        payload["velocity_stall_attempts"] = int(low_velocity_attempts)
        payload["strong_recovery_mode"] = bool(strong_recovery_mode)
        payload["strong_recovery_attempts"] = int(strong_recovery_attempts)
        payload["retries_this_stage"] = int(retries_this_stage)
        payload["adaptation_tier"] = int(adaptation_tier)
        payload["adaptation_history"] = list(adaptation_history)
        payload["escalation_level"] = int(escalation_level)
        payload["curriculum_stage_scope"] = stage.value
        if intra_state is not None:
            payload["intra_stage1_hard_pct"] = round(float(intra_state.hard_pct), 4)
            payload["intra_stage1_easy_trades"] = int(intra_state.easy_trades)
            payload["intra_stage1_easy_wins"] = int(intra_state.easy_wins)
            payload["intra_stage1_easy_winrate_history"] = list(intra_state.easy_winrate_history)
            payload["intra_stage1_meta"] = dict(intra_meta)
        if intra_s2_state is not None:
            payload["intra_stage2_hard_pct"] = round(float(intra_s2_state.hard_pct), 4)
            payload["intra_stage2_easy_flat_bars"] = int(intra_s2_state.easy_flat_bars)
            payload["intra_stage2_easy_range_signals"] = int(intra_s2_state.easy_range_signals)
            payload["intra_stage2_easy_flat_ratio_history"] = list(
                intra_s2_state.easy_flat_ratio_history
            )
            payload["intra_stage2_meta"] = dict(intra_s2_meta)
        if cur_cfg.meta_controller_enabled:
            payload.update(meta_controller.metrics_payload())
        payload.update(plateau_state.to_metrics())
        payload.update(remediation_state.to_metrics())
        payload.update(organism_autonomy_state.to_metrics())
        payload.update(swarm_state.to_metrics())
        payload.update(
            quarantine_progress_payload(
                plateau_quarantine,
                stage_trades=stage_trades,
                cfg=cur_cfg,
            )
        )
        payload["plateau_min_stage_trades"] = plateau_min_stage_trades(stage, cur_cfg)
        payload["stage_pass_gate_trades"] = required
        payload["stage_budget_trades"] = target
        return payload

    def _maybe_periodic_checkpoint(phase: str) -> None:
        interval = max(60, int(cur_cfg.checkpoint_interval_sec))
        if host._last_checkpoint_at <= 0.0 or time.time() - host._last_checkpoint_at >= interval:
            host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                phase=phase,
                stage_metrics=_stage_metrics_payload(),
            )

    def _write_progress(
        *,
        phase: str,
        message: str,
        chunk_trades: int = 0,
        rollout_steps: int = 0,
        exploration_active: bool = False,
        hold_ratio: float = 0.0,
    ) -> None:
        nonlocal scorecard_snapshot_trades, scorecard_snapshot_patterns, scorecard_snapshot_at
        nonlocal last_progress_write_at
        current_stage_trades = stage_trades + chunk_trades
        elapsed_snapshot = max(0.0, time.time() - scorecard_snapshot_at)
        constitution_fields = host._constitution_progress_fields()
        scorecard = build_scorecard_payload(
            stage=stage,
            curriculum_index=stage_index + 1,
            stages_passed=list(host._stages_passed),
            stage_trades=current_stage_trades,
            stage_wins=stage_wins,
            stage_hold_signals=stage_hold_signals,
            stage_total_signals=stage_total_signals,
            constitution_violations=int(constitution_fields["constitution_violations_session"]),
            target_trades=target,
            phase=phase,
            patterns_mined=patterns_mined,
            learning_attempt=attempt + 1,
            prev_stage_trades=scorecard_snapshot_trades,
            prev_patterns_mined=scorecard_snapshot_patterns,
            snapshot_elapsed_sec=elapsed_snapshot,
            stage_range_flat_bars=stage_range_flat_bars,
            stage_range_total_signals=stage_range_total_signals,
            stage_range_round_trips=stage_range_round_trips,
            provisional_pass=gen0_provisional,
            cfg=cur_cfg,
        )
        adaptation_fields = enrich_adaptation_payload(
            stage_trades=current_stage_trades,
            required=required,
            winrate_history=winrate_history,
            retries_this_stage=retries_this_stage,
            adaptation_tier=adaptation_tier,
            max_adaptation_tiers=cur_cfg.max_adaptation_tiers,
            max_stage_retries=cur_cfg.max_stage_retries,
            adaptation_history=adaptation_history,
            adaptation_enabled=cur_cfg.adaptation_enabled,
            wall_behavior=cur_cfg.wall_behavior,
            reward_history=reward_history,
            strong_recovery_mode=strong_recovery_mode,
            velocity_stall_attempts=low_velocity_attempts,
            strong_recovery_attempts=strong_recovery_attempts,
            provisional_pass_considered=provisional_pass_considered,
        )
        scorecard.update(adaptation_fields)
        scorecard.update(
            plateau_progress_fields(
                plateau_state,
                stage_trades=current_stage_trades,
                required=required,
                cfg=cur_cfg,
            )
        )
        scorecard.update(
            build_plateau_audit(
                plateau_state,
                stage_trades=current_stage_trades,
                required=required,
                cfg=cur_cfg,
                progress=scorecard,
                remediation_exhausted=remediation_is_exhausted(
                    remediation_active=remediation_state.active,
                    remediation_step=remediation_state.remediation_step,
                    remediation_cycle=remediation_state.remediation_cycle,
                    cfg=cur_cfg,
                ),
                trade_budget_remaining=max(0, trade_budget_cap - host.cumulative_trades),
            )
        )
        scorecard["stall_remediation_cycle"] = int(remediation_state.remediation_cycle)
        scorecard["stall_remediation_step"] = int(remediation_state.remediation_step)
        scorecard["stall_remediation_max_steps"] = int(cur_cfg.stall_remediation_max_steps)
        scorecard["stall_remediation_max_cycles"] = int(cur_cfg.stall_remediation_max_cycles)
        scorecard["stage1_winrate_gate"] = float(
            getattr(cur_cfg, "stage1_winrate_pass_threshold", 0.45)
        )
        scorecard["stage1_winrate_recommended"] = float(
            getattr(cur_cfg, "stage1_winrate_recommended", 0.45)
        )
        scorecard["stage_pass_gate_trades"] = int(required)
        scorecard["stage_budget_trades"] = int(target)
        scorecard["plateau_min_stage_trades"] = int(plateau_min_stage_trades(stage, cur_cfg))
        scorecard["rolling_winrate_500"] = round(_rolling_winrate_500(), 6)
        scorecard.update(
            quarantine_progress_payload(
                plateau_quarantine,
                stage_trades=current_stage_trades,
                cfg=cur_cfg,
            )
        )
        scorecard["sim_ticks_processed_cumulative"] = int(sim_ticks_processed_cumulative)
        if rollout_wall_clock_samples > 0 and stage_trades > 0:
            avg_rollout_sec = rollout_wall_clock_total_sec / float(rollout_wall_clock_samples)
            scorecard["wall_clock_rollout_sec_avg"] = round(avg_rollout_sec, 2)
            trades_per_min = (float(stage_trades) / max(0.01, rollout_wall_clock_total_sec)) * 60.0
            scorecard["wall_clock_trades_per_min"] = round(trades_per_min, 1)
        if evolution_last_action_applied is not None:
            scorecard["evolution_last_action_applied"] = bool(evolution_last_action_applied)
            scorecard["evolution_last_action_detail"] = str(evolution_last_action_detail or "")
        if cur_cfg.meta_controller_enabled:
            scorecard.update(meta_controller.scorecard_fields(meta_last_plan))
        elapsed_stage_sec = max(0.0, time.time() - stage_started_at)
        progress_extra = merge_birth_progress_extra(constitution_fields, scorecard)
        host._emit_birth_progress(
            stage="training_running",
            phase=phase,
            message=message,
            progress_pct=stage_progress_pct,
            cumulative_trades=host.cumulative_trades + chunk_trades,
            target_trades=trade_budget_cap,
            ppo_steps=host.ppo_steps,
            birth_start_time=host.birth_start_time,
            curriculum_stage=stage.value,
            stage_trades=current_stage_trades,
            stage_hold_signals=stage_hold_signals,
            stage_total_signals=stage_total_signals,
            stage_range_hold_signals=stage_range_hold_signals,
            stage_range_total_signals=stage_range_total_signals,
            stage_range_flat_bars=stage_range_flat_bars,
            stage_range_round_trips=stage_range_round_trips,
            stage_range_flat_ratio=round(
                float(stage_range_flat_bars) / float(max(1, stage_range_total_signals)),
                4,
            ),
            rollout_trades=chunk_trades,
            rollout_steps=rollout_steps,
            hold_ratio=round(hold_ratio, 4),
            exploration_active=exploration_active,
            learning_attempt=attempt + 1,
            escalation_level=escalation_level,
            gen0_provisional=gen0_provisional,
            patterns_mined=patterns_mined,
            oracle_wins=oracle_wins,
            data_days_loaded=data_days_loaded,
            expansion_step=expansion_step,
            stage_wall_remaining_sec=max(
                0, int(cur_cfg.max_stage_wall_sec) - int(elapsed_stage_sec)
            ),
            quality_score=float(host._data_manifest.get("quality_score", 0.0) or 0.0),
            intra_hard_pct=round(float(intra_state.hard_pct), 4) if intra_state else None,
            intra_easy_winrate=round(
                float(intra_state.easy_wins) / float(max(1, intra_state.easy_trades)),
                4,
            )
            if intra_state and intra_state.easy_trades > 0
            else None,
            needs_attention=False,
            attention_summary="",
            attention_reason_code="",
            attention_recommended_actions=[],
            user_initiated_stop=False,
            extra_parts=(progress_extra,),
        )
        if (
            current_stage_trades > scorecard_snapshot_trades
            or patterns_mined > scorecard_snapshot_patterns
        ):
            scorecard_snapshot_trades = current_stage_trades
            scorecard_snapshot_patterns = patterns_mined
            scorecard_snapshot_at = time.time()
        last_progress_write_at = time.time()

    def _log_meta_decision(plan: MetaActionPlan, trigger: str) -> None:
        event = BirthMetaController.format_decision_log(plan, trigger=trigger)
        logger.info(
            "birth.meta.decision trigger=%s primary=%s rationale=%s "
            "health=%s combined_velocity=%.6f is_stalled=%s",
            event.get("trigger"),
            event.get("primary"),
            event.get("rationale"),
            event.get("learning_health"),
            float(event.get("combined_velocity", 0.0) or 0.0),
            event.get("is_stalled"),
            extra={"event_data": event},
        )

    def _log_stall_event(
        *,
        event: str,
        stall: StallDetectionResult,
        strong_recovery: bool,
    ) -> None:
        logger.info(
            "birth.%s stage=%s winrate_velocity=%.6f reward_velocity=%.6f "
            "combined=%.6f attempts=%s/%s strong_recovery=%s escalation=%s",
            event,
            stage.value,
            stall.winrate_velocity,
            stall.reward_velocity,
            stall.combined_velocity,
            stall.low_velocity_attempts,
            stall.threshold,
            strong_recovery,
            escalation_level,
        )

    def _log_provisional_pass_outcome(
        *,
        source: str,
        should_grant: bool,
        blocked_reason: str | None,
        safeguards: dict[str, Any],
    ) -> None:
        logger.info(
            "birth.provisional_pass source=%s stage=%s should_grant=%s "
            "blocked_reason=%s safeguards=%s",
            source,
            stage.value,
            should_grant,
            blocked_reason or "",
            safeguards,
        )

    def _apply_meta_plan(plan: MetaActionPlan, *, trigger: str = "") -> None:
        nonlocal escalation_level, strong_recovery_mode, strong_recovery_attempts
        nonlocal low_velocity_attempts, meta_last_plan, meta_message_suffix
        meta_last_plan = plan
        if plan.escalation_delta > 0:
            escalation_level = min(
                cur_cfg.max_escalation_level,
                escalation_level + plan.escalation_delta,
            )
        elif plan.escalation_delta < 0:
            escalation_level = max(0, escalation_level + plan.escalation_delta)
        if plan.chunk_target is not None:
            cur_cfg.rollout_chunk_trades = plan.chunk_target
        if plan.enter_strong_recovery:
            strong_recovery_mode = True
            strong_recovery_attempts = 0
            low_velocity_attempts = 0
            meta_controller.explore_multiplier = max(
                0.4,
                min(1.0, float(cur_cfg.meta_explore_decay_stall)),
            )
        if plan.exit_strong_recovery:
            strong_recovery_mode = False
            strong_recovery_attempts = 0
            cur_cfg.rollout_chunk_trades = max(
                cur_cfg.exploration_chunk_size,
                original_rollout_chunk,
            )
            meta_controller.explore_multiplier = 1.0
        if plan.explore_steps_multiplier != 1.0:
            meta_controller.explore_multiplier = max(
                0.4,
                min(1.0, float(plan.explore_steps_multiplier)),
            )
        if plan.intra_hard_pct_delta is not None and intra_state is not None:
            intra_state.hard_pct = max(
                cur_cfg.intra_initial_hard_pct,
                min(
                    cur_cfg.intra_max_hard_pct,
                    intra_state.hard_pct + plan.intra_hard_pct_delta,
                ),
            )
        if plan.mine:
            _mine_and_inject(aggressive=plan.mine_aggressive)
        if plan.expand_data:
            _maybe_expand_data()
        if plan.reward_tweak is not None:
            meta_controller.active_reward = plan.reward_tweak
        if plan.primary != RecoveryStrategy.HOLD:
            meta_message_suffix = (
                f" · meta: {plan.primary.value} ({plan.rationale})"
            )
        self_eval_suffix = meta_controller.format_self_eval_suffix()
        if self_eval_suffix:
            meta_message_suffix = self_eval_suffix
        if trigger:
            _log_meta_decision(plan, trigger)
        else:
            logger.info(
                "birth.meta.applied primary=%s rationale=%s",
                plan.primary.value,
                plan.rationale,
            )

    def _mine_and_inject(*, aggressive: bool = False) -> None:
        nonlocal patterns_mined, oracle_wins, active_stage_ticks
        if current_intra_sample_pool:
            pool = list(current_intra_sample_pool)
        elif len(active_train) > len(active_stage_ticks):
            pool = list(active_train)
        else:
            pool = list(active_stage_ticks)
        max_patterns, scan_stride = host._resolve_oracle_mining_params(
            cur_cfg,
            aggressive=aggressive,
        )
        mine_result = mine_winning_patterns(
            ticks=pool,
            stage=stage,
            runtime=host.runtime,
            workspace_root=host.workspace_root,
            max_patterns=max_patterns,
            scan_stride=scan_stride,
            max_hold_bars=cur_cfg.oracle_max_hold_bars,
        )
        patterns_mined += len(mine_result.patterns)
        oracle_wins += mine_result.wins
        meta_controller.record_inject(
            patterns=len(mine_result.patterns),
            oracle_wins=mine_result.wins,
        )
        for pattern in mine_result.patterns:
            host.buffer.add(pattern, priority=3.0 + min(10.0, abs(float(pattern.get("reward", 0.0)))))
        active_stage_ticks = filter_ticks_for_stage(stage, active_train) or list(active_train)
        _rebuild_intra_pools(active_stage_ticks)

    def _maybe_expand_data() -> bool:
        nonlocal active_train, active_stage_ticks, expansion_step, data_days_loaded, data_exhausted
        if data_exhausted:
            return False
        if expansion_ladder_at_max(
            expansion_step,
            list(cur_cfg.data_expansion_steps),
            has_train_ticks=bool(active_train),
        ):
            logger.info(
                "birth.data_expansion.skip_at_max step=%s train_ticks=%s",
                expansion_step,
                len(active_train),
            )
            data_exhausted = True
            return False
        expanded = expand_birth_data(
            market_data_service=host.market_data_service,
            runtime=host.runtime,
            current_step=expansion_step,
            expansion_steps=list(cur_cfg.data_expansion_steps),
            holdout_pct=host.birth_config.holdout_pct,
            enrich_news_fn=lambda rows: enrich_ticks_with_news(
                rows,
                workspace_root=host.workspace_root,
                primary=news_cfg.primary,
                enable_cache=news_cfg.enable_cache,
                cache_path=news_cfg.cache_path,
            ),
            synthetic_fallback_fn=(
                None
                if prefer_real
                else lambda n, p: host._generate_synthetic_ticks(n, start_price=p or start_price)
            ),
            start_price=start_price,
        )
        expansion_step = expanded.step_index
        data_days_loaded = expanded.days_back
        if expanded.exhausted and not expanded.train_ticks:
            data_exhausted = True
            return False
        active_train = list(expanded.train_ticks)
        active_stage_ticks = filter_ticks_for_stage(stage, active_train) or list(active_train)
        _rebuild_intra_pools(active_stage_ticks)
        host._real_data_pct = expanded.real_data_pct
        _write_progress(
            phase="data_expansion",
            message=(
                f"Data expansion: {data_days_loaded} dagen, "
                f"{len(active_train):,} train ticks · {stage.value}"
            ),
        )
        return True

    _write_progress(
        phase="curriculum_research",
        message=f"Curriculum {stage.value}: oracle scan start (doel {required:,} trades).",
    )
    if isinstance(stage_metrics, dict) and stage_metrics.get("pending_data_expand"):
        _maybe_expand_data()
        pending_cleared = dict(_stage_metrics_payload())
        pending_cleared.pop("pending_data_expand", None)
        host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=str(host.final_policy_path),
            phase="curriculum_learning",
            stage_metrics=pending_cleared,
        )
    _mine_and_inject()
    if len(host.buffer) >= 80:
        host.current_policy = host.ppo_trainer.update_from_buffer(
            buffer=host.buffer,
            timesteps=ppo_steps_per_update,
            birth_phase=True,
        )
        host.ppo_steps += ppo_steps_per_update

    def _would_certified_stage_stall(
        *,
        elapsed_stage_sec: float,
        failure_key: str,
        force: bool = False,
    ) -> dict[str, Any] | None:
        if allow_provisional or stage_trades < required:
            return None
        blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
            stage,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            hold_ratio=float(stage_hold_signals) / float(max(1, stage_total_signals)),
            required=required,
            constitution_violations=host._constitution_guard.violations,
            range_flat_ratio=float(stage_range_flat_bars)
            / float(max(1, stage_range_total_signals)),
            range_round_trips=stage_range_round_trips,
            range_total_signals=stage_range_total_signals,
            cfg=cur_cfg,
        )
        if not blocker_metric:
            return None
        if not force:
            stagnation_met = False
            if stage == CurriculumStage.STAGE1_TREND:
                stagnation_met = (
                    winrate_stagnation_count >= cur_cfg.stage1_winrate_stagnation_rollouts
                )
            elif stage == CurriculumStage.STAGE2_RANGE:
                stagnation_met = (
                    hold_stagnation_count >= cur_cfg.stage2_hold_stagnation_rollouts
                )
            elif stage == CurriculumStage.STAGE3_MIXED:
                stagnation_met = host._constitution_guard.violations > 0
            stall_wall = max(300, int(cur_cfg.certified_stage_stall_wall_sec))
            if not stagnation_met:
                return None
            if not (elapsed_stage_sec >= stall_wall or wall_budget_exhausted):
                return None
        return {
            "failure_key": failure_key,
            "blocker_metric": blocker_metric,
            "blocker_value": blocker_value,
            "blocker_reason": blocker_reason,
        }

    def _finalize_certified_stage_stall(
        pending: dict[str, Any],
        *,
        human_gate: bool = False,
    ) -> dict[str, Any]:
        failure_key = str(pending["failure_key"])
        blocker_metric = pending["blocker_metric"]
        blocker_value = pending["blocker_value"]
        blocker_reason = pending.get("blocker_reason")
        logger.info(
            "birth.terminal_stall reason=%s cumulative_trades=%s cap=%s "
            "adaptation_tier=%s retries=%s data_exhausted=%s buffer=%s human_gate=%s",
            blocker_reason or failure_key,
            host.cumulative_trades,
            effective_trade_budget_cap,
            adaptation_tier,
            retries_this_stage,
            data_exhausted,
            len(host.buffer),
            human_gate,
        )
        stall_reason = str(
            pending.get("terminal_stall_reason")
            or pending.get("blocker_reason")
            or failure_key
            or blocker_metric
            or "stage_stalled"
        )
        stage_winrate = float(stage_wins) / float(max(1, stage_trades))
        proxy_winrate = float(oos_proxy_history[-1]) if oos_proxy_history else None
        fitness_signal = max(stage_winrate, float(proxy_winrate or 0.0))
        recommended_recovery = str(
            pending.get("recommended_recovery_action")
            or organism_autonomy_state.last_recommended_action
            or ""
        )
        autonomy_decision = evaluate_terminal_stall(
            cfg=cur_cfg,
            autonomy_state=organism_autonomy_state,
            pending=pending,
            curriculum_stage=stage.value,
            stage_trades=stage_trades,
            required=required,
            constitution_violations=host._constitution_guard.violations,
            fitness_signal=fitness_signal,
            recommended_recovery_action=recommended_recovery,
            remediation_cycles_exhausted=stall_reason in {HUMAN_GATE_REASON, PHOENIX_CYCLE_REASON},
            plateau_exhausted=stall_reason == TERMINAL_STALL_REASON,
        )
        provisional_graduation = (
            autonomy_decision.dispatch == RecoveryDispatch.PROVISIONAL_GRADUATE
            or (
                cur_cfg.graduation_mode == "evolution_deferred"
                and (human_gate or cur_cfg.autonomous_recovery_enabled)
                and host._constitution_guard.violations == 0
                and stage_trades >= required
                and fitness_signal >= float(cur_cfg.provisional_oos_floor)
                and cur_cfg.allow_provisional_pass
            )
        )
        if autonomy_decision.stall_reason:
            stall_reason = autonomy_decision.stall_reason
        if host._constitution_guard.violations == 0 and stage_trades >= max(1, required // 2):
            try:
                from lumina_core.birth.dna_handoff import register_partial_birth_dna

                register_partial_birth_dna(
                    host.workspace_root,
                    curriculum_stage=stage.value,
                    stage_trades=stage_trades,
                    stage_winrate=stage_winrate,
                    oos_proxy_winrate=proxy_winrate,
                    policy_path=str(host.final_policy_path),
                    stall_reason=stall_reason,
                )
            except Exception as exc:
                logger.warning("birth.dna_handoff.partial_failed: %s", exc)
        if cur_cfg.autonomous_recovery_enabled:
            needs_attention = autonomy_decision.needs_attention and not provisional_graduation
            retryable = autonomy_decision.retryable or provisional_graduation
        else:
            needs_attention = (
                (bool(human_gate) or stall_reason in {TERMINAL_STALL_REASON, HUMAN_GATE_REASON})
                and not provisional_graduation
            )
            retryable = not needs_attention or provisional_graduation
        autonomy_extra: dict[str, Any] = {}
        if autonomy_decision.autonomy_metrics:
            autonomy_extra.update(autonomy_decision.autonomy_metrics)
        if autonomy_decision.recommended_action:
            autonomy_extra["recommended_recovery_action"] = autonomy_decision.recommended_action
            autonomy_extra["autonomous_recovery_pending"] = (
                cur_cfg.autonomous_recovery_enabled
                and autonomy_decision.dispatch
                in {RecoveryDispatch.PHOENIX_RESUME, RecoveryDispatch.CONTINUE_LOOP}
            )
        if autonomy_decision.message:
            autonomy_extra["autonomy_message"] = autonomy_decision.message
        write_birth_progress(
            host.workspace_root,
            stage="stage_stalled",
            phase="stage_stalled",
            message=(
                f"Stage {stage.value} stalled: "
                f"{blocker_reason or blocker_metric or failure_key}"
            ),
            progress_pct=stage_progress_pct,
            cumulative_trades=host.cumulative_trades,
            target_trades=effective_trade_budget_cap,
            birth_start_time=host.birth_start_time,
            curriculum_stage=stage.value,
            stages_passed=list(host._stages_passed),
            stage_blocker_metric=blocker_metric,
            stage_blocker_value=blocker_value,
            pass_reason=blocker_reason,
            retryable=retryable,
            needs_attention=needs_attention,
            provisional_graduation=provisional_graduation,
            graduation_tier="provisional" if provisional_graduation else "strict",
            oos_proxy_winrate=proxy_winrate,
            **host._budget_progress_fields(terminal_stall_reason=stall_reason),
            **host._constitution_progress_fields(),
            **autonomy_extra,
        )
        policy_hint = str(host.final_policy_path)
        if host.final_policy_path.is_file():
            policy_hint = str(host.final_policy_path)
        checkpoint_phase = "stage_stalled"
        if autonomy_decision.dispatch == RecoveryDispatch.PHOENIX_RESUME:
            checkpoint_phase = "phoenix_cycle"
        host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=policy_hint,
            phase=checkpoint_phase,
            stage_metrics=_stage_metrics_payload(),
        )
        if autonomy_decision.checkpoint_patch and cur_cfg.autonomous_recovery_enabled:
            try:
                from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload

                ckpt = read_checkpoint_payload(host.workspace_root) or {}
                patch = autonomy_decision.checkpoint_patch
                ckpt_metrics = dict(ckpt.get("stage_metrics") or {})
                ckpt_metrics.update(dict(patch.get("stage_metrics") or {}))
                ckpt.update({k: v for k, v in patch.items() if k != "stage_metrics"})
                ckpt["stage_metrics"] = ckpt_metrics
                write_checkpoint_payload(host.workspace_root, ckpt)
            except Exception as exc:
                logger.warning("birth.autonomy.checkpoint_patch_failed: %s", exc)
        if provisional_graduation:
            logger.info(
                "birth.provisional_graduation stage=%s fitness=%.2f%% proxy=%s",
                stage.value,
                fitness_signal * 100.0,
                proxy_winrate,
            )
        if needs_attention:
            try:
                from lumina_core.notifications.attention_events import birth_stage_stalled_event
                from lumina_core.notifications.attention_notifier import notify_attention

                winrate = float(stage_wins) / float(max(1, stage_trades))
                notify_attention(
                    birth_stage_stalled_event(
                        curriculum_stage=stage.value,
                        stall_reason=stall_reason,
                        blocker_detail=str(blocker_reason or blocker_metric or failure_key),
                        stage_trades=stage_trades,
                        winrate=winrate,
                        retryable=retryable,
                        phase2_active=remediation_state.active,
                    ),
                    workspace_root=host.workspace_root,
                )
            except Exception as exc:
                logger.warning("birth.attention_notify_failed: %s", exc)
        return {
            "status": "stage_stalled",
            "failure_reason": failure_key,
            "total_trades": host.cumulative_trades,
            "ppo_steps": host.ppo_steps,
            "training_mode": training_mode,
        }

    def _apply_phoenix_in_loop(*, stall_reason: str) -> bool:
        """Apply phoenix novelty inside rollout loop; True when loop should continue."""
        nonlocal attempt, active_train, active_stage_ticks, strong_recovery_mode, escalation_level
        if not cur_cfg.autonomous_recovery_enabled or not cur_cfg.phoenix_loop_enabled:
            return False
        from lumina_core.birth.phoenix_loop import (
            begin_phoenix_cycle,
            can_start_phoenix,
            select_phoenix_novelty,
        )

        if not can_start_phoenix(organism_autonomy_state.phoenix, cfg=cur_cfg):
            return False
        novelty = select_phoenix_novelty(organism_autonomy_state.phoenix, cfg=cur_cfg)
        begin_phoenix_cycle(
            organism_autonomy_state.phoenix,
            novelty=novelty,
            stall_reason=stall_reason,
        )
        organism_autonomy_state.autonomous_recovery_count += 1
        remediation_state.active = False
        remediation_state.remediation_step = 0
        remediation_state.remediation_rollouts_this_step = 0
        reset_plateau_for_new_cycle(
            plateau_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        detail = f"phoenix in-loop: {novelty.value}"
        if novelty in {PhoenixNoveltyAction.EXPAND_DATA, PhoenixNoveltyAction.WIDEN_HORIZON}:
            _maybe_expand_data()
            detail = f"{detail}; data expanded"
        elif novelty == PhoenixNoveltyAction.POLICY_SWARM:
            _start_policy_swarm()
            detail = f"{detail}; policy swarm started"
        elif novelty == PhoenixNoveltyAction.REWARD_SWEEP:
            remediation_state.meta_sweep_index += 1
            escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
            detail = f"{detail}; reward sweep #{remediation_state.meta_sweep_index}"
        elif novelty == PhoenixNoveltyAction.SOFT_GATE:
            detail = f"{detail}; soft gate floor {cur_cfg.stage1_winrate_pass_floor:.0%}"
        attempt = 0
        strong_recovery_mode = True
        _write_progress(phase="phoenix_cycle", message=detail)
        logger.warning("birth.phoenix.in_loop %s", detail)
        return True

    def _apply_stall_remediation_action(action: StallRemediationAction | None) -> str:
        nonlocal attempt, active_train, active_stage_ticks, strong_recovery_mode, escalation_level
        if action is None:
            return "no action"
        detail = ""
        if action == StallRemediationAction.EXPAND_AND_RETRY:
            _maybe_expand_data()
            detail = "expanded data window"
        elif action == StallRemediationAction.BUFFER_CURATE_ORACLE:
            removed = curate_buffer_bottom_half(host.buffer)
            strong_recovery_mode = True
            _mine_and_inject(aggressive=True)
            detail = f"curated {removed} low-reward buffer trajectories"
        elif action == StallRemediationAction.REGIME_DIVERSE_SLICE:
            filtered = filter_train_ticks_for_holdout_profile(
                active_train,
                holdout_ticks_ref,
            )
            if filtered:
                active_train = list(filtered)
                active_stage_ticks = filter_ticks_for_stage(stage, active_train)
            detail = "regime-diverse train slice applied"
        elif action == StallRemediationAction.META_SWEEP:
            remediation_state.meta_sweep_index += 1
            escalation_level = min(
                cur_cfg.max_escalation_level,
                escalation_level + 1,
            )
            detail = f"meta explore sweep #{remediation_state.meta_sweep_index}"
        elif action == StallRemediationAction.ORACLE_DISTILL:
            detail = _apply_oracle_distill()
        if remediation_state.remediation_cycle >= 2:
            host.current_policy = host._create_birth_policy(allow_load_existing=False)
            if intra_state is not None:
                intra_state.hard_pct = 0.0
                _rebuild_intra_pools(active_stage_ticks)
            strong_recovery_mode = True
            if detail:
                detail = f"{detail}; aggressive cycle {remediation_state.remediation_cycle}"
            else:
                detail = f"aggressive cycle {remediation_state.remediation_cycle}"
        return detail

    def _try_stall_remediation_on_terminal(pending: dict[str, Any]) -> bool:
        """Return True when remediation applied and loop should continue."""
        nonlocal attempt
        stall_reason = str(
            pending.get("terminal_stall_reason") or pending.get("blocker_reason") or ""
        )
        if stall_reason != TERMINAL_STALL_REASON:
            return False
        if not should_run_remediation_instead_of_human_gate(
            remediation_state,
            cfg=cur_cfg,
            plateau_exhausted=True,
        ):
            return False
        if can_start_remediation(remediation_state, cfg=cur_cfg):
            begin_remediation_cycle(
                remediation_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            try:
                from lumina_core.notifications.milestone_events import (
                    stall_remediation_cycle_event,
                )

                host._notify_milestone(
                    stall_remediation_cycle_event(
                        cycle=remediation_state.remediation_cycle,
                        max_cycles=int(cur_cfg.stall_remediation_max_cycles),
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_remediation_cycle_failed: %s", exc)
            plateau_state.active = False
            plateau_state.evolution_step = 0
            plateau_state.forced_recoveries_count = 0
        if is_remediation_exhausted(remediation_state, cfg=cur_cfg):
            if _trade_budget_remaining() > 0 and can_start_remediation(
                remediation_state, cfg=cur_cfg
            ):
                reset_plateau_for_new_cycle(
                    plateau_state,
                    stage_trades=stage_trades,
                    stage_wins=stage_wins,
                )
                remediation_state.active = False
                remediation_state.remediation_step = 0
                remediation_state.remediation_rollouts_this_step = 0
                return _try_plateau_evolution(failure_key=failure_key)
            if _trade_budget_remaining() > 0 and should_phoenix_reset(
                plateau_state,
                cfg=cur_cfg,
                winrate=float(stage_wins) / float(max(1, stage_trades)),
            ):
                _apply_phoenix_reset()
                reset_plateau_for_new_cycle(
                    plateau_state,
                    stage_trades=stage_trades,
                    stage_wins=stage_wins,
                )
                remediation_state.active = False
                return _try_plateau_evolution(failure_key=failure_key)
            if cur_cfg.autonomous_recovery_enabled and _apply_phoenix_in_loop(
                stall_reason=TERMINAL_STALL_REASON
            ):
                return True
            return False
        action = begin_remediation_step(
            remediation_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        detail = _apply_stall_remediation_action(action)
        record_remediation_outcome(
            remediation_state,
            action=action,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            detail=detail,
        )
        attempt = 0
        host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=str(host.final_policy_path),
            phase="stall_remediation",
            stage_metrics=_stage_metrics_payload(),
        )
        _write_progress(
            phase="stall_remediation",
            message=(
                f"Stall remediation step {remediation_state.remediation_step}/"
                f"{cur_cfg.stall_remediation_max_steps}: {detail}"
            ),
        )
        logger.info(
            "birth.stall_remediation.applied step=%s action=%s",
            remediation_state.remediation_step,
            action.value if action else "none",
        )
        return True

    def _maybe_advance_stall_remediation_in_loop() -> bool:
        """Advance remediation between rollouts; True if human gate finalize needed."""
        nonlocal attempt
        if not remediation_state.active:
            return False
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        if not should_advance_remediation_step(
            remediation_state,
            cfg=cur_cfg,
            current_winrate=current_winrate,
        ):
            return False
        if remediation_state.remediation_step >= int(cur_cfg.stall_remediation_max_steps):
            if _apply_phoenix_in_loop(stall_reason=HUMAN_GATE_REASON):
                return False
            return not cur_cfg.autonomous_recovery_enabled
        action = begin_remediation_step(
            remediation_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        detail = _apply_stall_remediation_action(action)
        record_remediation_outcome(
            remediation_state,
            action=action,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            detail=detail,
        )
        attempt = 0
        _write_progress(
            phase="stall_remediation",
            message=f"Stall remediation advanced: {detail}",
        )
        try:
            from lumina_core.notifications.milestone_events import (
                stall_remediation_step_event,
            )

            host._notify_milestone(
                stall_remediation_step_event(
                    cycle=remediation_state.remediation_cycle,
                    step=remediation_state.remediation_step,
                    max_steps=int(cur_cfg.stall_remediation_max_steps),
                    action=action.value if action else "",
                    detail=detail,
                    winrate=current_winrate,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_remediation_step_failed: %s", exc)
        return remediation_state.remediation_step >= int(cur_cfg.stall_remediation_max_steps)

    def _finalize_plateau_evolution_step(
        *,
        action: EvolutionAction,
        detail: str,
        failure_key: str,
        applied: bool = True,
        forced_advance: bool = False,
    ) -> None:
        nonlocal attempt, ppo_steps_at_plateau_evolution_step
        nonlocal evolution_last_action_applied, evolution_last_action_detail
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        evolution_last_action_applied = bool(applied or forced_advance)
        evolution_last_action_detail = str(detail or "")
        if not applied and not forced_advance:
            revert_evolution_step_on_noop(plateau_state)
            plateau_state.evolution_noop_count += 1
            logger.info(
                "birth.plateau.evolution_noop step=%s action=%s detail=%s noops=%s",
                plateau_state.evolution_step,
                action.value,
                detail,
                plateau_state.evolution_noop_count,
            )
            _write_progress(
                phase="plateau_evolution",
                message=(
                    f"Plateau evolution skipped (no-op): {detail} "
                    f"· noops {plateau_state.evolution_noop_count}/"
                    f"{cur_cfg.plateau_evolution_max_noops_per_step}"
                ),
            )
            return
        if not applied and forced_advance:
            detail = f"{detail} (forced advance after no-ops)"
        plateau_state.evolution_noop_count = 0
        ppo_steps_at_plateau_evolution_step = int(host.ppo_steps)
        record_evolution_outcome(
            plateau_state,
            action=action,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            detail=detail,
            applied=applied,
            rolling_winrate_500=_rolling_winrate_500(),
        )
        attempt = 0
        host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=str(host.final_policy_path),
            phase="plateau_evolution",
            stage_metrics=_stage_metrics_payload(),
        )
        forced_suffix = " (forced advance)" if forced_advance else ""
        _write_progress(
            phase="plateau_evolution",
            message=(
                f"Plateau evolution step {plateau_state.evolution_step}/"
                f"{cur_cfg.plateau_max_evolution_steps}: {detail}{forced_suffix}"
            ),
        )
        logger.info(
            "birth.plateau.evolution_applied step=%s action=%s detail=%s failure=%s forced=%s",
            plateau_state.evolution_step,
            action.value,
            detail,
            failure_key,
            forced_advance,
        )
        try:
            from lumina_core.notifications.milestone_events import plateau_evolution_step_event

            host._notify_milestone(
                plateau_evolution_step_event(
                    step=plateau_state.evolution_step,
                    max_steps=int(cur_cfg.plateau_max_evolution_steps),
                    action=action.value,
                    detail=f"{detail}{forced_suffix}",
                    winrate=current_winrate,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_evolution_notify_failed: %s", exc)
        if forced_advance:
            try:
                from lumina_core.notifications.milestone_events import (
                    plateau_evolution_forced_advance_event,
                )

                host._notify_milestone(
                    plateau_evolution_forced_advance_event(
                        step=plateau_state.evolution_step,
                        max_steps=int(cur_cfg.plateau_max_evolution_steps),
                        action=action.value,
                        winrate=current_winrate,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_forced_advance_notify_failed: %s", exc)

    def _plateau_pass_target() -> float:
        return learning_metric_target(
            stage,
            cfg=cur_cfg,
            pass_criteria=stage_pass_criteria,
        )

    def _try_evolution_exhausted_remediation(*, failure_key: str) -> bool:
        """Start stall remediation when evolution ladder is done (no phantom steps)."""
        if not plateau_state.active or allow_provisional:
            return False
        if not evolution_ladder_exhausted(plateau_state):
            return False
        pending = _plateau_terminal_pending(failure_key=failure_key)
        if pending is None:
            return False
        return _try_stall_remediation_on_terminal(pending)

    def _maybe_advance_plateau_evolution_in_loop() -> bool:
        """Advance plateau evolution between rollouts (mirrors remediation loop)."""
        nonlocal attempt
        if not plateau_state.active or allow_provisional:
            return False
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        pass_target = _plateau_pass_target()
        ppo_since = _ppo_steps_since_evolution_step()
        forced = should_force_advance_evolution_step(
            plateau_state,
            cfg=cur_cfg,
            current_winrate=current_winrate,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        )
        if not should_trigger_plateau_evolution_step(
            plateau_state,
            cfg=cur_cfg,
            current_winrate=current_winrate,
            allow_start=False,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        ):
            return False
        action = begin_evolution_step(
            plateau_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = _apply_plateau_evolution_action(action)
        _finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key="stage1_winrate",
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _resolve_terminal_stall(pending: dict[str, Any]) -> dict[str, Any] | None:
        """None => continue loop; dict => terminal stall result."""
        if _try_stall_remediation_on_terminal(pending):
            return None
        stall_reason = str(
            pending.get("terminal_stall_reason") or pending.get("blocker_reason") or ""
        )
        if cur_cfg.autonomous_recovery_enabled:
            return _finalize_certified_stage_stall(pending, human_gate=False)
        human_gate = stall_reason in {TERMINAL_STALL_REASON, HUMAN_GATE_REASON}
        return _finalize_certified_stage_stall(pending, human_gate=human_gate)

    def _best_policy_snapshot_path() -> Path:
        return host.workspace_root / "lumina_agents" / "ppo" / f"birth_best_{stage.value}.zip"

    def _meta_self_eval_phase_str() -> str:
        if cur_cfg.meta_controller_enabled and cur_cfg.meta_self_eval_enabled:
            return str(meta_controller.self_eval.phase.value)
        return ""

    def _maybe_save_best_policy(*, stage_trades: int, stage_wins: int) -> None:
        snapshot_path = _best_policy_snapshot_path()
        if maybe_update_best_winrate(
            plateau_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            policy_path=str(snapshot_path),
            cfg=cur_cfg,
        ):
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            save_fn = getattr(host.ppo_trainer, "save_final_birth_policy", None)
            if callable(save_fn):
                save_fn(str(snapshot_path))
                logger.info(
                    "birth.plateau.best_policy_saved path=%s winrate=%.2f%% trades=%s",
                    snapshot_path,
                    plateau_state.best_winrate * 100.0,
                    stage_trades,
                )
                try:
                    from lumina_core.notifications.milestone_events import (
                        best_policy_updated_event,
                    )

                    host._notify_milestone(
                        best_policy_updated_event(
                            winrate=plateau_state.best_winrate,
                            stage_trades=stage_trades,
                            policy_path=str(snapshot_path),
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_best_policy_failed: %s", exc)

    def _apply_swarm_variant_for_rollout() -> tuple[Any | None, float]:
        variant = swarm_state.current_variant()
        if variant is None:
            return None, 1.0
        if variant.policy_path:
            host.current_policy = host._create_birth_policy(
                allow_load_existing=True,
                policy_path=variant.policy_path,
            )
        return variant.reward, float(variant.explore_multiplier)

    def _start_policy_swarm() -> None:
        nonlocal swarm_state
        if (
            not cur_cfg.policy_swarm_enabled
            or allow_provisional
            or swarm_state.active
            or swarm_state.committed_variant_id
        ):
            return
        baseline = (
            meta_controller.active_reward
            if cur_cfg.meta_controller_enabled
            else host.birth_config.reward
        )
        variants = build_swarm_variants(baseline, cfg=cur_cfg)
        swarm_dir = host.workspace_root / "lumina_agents" / "ppo"
        swarm_dir.mkdir(parents=True, exist_ok=True)
        materialized = []
        save_fn = getattr(host.ppo_trainer, "save_final_birth_policy", None)
        for index, variant in enumerate(variants):
            host.current_policy = host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            path = swarm_dir / f"swarm_{stage.value}_{index}_{variant.variant_id}.zip"
            if callable(save_fn):
                save_fn(str(path))
            materialized.append(replace(variant, policy_path=str(path)))
        swarm_state = PolicySwarmState(active=True, variants=materialized)
        _apply_swarm_variant_for_rollout()
        logger.info("birth.policy_swarm.started variants=%s stage=%s", len(materialized), stage.value)

    def _maybe_record_and_advance_swarm(*, trades: int, wins: int, total_pnl: float) -> None:
        nonlocal swarm_state
        if not swarm_state.active:
            return
        variant = swarm_state.current_variant()
        if variant is None:
            swarm_state.active = False
            return
        record_swarm_rollout(
            swarm_state,
            variant_id=variant.variant_id,
            trades=trades,
            wins=wins,
            total_pnl=total_pnl,
        )
        swarm_state.rollouts_this_variant += 1
        target = swarm_rollout_target(cur_cfg)
        if swarm_state.rollouts_this_variant < target:
            return
        swarm_state.rollouts_this_variant = 0
        swarm_state.variant_index += 1
        if swarm_state.variant_index >= len(swarm_state.variants):
            winner = select_swarm_winner(swarm_state)
            if winner is not None:
                if winner.policy_path:
                    host.current_policy = host._create_birth_policy(
                        allow_load_existing=True,
                        policy_path=winner.policy_path,
                    )
                if cur_cfg.meta_controller_enabled:
                    meta_controller.active_reward = winner.reward
                swarm_state.committed_variant_id = winner.variant_id
            swarm_state.active = False
            logger.info(
                "birth.policy_swarm.committed winner=%s",
                swarm_state.committed_variant_id,
            )
            return
        _apply_swarm_variant_for_rollout()

    def _maybe_detect_plateau(*, stage_trades: int, stage_wins: int) -> None:
        nonlocal ppo_steps_at_plateau_evolution_step
        if plateau_state.active or allow_provisional:
            return
        ctx = PlateauEnterContext(
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            required=required,
            winrate_trend_slope=calculate_simple_slope(winrate_history),
            velocity_stall_attempts=low_velocity_attempts,
            meta_self_eval_phase=_meta_self_eval_phase_str(),
            pass_metric_target=pass_metric_target,
            plateau_quarantine_active=is_plateau_quarantine_blocking(
                quarantine_rollouts_remaining=int(
                    plateau_quarantine.get("plateau_quarantine_rollouts_remaining", 0) or 0
                ),
                quarantine_trades_at_resume=int(
                    plateau_quarantine.get("plateau_quarantine_trades_at_resume", 0) or 0
                ),
                stage_trades=stage_trades,
                quarantine_min_trades=int(
                    plateau_quarantine.get("plateau_quarantine_trades_remaining", 0)
                    or cur_cfg.plateau_quarantine_min_trades
                ),
            ),
            stage=stage,
        )
        if should_enter_plateau(ctx, cfg=cur_cfg):
            enter_plateau(
                plateau_state,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            ppo_steps_at_plateau_evolution_step = int(host.ppo_steps)
            sanitize_plateau_best_snapshot(
                plateau_state,
                cfg=cur_cfg,
                stage_trades=stage_trades,
                stage_wins=stage_wins,
            )
            wr = float(stage_wins) / float(max(1, stage_trades))
            try:
                from lumina_core.notifications.milestone_events import plateau_entered_event

                host._notify_milestone(
                    plateau_entered_event(
                        stage_trades=stage_trades,
                        winrate=wr,
                        pass_target=pass_metric_target,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_plateau_enter_failed: %s", exc)
            _start_policy_swarm()
            _try_plateau_evolution(failure_key="stage1_winrate")

    def _effective_max_rollouts() -> int:
        if not plateau_state.active and not remediation_state.active:
            if allow_provisional:
                return max_rollouts
            return max_rollouts
        if allow_provisional:
            return max_rollouts
        if remediation_state.active:
            return min(max_rollouts, cur_cfg.stall_remediation_rollouts_per_step)
        if (
            plateau_state.evolution_step > 0
            or plateau_state.active
        ):
            return min(max_rollouts, cur_cfg.plateau_evolution_rollouts_per_step)
        return max_rollouts

    def _plateau_terminal_pending(*, failure_key: str) -> dict[str, Any] | None:
        if not should_terminal_plateau_stall(
            plateau_state,
            stage_trades=stage_trades,
            required=required,
            cfg=cur_cfg,
            meta_self_eval_phase=_meta_self_eval_phase_str(),
            remediation_exhausted=_remediation_exhausted_now(),
            trade_budget_remaining=_trade_budget_remaining(),
        ):
            return None
        hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
        range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
        blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
            stage,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            hold_ratio=hold_ratio,
            required=required,
            constitution_violations=host._constitution_guard.violations,
            range_flat_ratio=range_flat_ratio,
            range_round_trips=stage_range_round_trips,
            range_total_signals=stage_range_total_signals,
            cfg=cur_cfg,
        )
        return {
            "failure_key": failure_key,
            "blocker_metric": blocker_metric,
            "blocker_value": blocker_value,
            "blocker_reason": TERMINAL_STALL_REASON,
            "terminal_stall_reason": TERMINAL_STALL_REASON,
        }

    def _try_plateau_evolution(*, failure_key: str) -> bool:
        nonlocal attempt, intra_state
        if not plateau_state.active or allow_provisional:
            return False
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        pass_target = _plateau_pass_target()
        ppo_since = _ppo_steps_since_evolution_step()
        forced = should_force_advance_evolution_step(
            plateau_state,
            cfg=cur_cfg,
            current_winrate=current_winrate,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        )
        if not should_trigger_plateau_evolution_step(
            plateau_state,
            cfg=cur_cfg,
            current_winrate=current_winrate,
            allow_start=True,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        ):
            return False
        action = begin_evolution_step(
            plateau_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = _apply_plateau_evolution_action(action)
        _finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key=failure_key,
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _should_terminal_stall_in_adaptive() -> bool:
        """True when plateau recovery must stop (budget-gated never-stop)."""
        if plateau_state.active and should_block_plateau_recovery(
            plateau_state,
            cfg=cur_cfg,
            remediation_exhausted=_remediation_exhausted_now(),
            trade_budget_remaining=_trade_budget_remaining(),
            stage_trades=stage_trades,
            required=required,
        ):
            return True
        if plateau_state.active:
            return False
        if (
            data_exhausted
            and len(host.buffer) < 80
            and adaptation_tier >= cur_cfg.max_adaptation_tiers - 1
        ):
            return True
        return False

    def _maybe_extend_trade_budget() -> bool:
        nonlocal effective_trade_budget_cap
        if host.cumulative_trades < effective_trade_budget_cap:
            return False
        old_cap = effective_trade_budget_cap
        effective_trade_budget_cap = int(effective_trade_budget_cap * 1.25) + 1000
        logger.info(
            "birth.budget_extended old_cap=%s new_cap=%s cumulative_trades=%s tier=%s",
            old_cap,
            effective_trade_budget_cap,
            host.cumulative_trades,
            adaptation_tier,
        )
        return True

    def _apply_adaptation_recovery(decision: AdaptationDecision, *, failure_key: str) -> bool:
        nonlocal escalation_level, retries_this_stage, attempt, adaptation_tier
        nonlocal winrate_stagnation_count, hold_stagnation_count, wall_budget_exhausted
        nonlocal stage_started_at, last_adaptation_stage_trades
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        if adaptation_tier >= cur_cfg.max_adaptation_tiers - 1:
            winrate_stagnation_count = 0
            hold_stagnation_count = 0
            wall_budget_exhausted = False
            escalation_level = min(cur_cfg.max_escalation_level, cur_cfg.max_escalation_level)
            cur_cfg.rollout_chunk_trades = max(
                cur_cfg.exploration_chunk_size,
                original_rollout_chunk,
            )
        else:
            escalation_level = min(
                cur_cfg.max_escalation_level,
                escalation_level + decision.escalation_increase,
            )
            cur_cfg.rollout_chunk_trades = decision.new_chunk_target
        adaptation_history.append(
            {
                "timestamp": time.time(),
                "reason": decision.reason,
                "chunk_target": cur_cfg.rollout_chunk_trades,
                "escalation": escalation_level,
                "tier": adaptation_tier,
                "winrate": current_winrate,
                "failure_key": failure_key,
            }
        )
        retries_this_stage += 1
        if retries_this_stage >= cur_cfg.max_stage_retries:
            if adaptation_tier + 1 < cur_cfg.max_adaptation_tiers:
                adaptation_tier += 1
                retries_this_stage = 0
                logger.info(
                    "birth.adaptation.tier_advanced tier=%s max=%s",
                    adaptation_tier,
                    cur_cfg.max_adaptation_tiers,
                )
            else:
                retries_this_stage = 0
                logger.info(
                    "birth.adaptation.persistent_recovery tier=%s failure=%s",
                    adaptation_tier,
                    failure_key,
                )
        attempt = 0
        winrate_stagnation_count = 0
        hold_stagnation_count = 0
        wall_budget_exhausted = False
        stage_started_at = time.time()
        last_adaptation_stage_trades = int(stage_trades)
        host._persist_checkpoint(
            training_mode=training_mode,
            curriculum_stage=stage.value,
            policy_path=str(host.final_policy_path),
            phase="curriculum_learning",
            stage_metrics=_stage_metrics_payload(),
        )
        logger.info(
            "birth.adaptation.applied reason=%s tier=%s new_chunk=%s escalation=%s",
            decision.reason,
            adaptation_tier,
            cur_cfg.rollout_chunk_trades,
            escalation_level,
        )
        _write_progress(
            phase="curriculum_learning",
            message=(
                f"Adaptive recovery tier {adaptation_tier + 1}/{cur_cfg.max_adaptation_tiers} "
                f"· retry {retries_this_stage}/{cur_cfg.max_stage_retries}: "
                f"{decision.log_message}"
            ),
        )
        return True

    def _resolve_meta_adaptation_decision(adapt_plan: MetaActionPlan) -> AdaptationDecision | None:
        decision = adapt_plan.adaptation
        if decision is not None and decision.should_retry:
            return decision
        if adaptation_tier == 0 and retries_this_stage == 0:
            return AdaptationDecision(
                should_retry=True,
                reason="stall_escalation",
                new_chunk_target=max(
                    cur_cfg.exploration_chunk_size,
                    min(cur_cfg.rollout_chunk_trades * 2, original_rollout_chunk),
                ),
                escalation_increase=1,
                log_message="Escalation ladder: forced recovery at stall boundary",
            )
        if adaptation_tier >= 1:
            return AdaptationDecision(
                should_retry=True,
                reason="persistent_recovery",
                new_chunk_target=max(
                    cur_cfg.exploration_chunk_size,
                    cur_cfg.rollout_chunk_trades,
                ),
                escalation_increase=0,
                log_message=(
                    f"Persistent recovery tier {adaptation_tier + 1}/"
                    f"{cur_cfg.max_adaptation_tiers}"
                ),
            )
        return None

    def _try_adaptive_stall_recovery(*, failure_key: str) -> bool:
        nonlocal escalation_level, retries_this_stage, attempt, adaptation_tier
        if not cur_cfg.adaptation_enabled or cur_cfg.wall_behavior != "adaptive":
            return False
        _maybe_extend_trade_budget()
        if _should_terminal_stall_in_adaptive():
            return False
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        if cur_cfg.meta_controller_enabled:
            snap, _ = _observe_snapshot()
            adapt_plan = meta_controller.decide_adaptation(
                snap,
                winrate=current_winrate,
                escalation_level=escalation_level,
                adaptation_tier=adaptation_tier,
                retries_this_stage=retries_this_stage,
                original_rollout_chunk=original_rollout_chunk,
                failure_key=failure_key,
            )
            decision = _resolve_meta_adaptation_decision(adapt_plan)
            if decision is None:
                return False
            if adapt_plan.mine:
                _mine_and_inject(aggressive=adapt_plan.mine_aggressive)
            if adapt_plan.expand_data:
                _maybe_expand_data()
        else:
            decision = get_adaptation_decision(
                stage_trades=stage_trades,
                required=required,
                winrate=current_winrate,
                winrate_history=winrate_history,
                escalation_level=escalation_level,
                cfg=cur_cfg,
            )
            if not decision.should_retry and adaptation_tier == 0 and retries_this_stage == 0:
                decision = AdaptationDecision(
                    should_retry=True,
                    reason="stall_escalation",
                    new_chunk_target=max(
                        cur_cfg.exploration_chunk_size,
                        min(cur_cfg.rollout_chunk_trades * 2, original_rollout_chunk),
                    ),
                    escalation_increase=1,
                    log_message="Escalation ladder: forced recovery at stall boundary",
                )
            if not decision.should_retry and adaptation_tier >= 1:
                decision = AdaptationDecision(
                    should_retry=True,
                    reason="persistent_recovery",
                    new_chunk_target=max(
                        cur_cfg.exploration_chunk_size,
                        cur_cfg.rollout_chunk_trades,
                    ),
                    escalation_increase=0,
                    log_message=(
                        f"Persistent recovery tier {adaptation_tier + 1}/"
                        f"{cur_cfg.max_adaptation_tiers}"
                    ),
                )
            if not decision.should_retry:
                return False
            if adaptation_tier >= 1:
                _mine_and_inject()
            if adaptation_tier >= 2 and cur_cfg.auto_expand_on_adaptation:
                _maybe_expand_data()
        return _apply_adaptation_recovery(decision, failure_key=failure_key)

    def _force_never_stop_recovery(*, failure_key: str) -> bool:
        """Keep curriculum loop alive when recovery tiers remain (ADR-0017)."""
        if not cur_cfg.adaptation_enabled or cur_cfg.wall_behavior != "adaptive":
            return False
        if _should_terminal_stall_in_adaptive():
            return False
        _maybe_extend_trade_budget()
        if plateau_state.active and not can_force_never_stop_recovery(
            plateau_state, cfg=cur_cfg
        ):
            return _try_plateau_evolution(failure_key=failure_key)
        if plateau_state.active:
            record_forced_recovery(plateau_state)
        logger.info(
            "birth.never_stop force_recovery failure=%s tier=%s retries=%s",
            failure_key,
            adaptation_tier,
            retries_this_stage,
        )
        decision = AdaptationDecision(
            should_retry=True,
            reason="never_stop_forced",
            new_chunk_target=max(
                cur_cfg.exploration_chunk_size,
                cur_cfg.rollout_chunk_trades,
            ),
            escalation_increase=1 if adaptation_tier == 0 else 0,
            log_message="Never-stop: forcing adaptive recovery instead of terminal stall",
        )
        if adaptation_tier >= 1:
            _mine_and_inject()
        if adaptation_tier >= 2 and cur_cfg.auto_expand_on_adaptation:
            _maybe_expand_data()
        return _apply_adaptation_recovery(decision, failure_key=failure_key)

    def _try_adaptation_stuck_escape(*, failure_key: str) -> bool:
        nonlocal adaptation_stuck_escapes, ppo_steps_at_plateau_evolution_step
        if not adaptation_stuck_escape_allowed(
            escapes_used=adaptation_stuck_escapes,
            max_escapes=cur_cfg.max_adaptation_stuck_escapes,
            trade_budget_remaining=_trade_budget_remaining(),
        ):
            return False
        adaptation_stuck_escapes += 1
        logger.warning(
            "birth.adaptation.stuck_escape attempt=%s/%s trades=%s tier=%s failure=%s",
            adaptation_stuck_escapes,
            cur_cfg.max_adaptation_stuck_escapes,
            stage_trades,
            adaptation_tier,
            failure_key,
        )
        _maybe_extend_trade_budget()
        if not plateau_state.active:
            enter_plateau(plateau_state, stage_trades=stage_trades, stage_wins=stage_wins)
            ppo_steps_at_plateau_evolution_step = int(host.ppo_steps)
        _apply_phoenix_reset()
        reset_plateau_for_new_cycle(
            plateau_state,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
        )
        _mine_and_inject(aggressive=True)
        if cur_cfg.auto_expand_on_adaptation and adaptation_tier >= 1:
            _maybe_expand_data()
        decision = AdaptationDecision(
            should_retry=True,
            reason="adaptation_stuck_escape",
            new_chunk_target=max(
                cur_cfg.exploration_chunk_size,
                min(original_rollout_chunk * 2, cur_cfg.rollout_chunk_trades * 2),
            ),
            escalation_increase=2,
            log_message=(
                f"Adaptation stuck escape {adaptation_stuck_escapes}/"
                f"{cur_cfg.max_adaptation_stuck_escapes}: phoenix reset + forced recovery"
            ),
        )
        return _apply_adaptation_recovery(decision, failure_key=failure_key)

    while True:
        if last_progress_write_at > 0 and time.time() - last_progress_write_at >= 60.0:
            _write_progress(
                phase="curriculum_learning",
                message=(
                    f"Curriculum {stage.value}: heartbeat · {stage_trades:,} / "
                    f"{required:,} trades · patronen {patterns_mined:,}"
                ),
            )

        if host._stop_requested():
            host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                policy_path=str(host.final_policy_path),
                phase="paused",
                stage_metrics=_stage_metrics_payload(),
            )
            return host._paused_result()

        elapsed_stage_sec = time.time() - stage_started_at
        failure_key = {
            CurriculumStage.STAGE1_TREND: "stage1_winrate",
            CurriculumStage.STAGE2_RANGE: "stage2_metric",
            CurriculumStage.STAGE3_MIXED: "stage3_constitution",
        }.get(stage, "stage_metrics")
        trades_beyond_hard_stop = should_trades_beyond_gate_hard_stop(
            stage_trades, required, cur_cfg
        )
        stall_pending = _would_certified_stage_stall(
            elapsed_stage_sec=elapsed_stage_sec,
            failure_key=failure_key,
            force=trades_beyond_hard_stop and stage_trades >= required,
        )
        if stall_pending is not None:
            if trades_beyond_hard_stop and stage_trades >= required and not plateau_state.active:
                _maybe_detect_plateau(stage_trades=stage_trades, stage_wins=stage_wins)
            adaptation_stuck = (
                trades_beyond_hard_stop
                and last_adaptation_stage_trades == stage_trades
            )
            if adaptation_stuck:
                logger.warning(
                    "birth.adaptation.loop_blocked trades=%s tier=%s failure=%s",
                    stage_trades,
                    adaptation_tier,
                    failure_key,
                )
                if _try_adaptation_stuck_escape(failure_key=failure_key):
                    continue
            elif _try_adaptive_stall_recovery(failure_key=failure_key):
                continue
            current_wr = float(stage_wins) / float(max(1, stage_trades))
            if plateau_state.active and should_trigger_plateau_evolution_step(
                plateau_state,
                cfg=cur_cfg,
                current_winrate=current_wr,
                allow_start=False,
                pass_target=_plateau_pass_target(),
            ) and _try_plateau_evolution(failure_key=failure_key):
                continue
            if not adaptation_stuck and _force_never_stop_recovery(failure_key=failure_key):
                continue
            if plateau_state.active and _try_plateau_evolution(failure_key=failure_key):
                continue
            if plateau_state.active and evolution_ladder_exhausted(plateau_state):
                if _try_evolution_exhausted_remediation(failure_key=failure_key):
                    continue
            plateau_terminal = _plateau_terminal_pending(failure_key=failure_key)
            if plateau_terminal is not None:
                cur_cfg.rollout_chunk_trades = original_rollout_chunk
                stall_result = _resolve_terminal_stall(plateau_terminal)
                if stall_result is None:
                    continue
                return stall_result
            cur_cfg.rollout_chunk_trades = original_rollout_chunk
            stall_result = _resolve_terminal_stall(stall_pending)
            if stall_result is None:
                continue
            return stall_result

        if elapsed_stage_sec >= max(300, int(cur_cfg.max_stage_wall_sec)):
            if (
                len(host.buffer) >= 256
                and host._constitution_guard.violations == 0
                and (patterns_mined >= 100 or stage_trades >= 1)
            ):
                if allow_provisional:
                    gen0_provisional = True
                    logger.info(
                        "birth.stage.wall_budget_provisional",
                        extra={"event_data": {"stage": stage.value, "elapsed_sec": elapsed_stage_sec}},
                    )
                elif not wall_budget_exhausted:
                    wall_budget_exhausted = True
                    escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
                    logger.info(
                        "birth.stage.wall_budget_exhausted",
                        extra={"event_data": {"stage": stage.value, "elapsed_sec": elapsed_stage_sec}},
                    )

        stage_val_sharpe = 0.0
        stage_val_max_dd = 100.0
        if stage_val_pnl:
            stage_val_sharpe, stage_val_max_dd = risk_metrics_from_pnl(stage_val_pnl)
        stage_result = evaluate_stage_pass(
            stage,
            trades=stage_trades,
            wins=stage_wins,
            hold_signals=stage_hold_signals,
            total_signals=stage_total_signals,
            range_hold_signals=stage_range_hold_signals,
            range_total_signals=stage_range_total_signals,
            range_flat_bars=stage_range_flat_bars,
            range_round_trips=stage_range_round_trips,
            constitution_violations=host._constitution_guard.violations,
            target_trades=target,
            cfg=cur_cfg,
            provisional=gen0_provisional,
            allow_provisional=allow_provisional,
            oracle_patterns=patterns_mined,
            buffer_size=len(host.buffer),
            stage_val_sharpe=stage_val_sharpe,
            stage_val_max_drawdown_pct=stage_val_max_dd,
        )
        if stage_result.passed:
            required = stage_pass_trades(stage, cur_cfg)
            pass_winrate = float(stage_wins) / float(max(1, stage_trades))
            logger.info(
                "birth.stage.passed stage=%s trades=%s wins=%s required=%s "
                "winrate=%.2f%% provisional=%s reason=%s",
                stage.value,
                stage_trades,
                stage_wins,
                required,
                pass_winrate * 100.0,
                bool(stage_result.provisional),
                stage_result.message,
                extra={
                    "event_data": {
                        "stage": stage.value,
                        "trades": stage_trades,
                        "wins": stage_wins,
                        "required": required,
                        "winrate": round(pass_winrate, 4),
                        "patterns_mined": patterns_mined,
                        "attempts": attempt,
                        "pass_reason": stage_result.message,
                        "provisional": stage_result.provisional,
                    }
                },
            )
            host._pending_stage_pass_receipt = receipt_from_stage_result(
                stage,
                stage_result,
                cfg=cur_cfg,
            )
            return None

        if stage_trades == last_stage_trades:
            stagnation_count += 1
        else:
            stagnation_count = 0
            last_stage_trades = stage_trades

        if stagnation_count >= cur_cfg.stagnation_rollouts_before_expand:
            _mine_and_inject()
            if not _maybe_expand_data():
                if allow_provisional and (
                    stage_trades > 0 or patterns_mined > 0 or len(host.buffer) >= 256
                ):
                    gen0_provisional = True
                    continue
                if data_exhausted:
                    write_birth_progress(
                        host.workspace_root,
                        stage="history_unavailable",
                        phase="data_expansion_exhausted",
                        message="Birth research: geen extra data/patronen beschikbaar.",
                        progress_pct=stage_progress_pct,
                        cumulative_trades=host.cumulative_trades,
                        target_trades=trade_budget_cap,
                        birth_start_time=host.birth_start_time,
                        curriculum_stage=stage.value,
                        retryable=True,
                    )
                    return {
                        "status": "history_unavailable",
                        "total_trades": host.cumulative_trades,
                        "ppo_steps": host.ppo_steps,
                        "training_mode": "certified",
                    }
            stagnation_count = 0
            if len(host.buffer) >= 80:
                host.current_policy = host.ppo_trainer.update_from_buffer(
                    buffer=host.buffer,
                    timesteps=ppo_steps_per_update,
                    birth_phase=True,
                )
                host.ppo_steps += ppo_steps_per_update

        if attempt >= _effective_max_rollouts():
            if allow_provisional and (
                should_gen0_soft_pass(
                    stage_trades=stage_trades,
                    buffer_size=len(host.buffer),
                    attempt=attempt,
                    cfg=cur_cfg,
                )
                or patterns_mined >= 100
            ):
                gen0_provisional = True
            elif allow_provisional and (stage_trades > 0 or patterns_mined > 0):
                gen0_provisional = True
            elif not allow_provisional and stage_trades >= required:
                force_failure_key = {
                    CurriculumStage.STAGE1_TREND: "stage1_winrate",
                    CurriculumStage.STAGE2_RANGE: "stage2_metric",
                    CurriculumStage.STAGE3_MIXED: "stage3_constitution",
                }.get(stage, "stage_metrics")
                stall_pending = _would_certified_stage_stall(
                    elapsed_stage_sec=time.time() - stage_started_at,
                    failure_key=force_failure_key,
                    force=True,
                )
                if stall_pending is not None:
                    if _try_adaptive_stall_recovery(failure_key=force_failure_key):
                        attempt = 0
                        continue
                    force_wr = float(stage_wins) / float(max(1, stage_trades))
                    if plateau_state.active and should_trigger_plateau_evolution_step(
                        plateau_state,
                        cfg=cur_cfg,
                        current_winrate=force_wr,
                        allow_start=False,
                        pass_target=_plateau_pass_target(),
                    ) and _try_plateau_evolution(failure_key=force_failure_key):
                        attempt = 0
                        continue
                    if _force_never_stop_recovery(failure_key=force_failure_key):
                        attempt = 0
                        continue
                    if plateau_state.active and _try_plateau_evolution(
                        failure_key=force_failure_key
                    ):
                        attempt = 0
                        continue
                    plateau_terminal = _plateau_terminal_pending(
                        failure_key=force_failure_key
                    )
                    if plateau_terminal is not None:
                        cur_cfg.rollout_chunk_trades = original_rollout_chunk
                        stall_result = _resolve_terminal_stall(plateau_terminal)
                        if stall_result is None:
                            attempt = 0
                            continue
                        return stall_result
                    cur_cfg.rollout_chunk_trades = original_rollout_chunk
                    stall_result = _resolve_terminal_stall(stall_pending)
                    if stall_result is None:
                        attempt = 0
                        continue
                    return stall_result
            else:
                if _maybe_expand_data():
                    attempt = 0
                    continue
                write_birth_progress(
                    host.workspace_root,
                    stage="history_unavailable",
                    phase="data_expansion_exhausted",
                    message="Birth research: max rollouts bereikt zonder patronen.",
                    progress_pct=stage_progress_pct,
                    cumulative_trades=host.cumulative_trades,
                    target_trades=trade_budget_cap,
                    birth_start_time=host.birth_start_time,
                    retryable=True,
                )
                return {
                    "status": "history_unavailable",
                    "total_trades": host.cumulative_trades,
                    "ppo_steps": host.ppo_steps,
                    "training_mode": "certified",
                }
            attempt = 0
            continue

        if stage_trades >= required:
            chunk_target = cur_cfg.rollout_chunk_trades
        else:
            remaining = max(1, required - stage_trades)
            chunk_target = min(remaining, cur_cfg.rollout_chunk_trades)
        active_ticks = host._stage_tick_pool(
            stage=stage,
            stage_ticks=active_stage_ticks,
            train_ticks=active_train,
            escalation_level=escalation_level,
            attempt=attempt,
            chunk_target=chunk_target,
            cur_cfg=cur_cfg,
            intra_state=intra_state,
            easy_pool=intra_easy_pool,
            hard_pool=intra_hard_pool,
            intra_s2_state=intra_s2_state,
            s2_easy_pool=intra_s2_easy_pool,
            s2_hard_pool=intra_s2_hard_pool,
        )
        current_intra_sample_pool = list(active_ticks)

        chunk_trades_snapshot = 0

        def _rollout_progress(snapshot: dict[str, Any]) -> None:
            nonlocal chunk_trades_snapshot
            chunk_trades_snapshot = int(snapshot.get("rollout_trades", 0) or 0)
            explore_suffix = " (exploratie actief)" if snapshot.get("exploration_active") else ""
            _write_progress(
                phase="curriculum_learning",
                message=(
                    f"Curriculum {stage.value}: {stage_trades + chunk_trades_snapshot:,} / "
                    f"{required:,} trades · poging {attempt + 1} · L{escalation_level} · "
                    f"patronen {patterns_mined:,}{explore_suffix}"
                ),
                chunk_trades=chunk_trades_snapshot,
                rollout_steps=int(snapshot.get("rollout_steps", 0) or 0),
                exploration_active=bool(snapshot.get("exploration_active")),
                hold_ratio=float(snapshot.get("hold_ratio", 0.0) or 0.0),
            )

        base_explore_steps = cur_cfg.exploration_steps * (1 + escalation_level)
        reward_override = None
        if cur_cfg.meta_controller_enabled:
            pre_snap, _ = _observe_snapshot()
            if cur_cfg.meta_self_eval_enabled:
                meta_controller.maybe_start_self_eval(
                    pre_snap,
                    strong_recovery_attempts=strong_recovery_attempts,
                    attempt=attempt + 1,
                )
            if (
                cur_cfg.meta_self_eval_enabled
                and meta_controller.is_self_eval_active()
            ):
                if meta_controller.self_eval.phase == SelfEvalPhase.PROBING:
                    pre_plan = meta_controller.decide_probe_rollout(pre_snap)
                elif meta_controller.self_eval.phase == SelfEvalPhase.COMMITTED:
                    pre_plan = meta_controller.decide_committed_rollout(pre_snap)
                else:
                    pre_plan = MetaActionPlan(
                        primary=RecoveryStrategy.HOLD,
                        rationale="self_eval_exhausted",
                        snapshot=pre_snap,
                        self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
                    )
            else:
                pre_plan = meta_controller.decide_review(
                    pre_snap,
                    trigger="pre_rollout",
                    base_explore_steps=base_explore_steps,
                    wall_budget_exhausted=wall_budget_exhausted,
                    winrate_stagnation_count=winrate_stagnation_count,
                    hold_stagnation_count=hold_stagnation_count,
                )
            current_wr = float(stage_wins) / float(max(1, stage_trades))
            current_hold = (
                float(stage_hold_signals) / float(max(1, stage_total_signals))
                if stage_total_signals
                else 0.0
            )
            if detect_hold_trap(
                hold_ratio=current_hold,
                winrate=current_wr,
                pass_metric_target=pass_metric_target,
                velocity_stall=low_velocity_attempts
                >= int(cur_cfg.velocity_stall_attempt_threshold),
                cfg=cur_cfg,
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_BOOST,
                    explore_steps=max(
                        base_explore_steps,
                        int(cur_cfg.exploration_steps) * 4,
                    ),
                    escalation_delta=1,
                    rationale="hold_trap_forced_explore",
                    snapshot=pre_snap,
                )
                if not hold_trap_milestone_sent:
                    hold_trap_milestone_sent = True
                    try:
                        from lumina_core.notifications.milestone_events import (
                            hold_trap_detected_event,
                        )

                        host._notify_milestone(
                            hold_trap_detected_event(
                                hold_ratio=current_hold,
                                winrate=current_wr,
                            )
                        )
                    except Exception as exc:
                        logger.debug("birth.milestone_hold_trap_failed: %s", exc)
            elif (
                stage == CurriculumStage.STAGE3_MIXED
                and stage_trades < required
                and current_hold > 0.75
                and low_velocity_attempts
                >= max(8, int(cur_cfg.velocity_stall_attempt_threshold) // 2)
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_BOOST,
                    explore_steps=max(
                        base_explore_steps,
                        int(cur_cfg.exploration_steps) * 4,
                    ),
                    escalation_delta=1,
                    rationale="stage3_hold_recovery_explore",
                    snapshot=pre_snap,
                )
                logger.info(
                    "birth.stage3_hold_recovery stage_trades=%s/%s hold_ratio=%.1f%% "
                    "velocity_stall_attempts=%s",
                    stage_trades,
                    required,
                    current_hold * 100.0,
                    low_velocity_attempts,
                )
            elif (
                stage == CurriculumStage.STAGE2_RANGE
                and detect_over_trading_trap(
                    range_flat_ratio=float(stage_range_flat_bars)
                    / float(max(1, stage_range_total_signals)),
                    range_round_trips=stage_range_round_trips,
                    required=required,
                    velocity_stall=low_velocity_attempts
                    >= int(cur_cfg.velocity_stall_attempt_threshold),
                    cfg=cur_cfg,
                )
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_REDUCE,
                    explore_steps=max(
                        200,
                        int(cur_cfg.exploration_steps * cur_cfg.strong_recovery_explore_fraction),
                    ),
                    escalation_delta=1,
                    rationale="over_trading_range_patience",
                    snapshot=pre_snap,
                )
                if not over_trading_milestone_sent:
                    over_trading_milestone_sent = True
                    logger.info(
                        "birth.over_trading_trap_detected stage=%s flat_ratio=%.2f%% round_trips=%s",
                        stage.value,
                        100.0
                        * float(stage_range_flat_bars)
                        / float(max(1, stage_range_total_signals)),
                        stage_range_round_trips,
                    )
            elif (
                pre_plan.primary == RecoveryStrategy.HOLD
                and _meta_self_eval_phase_str() == "exhausted"
                and plateau_state.active
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_BOOST,
                    explore_steps=max(
                        base_explore_steps,
                        int(cur_cfg.exploration_steps) * 4,
                    ),
                    escalation_delta=1,
                    rationale="meta_exhausted_forced_explore",
                    snapshot=pre_snap,
                )
            if pre_plan.mine:
                _mine_and_inject(aggressive=pre_plan.mine_aggressive)
            if pre_plan.escalation_delta > 0:
                escalation_level = min(
                    cur_cfg.max_escalation_level,
                    escalation_level + pre_plan.escalation_delta,
                )
            elif pre_plan.escalation_delta < 0:
                escalation_level = max(0, escalation_level + pre_plan.escalation_delta)
            explore_steps = meta_controller.apply_explore_multiplier(
                pre_plan.explore_steps or base_explore_steps,
            )
            meta_last_plan = pre_plan
            if pre_plan.primary != RecoveryStrategy.HOLD or pre_plan.mine or pre_plan.expand_data:
                _log_meta_decision(pre_plan, trigger="pre_rollout")
            if meta_controller.reward_tweak_active:
                reward_override = meta_controller.active_reward
        else:
            explore_steps = base_explore_steps
            if not strong_recovery_mode:
                if (
                    stage == CurriculumStage.STAGE2_RANGE
                    and stage_trades >= required
                    and hold_stagnation_count >= cur_cfg.stage2_hold_stagnation_rollouts
                ):
                    explore_steps = max(explore_steps, cur_cfg.exploration_steps * 4)
                    escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
                if (
                    stage == CurriculumStage.STAGE1_TREND
                    and stage_trades >= required
                    and winrate_stagnation_count >= cur_cfg.stage1_winrate_stagnation_rollouts
                ):
                    explore_steps = max(explore_steps, cur_cfg.exploration_steps * 4)
                    escalation_level = min(cur_cfg.max_escalation_level, escalation_level + 1)
                    _mine_and_inject()
                if wall_budget_exhausted:
                    explore_steps = max(explore_steps, cur_cfg.exploration_steps * 4)
            else:
                if (
                    strong_recovery_attempts > 0
                    and strong_recovery_attempts
                    % cur_cfg.strong_recovery_expand_every_attempts
                    == 0
                ):
                    _maybe_expand_data()
                    _mine_and_inject(aggressive=True)
                explore_steps = max(
                    200,
                    int(
                        cur_cfg.exploration_steps
                        * cur_cfg.strong_recovery_explore_fraction
                    ),
                )
        pre_rollout_hold = (
            float(stage_hold_signals) / float(max(1, stage_total_signals))
            if stage_total_signals
            else 0.0
        )
        pre_rollout_flat = (
            float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
            if stage_range_total_signals
            else 0.0
        )
        if swarm_state.active:
            swarm_reward, swarm_explore_mult = _apply_swarm_variant_for_rollout()
            if swarm_reward is not None:
                reward_override = swarm_reward
            explore_steps = max(200, int(explore_steps * swarm_explore_mult))
        plateau_recovery = plateau_state.active or remediation_state.active
        hold_cap: float | None = None
        position_flat_cap: float | None = None
        range_patience_active = stage == CurriculumStage.STAGE2_RANGE
        velocity_stalled = low_velocity_attempts >= int(cur_cfg.velocity_stall_attempt_threshold)
        if plateau_recovery or detect_hold_trap(
            hold_ratio=pre_rollout_hold,
            winrate=float(stage_wins) / float(max(1, stage_trades)),
            pass_metric_target=pass_metric_target,
            velocity_stall=velocity_stalled,
            cfg=cur_cfg,
        ):
            hold_cap = float(cur_cfg.hold_trap_recovery_hold_cap)
        if stage == CurriculumStage.STAGE2_RANGE and detect_over_trading_trap(
            range_flat_ratio=pre_rollout_flat,
            range_round_trips=stage_range_round_trips,
            required=required,
            velocity_stall=velocity_stalled,
            cfg=cur_cfg,
        ):
            position_flat_cap = float(cur_cfg.over_trading_recovery_flat_target)
            range_patience_active = True
        if (
            plateau_state.best_policy_path
            and is_valid_best_policy_snapshot(plateau_state, cfg=cur_cfg)
            and attempt - last_policy_rollback_attempt
            >= int(cur_cfg.policy_rollback_cooldown_rollouts)
        ):
            live_wr = float(stage_wins) / float(max(1, stage_trades))
            rollback_wr_gap = live_wr + float(cur_cfg.policy_rollback_winrate_gap) < (
                plateau_state.best_winrate
            )
            should_rollback = rollback_wr_gap and (
                strong_recovery_mode
                or (
                    stage == CurriculumStage.STAGE3_MIXED
                    and stage_trades < required
                    and pre_rollout_hold > 0.75
                )
            )
            if should_rollback:
                detail, applied = _apply_plateau_evolution_action(
                    EvolutionAction.POLICY_ROLLBACK
                )
                if applied:
                    last_policy_rollback_attempt = attempt
                logger.info(
                    "birth.policy_rollback_auto_applied detail=%s applied=%s live_wr=%.2f%% best=%.2f%% "
                    "stage=%s hold_ratio=%.1f%%",
                    detail,
                    applied,
                    live_wr * 100.0,
                    plateau_state.best_winrate * 100.0,
                    stage.value,
                    pre_rollout_hold * 100.0,
                )
        rollout_started_at = time.time()
        rollout = run_policy_rollout(
            runtime=host.runtime,
            data=active_ticks,
            policy=host.current_policy,
            target_trades=chunk_target,
            workspace_root=host.workspace_root,
            constitution_guard=host._constitution_guard,
            rollout_step_budget=chunk_budget,
            stall_probe_steps=max(200, cur_cfg.stall_probe_steps // (1 + escalation_level)),
            exploration_steps=explore_steps,
            escalation_level=escalation_level,
            hold_cap_ratio=hold_cap,
            position_flat_cap=position_flat_cap,
            range_patience_active=range_patience_active,
            plateau_active=plateau_recovery,
            on_progress=_rollout_progress,
            reward_override=reward_override,
        )
        rollout_wall_clock_total_sec += max(0.0, time.time() - rollout_started_at)
        rollout_wall_clock_samples += 1
        sim_ticks_processed_cumulative += int(getattr(rollout, "rollout_steps", 0) or 0)

        stage_trades += rollout.trades
        stage_wins += rollout.wins
        stage_hold_signals += rollout.hold_signals
        stage_total_signals += rollout.total_signals
        stage_range_hold_signals += rollout.range_hold_signals
        stage_range_total_signals += rollout.range_total_signals
        stage_range_flat_bars += rollout.range_flat_bars
        stage_range_round_trips += rollout.range_round_trips
        host.cumulative_trades += rollout.trades
        _maybe_run_oos_proxy()
        _maybe_record_and_advance_swarm(
            trades=rollout.trades,
            wins=rollout.wins,
            total_pnl=float(rollout.total_pnl),
        )
        if is_runway_stage(stage):
            stage_val_pnl.extend(rollout.pnl_series)

        if intra_state is not None and rollout.easy_trades > 0:
            update_stage1_intra_state(
                intra_state,
                chunk_easy_trades=rollout.easy_trades,
                chunk_easy_wins=rollout.easy_wins,
                cfg=cur_cfg,
            )
        if intra_s2_state is not None and rollout.range_total_signals > 0:
            easy_share = 0.0
            if current_intra_sample_pool:
                easy_count = sum(
                    1
                    for t in current_intra_sample_pool
                    if str(t.get("_intra_difficulty", "")).lower() == "easy"
                )
                easy_share = float(easy_count) / float(max(1, len(current_intra_sample_pool)))
            if easy_share > 0.0:
                update_stage2_intra_state(
                    intra_s2_state,
                    chunk_flat_bars=int(rollout.range_flat_bars * easy_share),
                    chunk_range_signals=max(
                        1, int(rollout.range_total_signals * easy_share)
                    ),
                    cfg=cur_cfg,
                )

        current_hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
        range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
        if stage == CurriculumStage.STAGE2_RANGE and rollout.range_total_signals > 0:
            rollout_flat = float(rollout.range_flat_bars) / float(max(1, rollout.range_total_signals))
            flat_delta = range_flat_ratio - last_range_flat_ratio
            logger.info(
                "birth.stage2.rollout_metrics rollout_flat=%.4f stage_flat=%.4f delta=%+.4f "
                "round_trips=%s trades=%s",
                rollout_flat,
                range_flat_ratio,
                flat_delta,
                rollout.range_round_trips,
                rollout.trades,
            )
            last_range_flat_ratio = range_flat_ratio
        if rollout.trades > 0:
            wins_at_trade_milestones[stage_trades] = stage_wins
        metric_band = range_flat_ratio if stage_range_total_signals >= 50 else current_hold_ratio
        current_winrate = float(stage_wins) / float(max(1, stage_trades))
        if rollout.trades > 0:
            winrate_history.append(current_winrate)
            if len(winrate_history) > cur_cfg.winrate_trend_window:
                winrate_history.pop(0)
            mean_reward = float(rollout.total_pnl) / float(max(1, rollout.trades))
            reward_history.append(mean_reward)
            if len(reward_history) > cur_cfg.reward_trend_window:
                reward_history.pop(0)

        snap: Any | None = None
        stall_result: StallDetectionResult | None = None
        if cur_cfg.meta_controller_enabled:
            meta_controller.rollouts_since_review += 1
            snap, stall_result = _observe_snapshot()
            if rollout.trades > 0:
                low_velocity_attempts = stall_result.low_velocity_attempts
            self_eval_skip_review = (
                cur_cfg.meta_self_eval_enabled
                and meta_controller.is_self_eval_active()
                and meta_controller.self_eval.phase
                in (SelfEvalPhase.PROBING, SelfEvalPhase.COMMITTED)
            )
            if self_eval_skip_review:
                complete_plan = meta_controller.on_probe_rollout_complete(
                    snap,
                    attempt=attempt + 1,
                )
                if complete_plan is not None:
                    _apply_meta_plan(complete_plan, trigger="self_eval")
                    if complete_plan.suggest_provisional_pass:
                        prov = meta_controller.evaluate_provisional_fallback(
                            snap,
                            allow_provisional=allow_provisional,
                            strong_recovery_attempts=strong_recovery_attempts,
                            stage_trades=stage_trades,
                            required=required,
                            attempt=attempt,
                            patterns_mined=patterns_mined,
                            buffer_size=len(host.buffer),
                            constitution_violations=host._constitution_guard.violations,
                        )
                        provisional_pass_considered = True
                        _log_provisional_pass_outcome(
                            source="self_eval_probe_complete",
                            should_grant=prov.should_grant,
                            blocked_reason=prov.blocked_reason,
                            safeguards=prov.safeguards,
                        )
                        if prov.should_grant:
                            gen0_provisional = True
                elif meta_controller.self_eval.phase == SelfEvalPhase.COMMITTED:
                    committed_plan = meta_controller.decide_committed_rollout(snap)
                    _apply_meta_plan(committed_plan, trigger="self_eval_committed")
                meta_message_suffix = meta_controller.format_self_eval_suffix()
            else:
                next_attempt = attempt + 1
                should_review = (
                    (
                        next_attempt > 0
                        and next_attempt % cur_cfg.meta_review_interval_rollouts == 0
                    )
                    or stall_result.is_stalled
                    or rollout.stalled
                    or snap.learning_health == LearningHealth.DECLINING
                )
                exhausted_self_eval = (
                    cur_cfg.meta_self_eval_enabled
                    and meta_controller.self_eval.phase == SelfEvalPhase.EXHAUSTED
                )
                if exhausted_self_eval:
                    should_review = True
                review_plan: MetaActionPlan | None = None
                review_trigger = "periodic"
                if should_review:
                    if exhausted_self_eval:
                        review_plan = MetaActionPlan(
                            primary=RecoveryStrategy.HOLD,
                            suggest_provisional_pass=True,
                            rationale="self_eval_exhausted",
                            snapshot=snap,
                            self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
                        )
                        review_trigger = "self_eval_exhausted"
                    else:
                        review_trigger = (
                            "stall"
                            if stall_result.is_stalled or rollout.stalled
                            else "periodic"
                        )
                        review_plan = meta_controller.decide_review(
                            snap,
                            trigger=review_trigger,
                            base_explore_steps=cur_cfg.exploration_steps
                            * (1 + escalation_level),
                            wall_budget_exhausted=wall_budget_exhausted,
                            winrate_stagnation_count=winrate_stagnation_count,
                            hold_stagnation_count=hold_stagnation_count,
                        )
                    _apply_meta_plan(review_plan, trigger=review_trigger)
                    if review_plan.suggest_provisional_pass:
                        prov = meta_controller.evaluate_provisional_fallback(
                            snap,
                            allow_provisional=allow_provisional,
                            strong_recovery_attempts=strong_recovery_attempts,
                            stage_trades=stage_trades,
                            required=required,
                            attempt=attempt,
                            patterns_mined=patterns_mined,
                            buffer_size=len(host.buffer),
                            constitution_violations=host._constitution_guard.violations,
                        )
                        provisional_pass_considered = True
                        _log_provisional_pass_outcome(
                            source=(
                                "self_eval_exhausted"
                                if review_trigger == "self_eval_exhausted"
                                else "meta_review"
                            ),
                            should_grant=prov.should_grant,
                            blocked_reason=prov.blocked_reason,
                            safeguards=prov.safeguards,
                        )
                        if prov.should_grant:
                            gen0_provisional = True
                    if review_plan.enter_strong_recovery:
                        _log_stall_event(
                            event="stall_detected",
                            stall=stall_result,
                            strong_recovery=True,
                        )
                        if (
                            cur_cfg.adaptation_enabled
                            and cur_cfg.wall_behavior == "adaptive"
                        ):
                            _try_adaptive_stall_recovery(failure_key="velocity_stall")
                    elif review_plan.exit_strong_recovery:
                        _log_stall_event(
                            event="stall_recovered",
                            stall=stall_result,
                            strong_recovery=False,
                        )
            if strong_recovery_mode:
                strong_recovery_attempts += 1
                prov = host._maybe_trigger_provisional_pass(
                    stage=stage,
                    stage_trades=stage_trades,
                    required=required,
                    attempt=attempt,
                    strong_recovery_attempts=strong_recovery_attempts,
                    patterns_mined=patterns_mined,
                    buffer_size=len(host.buffer),
                    constitution_violations=host._constitution_guard.violations,
                    combined_velocity=snap.combined_velocity,
                    allow_provisional=allow_provisional,
                    cfg=cur_cfg,
                )
                provisional_pass_considered = True
                _log_provisional_pass_outcome(
                    source="strong_recovery",
                    should_grant=prov.should_grant,
                    blocked_reason=prov.blocked_reason,
                    safeguards=prov.safeguards,
                )
                if prov.should_grant:
                    gen0_provisional = True
        elif stage_trades >= required and rollout.trades > 0:
            stall_result = host._detect_stall(
                winrate_history=winrate_history,
                reward_history=reward_history,
                low_velocity_attempts=low_velocity_attempts,
                cfg=cur_cfg,
            )
            low_velocity_attempts = stall_result.low_velocity_attempts
            if stall_result.is_stalled:
                if not strong_recovery_mode:
                    strong_recovery_mode = True
                    strong_recovery_attempts = 0
                    escalation_level = min(
                        cur_cfg.max_escalation_level,
                        escalation_level + cur_cfg.strong_recovery_escalation_boost,
                    )
                    cur_cfg.rollout_chunk_trades = max(
                        cur_cfg.exploration_chunk_size,
                        cur_cfg.exploration_chunk_size * 2,
                    )
                    low_velocity_attempts = 0
                    _log_stall_event(
                        event="stall_detected",
                        stall=stall_result,
                        strong_recovery=True,
                    )
                    _mine_and_inject(aggressive=True)
                    if cur_cfg.adaptation_enabled and cur_cfg.wall_behavior == "adaptive":
                        _try_adaptive_stall_recovery(failure_key="velocity_stall")
            elif (
                strong_recovery_mode
                and stall_result.combined_velocity > cur_cfg.velocity_stall_epsilon
            ):
                strong_recovery_mode = False
                strong_recovery_attempts = 0
                cur_cfg.rollout_chunk_trades = max(
                    cur_cfg.exploration_chunk_size,
                    original_rollout_chunk,
                )
                _log_stall_event(
                    event="stall_recovered",
                    stall=stall_result,
                    strong_recovery=False,
                )
            if strong_recovery_mode:
                strong_recovery_attempts += 1
                prov = host._maybe_trigger_provisional_pass(
                    stage=stage,
                    stage_trades=stage_trades,
                    required=required,
                    attempt=attempt,
                    strong_recovery_attempts=strong_recovery_attempts,
                    patterns_mined=patterns_mined,
                    buffer_size=len(host.buffer),
                    constitution_violations=host._constitution_guard.violations,
                    combined_velocity=stall_result.combined_velocity,
                    allow_provisional=allow_provisional,
                    cfg=cur_cfg,
                )
                provisional_pass_considered = True
                _log_provisional_pass_outcome(
                    source="strong_recovery_legacy",
                    should_grant=prov.should_grant,
                    blocked_reason=prov.blocked_reason,
                    safeguards=prov.safeguards,
                )
                if prov.should_grant:
                    gen0_provisional = True

        if (
            stage == CurriculumStage.STAGE1_TREND
            and stage_trades >= required
            and (current_winrate < pass_metric_target or current_hold_ratio > 0.85)
        ):
            if abs(current_winrate - last_winrate) < 0.01 and abs(
                current_hold_ratio - last_hold_ratio
            ) < 0.01:
                winrate_stagnation_count += 1
            else:
                winrate_stagnation_count = 0
            last_winrate = current_winrate
            last_hold_ratio = current_hold_ratio
        elif (
            stage == CurriculumStage.STAGE2_RANGE
            and stage_trades >= required
            and (metric_band > 0.70 or metric_band < 0.30)
        ):
            if abs(metric_band - last_hold_ratio) < 0.01:
                hold_stagnation_count += 1
            else:
                hold_stagnation_count = 0
            last_hold_ratio = metric_band
        else:
            hold_stagnation_count = 0
            if stage != CurriculumStage.STAGE1_TREND:
                winrate_stagnation_count = 0

        for traj in rollout.trajectories:
            host.buffer.add(traj, priority=1.0 + min(10.0, abs(float(traj.get("reward", 0.0)))))

        if len(host.buffer) >= 256:
            stage_winrate = float(stage_wins) / float(max(1, stage_trades))
            _write_progress(
                phase="ppo_training",
                message=(
                    f"PPO batch start · {stage_trades:,}/{required:,} trades · "
                    f"winrate {stage_winrate:.1%} · patronen {patterns_mined:,}"
                ),
                hold_ratio=float(stage_hold_signals) / float(max(1, stage_total_signals)),
            )
            host.current_policy = host.ppo_trainer.update_from_buffer(
                buffer=host.buffer,
                timesteps=ppo_steps_per_update,
                birth_phase=True,
            )
            host.ppo_steps += ppo_steps_per_update
            host._persist_checkpoint(
                training_mode=training_mode,
                curriculum_stage=stage.value,
                phase="ppo_training",
                stage_metrics=_stage_metrics_payload(),
            )

        if rollout.stalled and stage_trades == 0 and patterns_mined == 0:
            escalation_level += 1
            if escalation_level >= cur_cfg.max_escalation_level:
                _mine_and_inject()
                _maybe_expand_data()
                escalation_level = 0
        elif rollout.trades == 0 or rollout.partial_complete:
            escalation_level = min(escalation_level + 1, cur_cfg.max_escalation_level - 1)
        elif rollout.trades < max(1, chunk_target // 4):
            escalation_level = min(escalation_level + 1, cur_cfg.max_escalation_level - 1)

        attempt += 1
        for pct in (50, 75, 90):
            if (
                pct not in budget_milestones_notified
                and effective_trade_budget_cap > 0
                and host.cumulative_trades * 100 // effective_trade_budget_cap >= pct
            ):
                budget_milestones_notified.add(pct)
                try:
                    from lumina_core.notifications.milestone_events import (
                        trade_budget_milestone_event,
                    )

                    host._notify_milestone(
                        trade_budget_milestone_event(
                            pct=pct,
                            cumulative_trades=host.cumulative_trades,
                            cap=effective_trade_budget_cap,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_budget_failed: %s", exc)
        if winrate_history:
            prior_mean = sum(winrate_history) / float(len(winrate_history))
            if current_winrate >= prior_mean + 0.02:
                try:
                    from lumina_core.notifications.milestone_events import (
                        learning_breakthrough_event,
                    )

                    host._notify_milestone(
                        learning_breakthrough_event(
                            winrate=current_winrate,
                            prior_mean=prior_mean,
                            delta=current_winrate - prior_mean,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_breakthrough_failed: %s", exc)
        if plateau_state.active:
            increment_evolution_rollout(plateau_state)
            failure_key_rollout = {
                CurriculumStage.STAGE1_TREND: "stage1_winrate",
                CurriculumStage.STAGE2_RANGE: "stage2_metric",
                CurriculumStage.STAGE3_MIXED: "stage3_constitution",
            }.get(stage, "stage_metrics")
            if _try_evolution_exhausted_remediation(failure_key=failure_key_rollout):
                attempt = 0
            else:
                _maybe_advance_plateau_evolution_in_loop()
        if remediation_state.active:
            increment_remediation_rollout(remediation_state)
            if _maybe_advance_stall_remediation_in_loop():
                pending = _plateau_terminal_pending(failure_key="stage1_winrate") or {
                    "failure_key": "stage1_winrate",
                    "blocker_metric": "trend_winrate",
                    "blocker_value": float(stage_wins) / float(max(1, stage_trades)),
                    "blocker_reason": HUMAN_GATE_REASON,
                    "terminal_stall_reason": HUMAN_GATE_REASON,
                }
                human_gate = not cur_cfg.autonomous_recovery_enabled
                stall_result = _finalize_certified_stage_stall(
                    pending,
                    human_gate=human_gate,
                )
                return stall_result
        update_plateau_quarantine_after_rollout(
            plateau_quarantine,
            stage_trades=stage_trades,
        )
        _maybe_detect_plateau(stage_trades=stage_trades, stage_wins=stage_wins)
        _maybe_save_best_policy(stage_trades=stage_trades, stage_wins=stage_wins)
        _maybe_periodic_checkpoint("curriculum_learning")
        _write_progress(
            phase="curriculum_learning",
            message=(
                f"Curriculum {stage.value}: {stage_trades:,} / {required:,} trades · "
                f"poging {attempt} · patronen {patterns_mined:,}{meta_message_suffix}"
            ),
            hold_ratio=current_hold_ratio,
        )
        meta_message_suffix = ""

