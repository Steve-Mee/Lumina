"""Birth curriculum stage scorecard helpers for UI transparency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    is_runway_stage,
    stage1_winrate_pass_threshold,
    stage_pass_trades,
    stage_trade_target,
)

CURRICULUM_STAGE_COUNT = 3

SCORECARD_PRESERVE_KEYS: tuple[str, ...] = (
    "curriculum_stage",
    "stage_trades",
    "stage_target_trades",
    "stage_training_budget_trades",
    "stage_wins",
    "stage_winrate",
    "stage_hold_ratio",
    "stage_hold_signals",
    "stage_total_signals",
    "curriculum_index",
    "curriculum_total",
    "stages_passed",
    "pass_criteria_id",
    "pass_criteria_label",
    "pass_metric_label",
    "pass_metric_target",
    "pass_metric_min",
    "pass_metric_max",
    "stage_display_name",
    "sub_phase",
    "sub_phase_label",
    "constitution_violations",
    "is_advancing",
    "patterns_mined",
    "learning_attempt",
    "birth_start_time",
    "elapsed_sec",
    "exploration_active",
    "oracle_wins",
    "escalation_level",
    "gen0_provisional",
    "data_days_loaded",
    "expansion_step",
    "stage_range_hold_signals",
    "stage_range_total_signals",
    "stage_range_flat_bars",
    "stage_range_round_trips",
    "stage_range_flat_ratio",
    "stage_wall_remaining_sec",
    "stage_blocker_metric",
    "stage_blocker_value",
    "pass_reason",
    "provisional_pass",
    "volume_gate_status",
    "winrate_trend_slope",
    "last_adaptation",
    "retries_this_stage",
    "adaptation_tier",
    "max_adaptation_tiers",
    "max_stage_retries",
    "auto_recovery_active",
    "adaptation_enabled",
    "wall_behavior",
    "learning_velocity_combined",
    "strong_recovery_mode",
    "velocity_stall_attempts",
    "strong_recovery_attempts",
    "provisional_pass_considered",
    "meta_primary_strategy",
    "meta_learning_health",
    "meta_pattern_quality",
    "meta_reward_tweak_active",
    "meta_reward_expectancy_coeff",
    "meta_review_trigger",
    "meta_explore_multiplier",
    "meta_rollouts_since_review",
    "meta_self_eval_phase",
    "meta_self_eval_current_strategy",
    "meta_self_eval_committed_strategy",
    "meta_self_eval_best_velocity_delta",
    "meta_self_eval_probes_completed",
    "trade_budget_cap",
    "trade_budget_remaining",
    "trade_budget_source",
    "terminal_stall_reason",
    "evolution_phase",
    "evolution_step",
    "evolution_step_label",
    "evolution_actions_remaining",
    "evolution_actions_total",
    "evolution_actions_completed",
    "evolution_phantom_steps",
    "plateau_elapsed_sec",
    "trades_beyond_gate",
    "plateau_forced_recoveries_count",
    "plateau_best_winrate",
    "needs_attention",
    "attention_reason_code",
    "attention_summary",
    "attention_recommended_actions",
    "attention_notified_at",
    "user_initiated_stop",
    "prior_stage",
    "prior_phase",
    "retryable",
    "constitution_violations_session",
    "constitution_violations_cumulative",
    "oos_metrics",
    "failure_reasons",
    "remediation_attempt",
    "remediation_max",
    "data_manifest",
    "retryable",
    "certificate_ok",
    "runway_phase",
    "micro_oos_probe",
    "birth_exit_winrate",
)


@dataclass(frozen=True, slots=True)
class PassCriteria:
    id: str
    label: str
    target_trades: int
    metric_label: str
    training_budget_trades: int = 0
    metric_target: float | None = None
    metric_min: float | None = None
    metric_max: float | None = None


def _pass_gate_label(*, pass_gate: int, training_budget: int, metric: str) -> str:
    if training_budget > pass_gate:
        return f">={pass_gate} pass gate ({training_budget} budget) · {metric}"
    return f">={pass_gate} · {metric}"


def curriculum_index_for_stage(stage: CurriculumStage) -> int:
    mapping = {
        CurriculumStage.STAGE1_TREND: 1,
        CurriculumStage.STAGE2_RANGE: 2,
        CurriculumStage.STAGE3_MIXED: 3,
        CurriculumStage.STAGE5_PROFIT_VAL: 5,
        CurriculumStage.STAGE6_RISK_DISCIPLINE: 6,
        CurriculumStage.STAGE7_HOLDOUT_PROFILE: 7,
        CurriculumStage.STAGE4_POLISH: 8,
    }
    return mapping.get(stage, 0)


def runway_curriculum_total() -> int:
    return 7


def stage_display_name(stage: CurriculumStage) -> str:
    names = {
        CurriculumStage.STAGE1_TREND: "Trend",
        CurriculumStage.STAGE2_RANGE: "Range patience",
        CurriculumStage.STAGE3_MIXED: "Mixed regimes",
        CurriculumStage.STAGE5_PROFIT_VAL: "Runway profit",
        CurriculumStage.STAGE6_RISK_DISCIPLINE: "Runway risk",
        CurriculumStage.STAGE7_HOLDOUT_PROFILE: "Runway generalize",
        CurriculumStage.STAGE4_POLISH: "Polish & certificate",
    }
    return names.get(stage, stage.value.replace("_", " ").title())


def pass_criteria_for_stage(
    stage: CurriculumStage,
    *,
    cfg: BirthCurriculumConfig | None = None,
    target_trades: int = 0,
) -> PassCriteria:
    if cfg is not None:
        required = stage_pass_trades(stage, cfg)
        training_budget = stage_trade_target(stage, cfg)
    else:
        training_budget = max(1, int(target_trades))
        required = max(50, min(100, training_budget))
    if stage == CurriculumStage.STAGE1_TREND:
        wr_gate = stage1_winrate_pass_threshold(cfg)
        return PassCriteria(
            id="trend_winrate",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"winrate >={wr_gate:.0%}",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Winrate",
            metric_target=wr_gate,
        )
    if stage == CurriculumStage.STAGE2_RANGE:
        return PassCriteria(
            id="range_roundtrip",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="position-flat 30–70% on range ticks",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Position flat",
            metric_min=0.30,
            metric_max=0.70,
        )
    if stage == CurriculumStage.STAGE3_MIXED:
        return PassCriteria(
            id="mixed_constitution",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="0 constitution violations",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Violations",
            metric_target=0.0,
        )
    if stage == CurriculumStage.STAGE5_PROFIT_VAL:
        wr = float(getattr(cfg, "runway_stage5_winrate_pass", 0.40) if cfg else 0.40)
        hold = float(getattr(cfg, "runway_stage5_hold_ratio_max", 0.55) if cfg else 0.55)
        return PassCriteria(
            id="runway_profit_val",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"val WR >={wr:.0%} · hold ≤{hold:.0%}",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Val winrate",
            metric_target=wr,
        )
    if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
        sharpe = float(getattr(cfg, "runway_stage6_sharpe_min", 0.20) if cfg else 0.20)
        dd = float(getattr(cfg, "runway_stage6_drawdown_max_pct", 12.0) if cfg else 12.0)
        return PassCriteria(
            id="runway_risk",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"Sharpe >={sharpe:.2f} · DD ≤{dd:.0f}%",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Val Sharpe",
            metric_target=sharpe,
        )
    if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        wr = float(getattr(cfg, "runway_stage7_winrate_min", 0.45) if cfg else 0.45)
        return PassCriteria(
            id="runway_holdout_profile",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"profile WR >={wr:.0%} · EP OOS probe",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Profile winrate",
            metric_target=wr,
        )
    return PassCriteria(
        id="polish_complete",
        label="Final PPO buffer polish",
        target_trades=0,
        metric_label="Polish",
        metric_target=None,
    )


def human_sub_phase(phase: str) -> str:
    mapping = {
        "curriculum_research": "Oracle research",
        "curriculum_learning": "Policy rollouts",
        "data_expansion": "Data expansion",
        "ppo_training": "PPO batch training",
        "ppo_polish": "Final PPO polish",
        "oos_evaluation": "OOS certificate eval",
        "parallel_simulation": "Parallel simulation",
    }
    key = str(phase or "").strip().lower()
    return mapping.get(key, key.replace("_", " ").title() if key else "In progress")


def compute_advancing(
    *,
    stage_trades: int,
    patterns_mined: int,
    prev_stage_trades: int,
    prev_patterns_mined: int,
    elapsed_since_snapshot_sec: float,
    stale_after_sec: float = 120.0,
) -> bool:
    has_delta = stage_trades > prev_stage_trades or patterns_mined > prev_patterns_mined
    return bool(has_delta)


def parse_curriculum_stage(value: str) -> CurriculumStage | None:
    raw = str(value or "").strip().lower()
    for stage in CurriculumStage:
        if stage.value == raw:
            return stage
    return None


def calculate_simple_slope(winrate_history: list[float]) -> float:
    if len(winrate_history) < 5:
        return 0.0
    return (winrate_history[-1] - winrate_history[0]) / max(1, len(winrate_history) - 1)


def combined_learning_velocity(
    winrate_history: list[float],
    reward_history: list[float],
) -> float:
    winrate_velocity = calculate_simple_slope(winrate_history)
    reward_velocity = calculate_simple_slope(reward_history)
    has_winrate = len(winrate_history) >= 5
    has_reward = len(reward_history) >= 5
    if has_winrate and has_reward:
        return min(winrate_velocity, reward_velocity)
    if has_winrate:
        return winrate_velocity
    if has_reward:
        return reward_velocity
    return 0.0


def enrich_adaptation_payload(
    *,
    stage_trades: int,
    required: int,
    winrate_history: list[float],
    retries_this_stage: int,
    adaptation_tier: int = 0,
    max_adaptation_tiers: int = 4,
    max_stage_retries: int = 3,
    adaptation_history: list[dict[str, Any]],
    adaptation_enabled: bool,
    wall_behavior: str,
    reward_history: list[float] | None = None,
    learning_velocity_combined: float | None = None,
    strong_recovery_mode: bool = False,
    velocity_stall_attempts: int = 0,
    strong_recovery_attempts: int = 0,
    provisional_pass_considered: bool = False,
    meta_primary_strategy: str = "hold",
    meta_learning_health: str = "flat",
    meta_pattern_quality: float = 0.0,
    meta_reward_tweak_active: bool = False,
    meta_review_trigger: str = "",
    meta_explore_multiplier: float = 1.0,
) -> dict[str, Any]:
    last_adaptation = adaptation_history[-1] if adaptation_history else {}
    adaptive_active = (
        adaptation_enabled
        and wall_behavior == "adaptive"
        and stage_trades >= required
    )
    combined = (
        float(learning_velocity_combined)
        if learning_velocity_combined is not None
        else combined_learning_velocity(winrate_history, reward_history or [])
    )
    return {
        "volume_gate_status": "PASSED" if stage_trades >= required else "PENDING",
        "winrate_trend_slope": round(calculate_simple_slope(winrate_history), 6),
        "learning_velocity_combined": round(combined, 6),
        "strong_recovery_mode": bool(strong_recovery_mode),
        "velocity_stall_attempts": int(velocity_stall_attempts),
        "strong_recovery_attempts": int(strong_recovery_attempts),
        "provisional_pass_considered": bool(provisional_pass_considered),
        "last_adaptation": last_adaptation,
        "retries_this_stage": int(retries_this_stage),
        "adaptation_tier": int(adaptation_tier),
        "max_adaptation_tiers": int(max_adaptation_tiers),
        "max_stage_retries": int(max_stage_retries),
        "auto_recovery_active": adaptive_active,
        "adaptation_enabled": bool(adaptation_enabled),
        "wall_behavior": str(wall_behavior),
        "meta_primary_strategy": str(meta_primary_strategy),
        "meta_learning_health": str(meta_learning_health),
        "meta_pattern_quality": round(float(meta_pattern_quality), 4),
        "meta_reward_tweak_active": bool(meta_reward_tweak_active),
        "meta_review_trigger": str(meta_review_trigger),
        "meta_explore_multiplier": round(float(meta_explore_multiplier), 4),
    }


def enrich_progress_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure scorecard fields exist and winrate is recomputed from stage wins/trades."""
    merged = dict(payload)
    stage = parse_curriculum_stage(str(merged.get("curriculum_stage", "") or ""))
    if stage is None:
        return merged

    stage_trades = max(0, int(merged.get("stage_trades", 0) or 0))
    if merged.get("stage_wins") is not None:
        stage_wins = max(0, int(merged.get("stage_wins", 0) or 0))
        merged["stage_wins"] = stage_wins
        if stage_trades > 0:
            merged["stage_winrate"] = round(float(stage_wins) / float(stage_trades), 4)

    stage_target = int(merged.get("stage_target_trades", 0) or 0)
    budget_target = max(stage_target, 100)
    if not merged.get("pass_criteria_id"):
        criteria = pass_criteria_for_stage(stage, target_trades=budget_target)
        merged.setdefault("pass_criteria_id", criteria.id)
        merged.setdefault("pass_criteria_label", criteria.label)
        merged.setdefault("pass_metric_label", criteria.metric_label)
        merged.setdefault("pass_metric_target", criteria.metric_target)
        merged.setdefault("pass_metric_min", criteria.metric_min)
        merged.setdefault("pass_metric_max", criteria.metric_max)
        merged.setdefault("stage_display_name", stage_display_name(stage))
    if not merged.get("curriculum_index"):
        merged["curriculum_index"] = curriculum_index_for_stage(stage)
    total = runway_curriculum_total() if is_runway_stage(stage) else CURRICULUM_STAGE_COUNT
    merged.setdefault("curriculum_total", total)

    phase = str(merged.get("sub_phase") or merged.get("phase") or "").strip().lower()
    if phase:
        merged.setdefault("sub_phase", phase)
        merged.setdefault("sub_phase_label", human_sub_phase(phase))

    cap = max(0, int(merged.get("trade_budget_cap") or merged.get("target_trades") or 0))
    cumulative = max(0, int(merged.get("cumulative_trades") or merged.get("trades_done") or 0))
    if cap > 0:
        merged["trade_budget_cap"] = cap
        merged["trade_budget_remaining"] = max(0, cap - cumulative)
    merged.setdefault("trade_budget_source", "")

    regime_dist = merged.get("regime_distribution")
    if isinstance(regime_dist, dict) and regime_dist:
        dominant = max(regime_dist.items(), key=lambda item: float(item[1] or 0.0))
        merged["regime_dominant"] = str(dominant[0])
        merged["regime_distribution_summary"] = format_regime_distribution_summary(regime_dist)

    session_violations = merged.get("constitution_violations_session")
    cumulative_violations = merged.get("constitution_violations_cumulative")
    legacy_violations = merged.get("constitution_violations")
    if session_violations is None and legacy_violations is not None:
        merged["constitution_violations_session"] = int(legacy_violations)
    if cumulative_violations is None and legacy_violations is not None:
        merged["constitution_violations_cumulative"] = int(legacy_violations)
    if stage == CurriculumStage.STAGE3_MIXED and session_violations is not None:
        merged["constitution_violations"] = int(session_violations)

    return merged


