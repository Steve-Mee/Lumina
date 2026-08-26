"""Scorecard enrichment helpers: slopes, adaptation payload, regime distribution."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage

from lumina_core.birth.stage_scorecard_criteria import (
    CURRICULUM_STAGE_COUNT,
    curriculum_index_for_stage,
    human_sub_phase,
    pass_criteria_for_stage,
    parse_curriculum_stage,
    stage_display_name,
)


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
    wall_triggers_total: int = 0,
    autonomous_recovery_attempts: int = 0,
    autonomous_recovery_successes: int = 0,
    autonomous_recovery_rate_pct: float = 0.0,
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
        "wall_triggers_total": int(wall_triggers_total),
        "autonomous_recovery_attempts": int(autonomous_recovery_attempts),
        "autonomous_recovery_successes": int(autonomous_recovery_successes),
        "autonomous_recovery_rate_pct": round(float(autonomous_recovery_rate_pct), 2),
    }


def format_regime_distribution_summary(distribution: dict[str, Any]) -> str:
    parts: list[str] = []
    for label in ("TREND_UP", "NEUTRAL", "TREND_DOWN"):
        pct = float(distribution.get(label, 0.0) or 0.0)
        if pct <= 0:
            continue
        parts.append(f"{label.replace('_', ' ').title()} {pct * 100:.0f}%")
    return " | ".join(parts) if parts else ""


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
    total = CURRICULUM_STAGE_COUNT
    merged["curriculum_total"] = total

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