def compute_regime_distribution(ticks: list[dict[str, Any]]) -> dict[str, float]:
    """Regime label distribution for birth forensics (diagnose-only)."""
    counts = {"TREND_UP": 0.0, "TREND_DOWN": 0.0, "NEUTRAL": 0.0}
    for tick in ticks:
        label = str(tick.get("regime", "NEUTRAL") or "NEUTRAL").strip().upper()
        if label not in counts:
            label = "NEUTRAL"
        counts[label] += 1.0
    total = sum(counts.values())
    if total <= 0:
        return {key: 0.0 for key in counts}
    return {key: round(value / total, 4) for key, value in counts.items()}


def format_regime_distribution_summary(distribution: dict[str, Any]) -> str:
    parts: list[str] = []
    for label in ("TREND_UP", "NEUTRAL", "TREND_DOWN"):
        pct = float(distribution.get(label, 0.0) or 0.0)
        if pct <= 0:
            continue
        parts.append(f"{label.replace('_', ' ').title()} {pct * 100:.0f}%")
    return " · ".join(parts) if parts else ""


def learning_metric_target(
    stage: CurriculumStage,
    *,
    cfg: BirthCurriculumConfig | None = None,
    pass_criteria: PassCriteria | None = None,
) -> float:
    """Winrate target for hold-trap / plateau recovery (not stage pass gates)."""
    if stage == CurriculumStage.STAGE1_TREND:
        return stage1_winrate_pass_threshold(cfg)
    if stage == CurriculumStage.STAGE3_MIXED:
        return float(getattr(cfg, "stage1_winrate_recommended", 0.45) if cfg is not None else 0.45)
    if pass_criteria is not None and pass_criteria.metric_target is not None:
        return float(pass_criteria.metric_target)
    return 0.45


def compute_stage_blocker(
    stage: CurriculumStage,
    *,
    stage_trades: int,
    stage_wins: int,
    hold_ratio: float,
    required: int,
    constitution_violations: int,
    range_flat_ratio: float,
    range_round_trips: int,
    range_total_signals: int,
    cfg: BirthCurriculumConfig | None = None,
) -> tuple[str | None, float | None, str | None]:
    """Return (blocker_metric_id, blocker_value, human pass/block reason)."""
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    if stage == CurriculumStage.STAGE1_TREND:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = stage1_winrate_pass_threshold(cfg) if cfg is not None else 0.45
        if winrate < wr_gate:
            return (
                "winrate",
                round(winrate, 4),
                f"winrate {winrate:.1%} < {wr_gate:.0%}",
            )
        return (None, None, None)
    if stage == CurriculumStage.STAGE2_RANGE:
        if trades < required:
            return (None, None, None)
        if range_total_signals >= 50:
            metric = range_flat_ratio
            label = "position_flat"
            min_round_trips = max(3, required // 10)
            if range_round_trips < min_round_trips:
                return (
                    "round_trips",
                    float(range_round_trips),
                    f"round_trips {range_round_trips} < {min_round_trips}",
                )
        else:
            metric = hold_ratio
            label = "hold"
        if metric < 0.30 or metric > 0.70:
            return (label, round(metric, 4), f"{label} {metric:.1%} outside 30–70%")
        return (None, None, None)
    if stage == CurriculumStage.STAGE3_MIXED:
        if trades < required:
            return (None, None, None)
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    if stage == CurriculumStage.STAGE5_PROFIT_VAL:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = float(getattr(cfg, "runway_stage5_winrate_pass", 0.40) if cfg else 0.40)
        hold_cap = float(getattr(cfg, "runway_stage5_hold_ratio_max", 0.55) if cfg else 0.55)
        if winrate < wr_gate:
            return ("winrate", round(winrate, 4), f"val winrate {winrate:.1%} < {wr_gate:.0%}")
        if hold_ratio > hold_cap:
            return ("hold", round(hold_ratio, 4), f"hold {hold_ratio:.1%} > {hold_cap:.0%}")
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = float(getattr(cfg, "runway_stage6_winrate_min", 0.42) if cfg else 0.42)
        if winrate < wr_gate:
            return ("winrate", round(winrate, 4), f"val winrate {winrate:.1%} < {wr_gate:.0%}")
        return (None, None, None)
    if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        wr_gate = float(getattr(cfg, "runway_stage7_winrate_min", 0.45) if cfg else 0.45)
        if winrate < wr_gate:
            return (
                "winrate",
                round(winrate, 4),
                f"profile winrate {winrate:.1%} < {wr_gate:.0%}",
            )
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    return (None, None, None)


def build_scorecard_payload(
    *,
    stage: CurriculumStage,
    curriculum_index: int,
    stages_passed: list[str],
    stage_trades: int,
    stage_wins: int,
    stage_hold_signals: int,
    stage_total_signals: int,
    constitution_violations: int,
    target_trades: int,
    phase: str,
    patterns_mined: int,
    learning_attempt: int,
    prev_stage_trades: int = 0,
    prev_patterns_mined: int = 0,
    snapshot_elapsed_sec: float = 0.0,
    stage_range_flat_bars: int = 0,
    stage_range_total_signals: int = 0,
    stage_range_round_trips: int = 0,
    provisional_pass: bool = False,
    cfg: BirthCurriculumConfig | None = None,
) -> dict[str, Any]:
    criteria = pass_criteria_for_stage(stage, cfg=cfg, target_trades=target_trades)
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
    winrate = float(wins) / float(max(1, trades))
    is_advancing = compute_advancing(
        stage_trades=trades,
        patterns_mined=int(patterns_mined),
        prev_stage_trades=int(prev_stage_trades),
        prev_patterns_mined=int(prev_patterns_mined),
        elapsed_since_snapshot_sec=float(snapshot_elapsed_sec),
    )
    required = stage_pass_trades(stage, cfg) if cfg is not None else criteria.target_trades
    range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
    blocker_metric, blocker_value, pass_reason = compute_stage_blocker(
        stage,
        stage_trades=trades,
        stage_wins=wins,
        hold_ratio=hold_ratio,
        required=required,
        constitution_violations=int(constitution_violations),
        range_flat_ratio=range_flat_ratio,
        range_round_trips=int(stage_range_round_trips),
        range_total_signals=int(stage_range_total_signals),
        cfg=cfg,
    )
    payload: dict[str, Any] = {
        "stage_wins": wins,
        "stage_winrate": round(winrate, 4),
        "stage_hold_ratio": round(hold_ratio, 4),
        "curriculum_index": int(curriculum_index),
        "curriculum_total": CURRICULUM_STAGE_COUNT,
        "stages_passed": list(stages_passed),
        "pass_criteria_id": criteria.id,
        "pass_criteria_label": criteria.label,
        "pass_metric_label": criteria.metric_label,
        "pass_metric_target": criteria.metric_target,
        "pass_metric_min": criteria.metric_min,
        "pass_metric_max": criteria.metric_max,
        "stage_display_name": stage_display_name(stage),
        "sub_phase": str(phase).strip().lower(),
        "sub_phase_label": human_sub_phase(phase),
        "constitution_violations": int(constitution_violations),
        "is_advancing": bool(is_advancing),
        "stage_target_trades": int(required),
        "stage_training_budget_trades": int(criteria.training_budget_trades),
    }
    if blocker_metric:
        payload["stage_blocker_metric"] = blocker_metric
        payload["stage_blocker_value"] = blocker_value
        payload["pass_reason"] = pass_reason
    else:
        payload["stage_blocker_metric"] = None
        payload["stage_blocker_value"] = None
        payload["pass_reason"] = None
    if provisional_pass:
        payload["provisional_pass"] = True
    return payload
