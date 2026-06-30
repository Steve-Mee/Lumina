"""Birth v2 configuration loader."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lumina_core.birth.birth_certificate import BirthCertificateThresholds

logger = logging.getLogger("lumina.birth.config")

BRO_ENGINE_VERSION = "BRO-v2"


@dataclass(slots=True)
class BirthNewsConfig:
    primary: str = "finnhub"
    enable_cache: bool = True
    cache_path: str = "state/birth_news_cache.json"


@dataclass(slots=True)
class BirthRewardConfig:
    """Expectancy-oriented PPO training reward (birth + sim only)."""

    enabled: bool = True
    expectancy_coeff: float = 0.5
    quality_win_bonus_coeff: float = 0.25
    loss_asymmetry_coeff: float = 1.25
    volatility_penalty_coeff: float = 0.15
    atr_floor: float = 0.0005
    trend_align_bonus_coeff: float = 0.10
    drawdown_penalty_coeff: float = 0.20
    sharpe_bonus_coeff: float = 0.05
    min_risk_usd: float = 25.0
    reward_clip: float = 5.0
    rolling_trade_window: int = 50


@dataclass(slots=True)
class BirthCurriculumConfig:
    stage1_trend_trades: int = 2000
    stage2_range_trades: int = 3000
    stage3_mixed_trades: int = 5000
    stage_pass_trade_pct: float = 0.10
    stage_pass_min_trades: int = 100
    stage4_polish_ppo_steps: int = 50_000
    rollout_step_budget_multiplier: int = 40
    stall_probe_steps: int = 5000
    exploration_steps: int = 2000
    rollout_chunk_trades: int = 250
    max_rollouts_per_stage: int = 500
    max_escalation_level: int = 5
    gen0_provisional_min_trades: int = 25
    oracle_scan_stride: int = 5
    oracle_patterns_per_stage: int = 5000
    oracle_max_hold_bars: int = 120
    data_expansion_steps: tuple[int, ...] = (90, 180, 365, 730)
    stagnation_rollouts_before_expand: int = 5
    curriculum_ppo_timesteps: int = 3_000
    polish_ppo_timesteps: int = 50_000
    max_stage_wall_sec: int = 14_400
    stage2_hold_stagnation_rollouts: int = 8
    stage1_winrate_stagnation_rollouts: int = 8
    checkpoint_interval_sec: int = 600
    max_certificate_remediation_attempts: int = 5
    allow_provisional_pass: bool = False
    certified_max_rollouts_per_stage: int = 200
    certified_stage_stall_wall_sec: int = 14_400
    adaptation_enabled: bool = True
    wall_behavior: str = "adaptive"
    max_stage_retries: int = 3
    max_adaptation_tiers: int = 4
    auto_expand_on_adaptation: bool = True
    exploration_chunk_size: int = 8
    winrate_trend_window: int = 12
    negative_slope_threshold: float = -0.005
    velocity_stall_attempt_threshold: int = 32
    velocity_stall_epsilon: float = 0.002
    strong_recovery_escalation_boost: int = 2
    reward_trend_window: int = 12
    strong_recovery_explore_fraction: float = 0.5
    strong_recovery_oracle_stride_divisor: int = 2
    strong_recovery_pattern_multiplier: int = 2
    strong_recovery_expand_every_attempts: int = 3
    strong_recovery_no_improvement_threshold: int = 12
    intra_stage1_enabled: bool = True
    intra_initial_hard_pct: float = 0.15
    intra_max_hard_pct: float = 0.70
    intra_hard_pct_step: float = 0.05
    intra_easy_winrate_target: float = 0.50
    intra_easy_stability_window: int = 3
    intra_easy_percentile: float = 0.40
    intra_hard_percentile: float = 0.40
    intra_pool_size_multiplier: int = 4
    meta_controller_enabled: bool = True
    meta_reward_tweak_step: float = 0.05
    meta_max_expectancy_coeff: float = 0.75
    meta_pattern_yield_floor: float = 0.15
    meta_improving_velocity_multiplier: float = 1.5
    meta_review_interval_rollouts: int = 5
    meta_explore_decay_improving: float = 0.65
    meta_explore_decay_stall: float = 0.50
    meta_intra_ramp_on_improving: bool = True
    meta_self_eval_enabled: bool = True
    meta_self_eval_min_stall_attempts: int = 32
    meta_self_eval_min_recovery_attempts: int = 8
    meta_self_eval_rollouts_per_strategy: int = 12
    meta_self_eval_min_velocity_gain: float = 0.003
    meta_self_eval_velocity_floor: float = 0.002
    meta_self_eval_cooldown_rollouts: int = 20
    plateau_detection_enabled: bool = True
    plateau_winrate_gap: float = 0.10
    plateau_trades_beyond_gate_multiplier: int = 10
    plateau_max_wall_sec: int = 7200
    plateau_max_evolution_steps: int = 8
    plateau_evolution_rollouts_per_step: int = 12
    max_forced_recoveries_per_plateau: int = 12
    plateau_save_best_policy: bool = True
    plateau_oracle_distill_top_pct: float = 0.25
    phoenix_reset_min_full_cycles: int = 3
    phoenix_reset_max_winrate: float = 0.30
    hold_trap_hold_ratio_threshold: float = 0.55
    hold_trap_winrate_gap: float = 0.10
    hold_trap_recovery_hold_cap: float = 0.40
    stall_remediation_enabled: bool = True
    stall_remediation_max_cycles: int = 3
    stall_remediation_max_steps: int = 5
    stall_remediation_rollouts_per_step: int = 12


@dataclass(slots=True)
class BirthV2Config:
    curriculum: BirthCurriculumConfig = field(default_factory=BirthCurriculumConfig)
    news: BirthNewsConfig = field(default_factory=BirthNewsConfig)
    reward: BirthRewardConfig = field(default_factory=BirthRewardConfig)
    holdout_pct: float = 0.20
    certificate_thresholds: BirthCertificateThresholds = field(default_factory=BirthCertificateThresholds)
    prefer_real_data_only: bool = True
    max_real_days: int = 90
    ppo_update_timesteps: int = 25_000
    chunk_size: int = 50_000
    trade_budget_cap: int = 10_000


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_wall_behavior(raw: Any) -> str:
    value = str(raw or "adaptive").strip().lower()
    if value in ("adaptive", "strict"):
        return value
    logger.warning("birth_v2.invalid_wall_behavior value=%s fallback=strict", raw)
    return "strict"


def _parse_expansion_steps(raw: Any) -> tuple[int, ...]:
    if isinstance(raw, list):
        out: list[int] = []
        for item in raw:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        if out:
            return tuple(out)
    return (90, 180, 365, 730)


def resolve_trade_budget_cap(raw: dict[str, Any]) -> tuple[int, str]:
    """Resolve global birth trade budget; prefer birth_v2, else first_boot.training_trades."""
    section = raw.get("birth_v2")
    first_boot = raw.get("first_boot")
    fb_trades = 0
    if isinstance(first_boot, dict):
        fb_trades = max(0, _coerce_int(first_boot.get("training_trades"), 0))

    if isinstance(section, dict) and section.get("trade_budget_cap") is not None:
        cap = max(500, _coerce_int(section.get("trade_budget_cap"), 10_000))
        return cap, "birth_v2.trade_budget_cap"

    if fb_trades > 0:
        return max(500, fb_trades), "first_boot.training_trades"

    return 10_000, "default"


def resolve_effective_trade_budget(
    raw: dict[str, Any],
    *,
    target_trades: int | None = None,
) -> tuple[int, str]:
    """Priority: explicit start arg > birth_v2.trade_budget_cap > first_boot.training_trades."""
    if target_trades is not None:
        try:
            from lumina_core.first_boot_ui import normalize_first_boot_training_trades

            normalized = normalize_first_boot_training_trades(int(target_trades))
            if normalized > 0:
                return normalized, "start_arg.target_trades"
        except (TypeError, ValueError):
            pass
    return resolve_trade_budget_cap(raw)


def load_birth_v2_config(workspace_root: Path | str | None = None) -> BirthV2Config:
    root = Path(workspace_root or Path.cwd())
    cfg_path = root / "config.yaml"
    raw: dict[str, Any] = {}
    if cfg_path.is_file():
        try:
            loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        except Exception as exc:
            logger.warning("birth_v2.config_load_failed detail=%s", exc)

    section = raw.get("birth_v2")
    if not isinstance(section, dict):
        section = {}
        fb = raw.get("first_boot")
        if isinstance(fb, dict):
            logger.warning("birth_v2: using deprecated first_boot keys; migrate to birth_v2 in config.yaml")
            section = {
                "prefer_real_data_only": fb.get("prefer_real_data_only", True),
                "max_real_days": fb.get("max_real_days", 90),
                "trade_budget_cap": fb.get("training_trades", 10_000),
                "ppo_update_timesteps": fb.get("ppo_update_timesteps", 25_000),
            }

    cur_raw = section.get("curriculum") if isinstance(section.get("curriculum"), dict) else {}
    news_raw = section.get("news") if isinstance(section.get("news"), dict) else {}
    reward_raw = section.get("reward") if isinstance(section.get("reward"), dict) else {}
    thr_raw = section.get("certificate_thresholds") if isinstance(section.get("certificate_thresholds"), dict) else {}

    curriculum = BirthCurriculumConfig(
        stage1_trend_trades=_coerce_int(cur_raw.get("stage1_trend_trades"), 2000),
        stage2_range_trades=_coerce_int(cur_raw.get("stage2_range_trades"), 3000),
        stage3_mixed_trades=_coerce_int(cur_raw.get("stage3_mixed_trades"), 5000),
        stage_pass_trade_pct=max(
            0.05,
            min(1.0, _coerce_float(cur_raw.get("stage_pass_trade_pct"), 0.10)),
        ),
        stage_pass_min_trades=max(50, _coerce_int(cur_raw.get("stage_pass_min_trades"), 100)),
        stage4_polish_ppo_steps=_coerce_int(cur_raw.get("stage4_polish_ppo_steps"), 50_000),
        rollout_step_budget_multiplier=_coerce_int(cur_raw.get("rollout_step_budget_multiplier"), 40),
        stall_probe_steps=_coerce_int(cur_raw.get("stall_probe_steps"), 5000),
        exploration_steps=_coerce_int(cur_raw.get("exploration_steps"), 2000),
        rollout_chunk_trades=_coerce_int(cur_raw.get("rollout_chunk_trades"), 250),
        max_rollouts_per_stage=_coerce_int(cur_raw.get("max_rollouts_per_stage"), 500),
        max_escalation_level=_coerce_int(cur_raw.get("max_escalation_level"), 5),
        gen0_provisional_min_trades=_coerce_int(cur_raw.get("gen0_provisional_min_trades"), 25),
        oracle_scan_stride=_coerce_int(cur_raw.get("oracle_scan_stride"), 5),
        oracle_patterns_per_stage=_coerce_int(cur_raw.get("oracle_patterns_per_stage"), 5000),
        oracle_max_hold_bars=_coerce_int(cur_raw.get("oracle_max_hold_bars"), 120),
        data_expansion_steps=_parse_expansion_steps(cur_raw.get("data_expansion_steps")),
        stagnation_rollouts_before_expand=_coerce_int(cur_raw.get("stagnation_rollouts_before_expand"), 5),
        curriculum_ppo_timesteps=_coerce_int(cur_raw.get("curriculum_ppo_timesteps"), 3_000),
        polish_ppo_timesteps=_coerce_int(cur_raw.get("polish_ppo_timesteps"), 50_000),
        max_stage_wall_sec=_coerce_int(cur_raw.get("max_stage_wall_sec"), 14_400),
        stage2_hold_stagnation_rollouts=_coerce_int(cur_raw.get("stage2_hold_stagnation_rollouts"), 8),
        stage1_winrate_stagnation_rollouts=_coerce_int(
            cur_raw.get("stage1_winrate_stagnation_rollouts"), 8
        ),
        checkpoint_interval_sec=_coerce_int(cur_raw.get("checkpoint_interval_sec"), 600),
        max_certificate_remediation_attempts=_coerce_int(
            cur_raw.get("max_certificate_remediation_attempts"), 5
        ),
        allow_provisional_pass=bool(cur_raw.get("allow_provisional_pass", False)),
        certified_max_rollouts_per_stage=_coerce_int(
            cur_raw.get("certified_max_rollouts_per_stage"), 200
        ),
        certified_stage_stall_wall_sec=_coerce_int(
            cur_raw.get("certified_stage_stall_wall_sec"),
            _coerce_int(cur_raw.get("max_stage_wall_sec"), 14_400),
        ),
        adaptation_enabled=bool(cur_raw.get("adaptation_enabled", True)),
        wall_behavior=_coerce_wall_behavior(cur_raw.get("wall_behavior", "adaptive")),
        max_stage_retries=_coerce_int(cur_raw.get("max_stage_retries"), 3),
        max_adaptation_tiers=_coerce_int(cur_raw.get("max_adaptation_tiers"), 4),
        auto_expand_on_adaptation=bool(cur_raw.get("auto_expand_on_adaptation", True)),
        exploration_chunk_size=_coerce_int(cur_raw.get("exploration_chunk_size"), 8),
        winrate_trend_window=_coerce_int(cur_raw.get("winrate_trend_window"), 12),
        negative_slope_threshold=_coerce_float(cur_raw.get("negative_slope_threshold"), -0.005),
        velocity_stall_attempt_threshold=max(
            5,
            min(80, _coerce_int(cur_raw.get("velocity_stall_attempt_threshold"), 32)),
        ),
        velocity_stall_epsilon=_coerce_float(cur_raw.get("velocity_stall_epsilon"), 0.002),
        strong_recovery_escalation_boost=max(
            1, _coerce_int(cur_raw.get("strong_recovery_escalation_boost"), 2)
        ),
        reward_trend_window=_coerce_int(cur_raw.get("reward_trend_window"), 12),
        strong_recovery_explore_fraction=max(
            0.25,
            min(1.0, _coerce_float(cur_raw.get("strong_recovery_explore_fraction"), 0.5)),
        ),
        strong_recovery_oracle_stride_divisor=max(
            1, _coerce_int(cur_raw.get("strong_recovery_oracle_stride_divisor"), 2)
        ),
        strong_recovery_pattern_multiplier=max(
            1, _coerce_int(cur_raw.get("strong_recovery_pattern_multiplier"), 2)
        ),
        strong_recovery_expand_every_attempts=max(
            1, _coerce_int(cur_raw.get("strong_recovery_expand_every_attempts"), 3)
        ),
        strong_recovery_no_improvement_threshold=max(
            5, _coerce_int(cur_raw.get("strong_recovery_no_improvement_threshold"), 12)
        ),
        intra_stage1_enabled=bool(cur_raw.get("intra_stage1_enabled", True)),
        intra_initial_hard_pct=max(
            0.0, min(1.0, _coerce_float(cur_raw.get("intra_initial_hard_pct"), 0.15))
        ),
        intra_max_hard_pct=max(
            0.05, min(1.0, _coerce_float(cur_raw.get("intra_max_hard_pct"), 0.70))
        ),
        intra_hard_pct_step=max(0.01, _coerce_float(cur_raw.get("intra_hard_pct_step"), 0.05)),
        intra_easy_winrate_target=max(
            0.1, min(0.95, _coerce_float(cur_raw.get("intra_easy_winrate_target"), 0.50))
        ),
        intra_easy_stability_window=max(1, _coerce_int(cur_raw.get("intra_easy_stability_window"), 3)),
        intra_easy_percentile=max(
            0.05, min(0.80, _coerce_float(cur_raw.get("intra_easy_percentile"), 0.40))
        ),
        intra_hard_percentile=max(
            0.05, min(0.80, _coerce_float(cur_raw.get("intra_hard_percentile"), 0.40))
        ),
        intra_pool_size_multiplier=max(1, _coerce_int(cur_raw.get("intra_pool_size_multiplier"), 4)),
        meta_controller_enabled=bool(cur_raw.get("meta_controller_enabled", True)),
        meta_reward_tweak_step=max(
            0.01, _coerce_float(cur_raw.get("meta_reward_tweak_step"), 0.05)
        ),
        meta_max_expectancy_coeff=max(
            0.1, min(2.0, _coerce_float(cur_raw.get("meta_max_expectancy_coeff"), 0.75))
        ),
        meta_pattern_yield_floor=max(
            0.0, min(1.0, _coerce_float(cur_raw.get("meta_pattern_yield_floor"), 0.15))
        ),
        meta_improving_velocity_multiplier=max(
            1.0, _coerce_float(cur_raw.get("meta_improving_velocity_multiplier"), 1.5)
        ),
        meta_review_interval_rollouts=max(
            1, _coerce_int(cur_raw.get("meta_review_interval_rollouts"), 5)
        ),
        meta_explore_decay_improving=max(
            0.4,
            min(1.0, _coerce_float(cur_raw.get("meta_explore_decay_improving"), 0.65)),
        ),
        meta_explore_decay_stall=max(
            0.4,
            min(1.0, _coerce_float(cur_raw.get("meta_explore_decay_stall"), 0.50)),
        ),
        meta_intra_ramp_on_improving=bool(cur_raw.get("meta_intra_ramp_on_improving", True)),
        meta_self_eval_enabled=bool(cur_raw.get("meta_self_eval_enabled", True)),
        meta_self_eval_min_stall_attempts=max(
            5, _coerce_int(cur_raw.get("meta_self_eval_min_stall_attempts"), 32)
        ),
        meta_self_eval_min_recovery_attempts=max(
            1, _coerce_int(cur_raw.get("meta_self_eval_min_recovery_attempts"), 8)
        ),
        meta_self_eval_rollouts_per_strategy=max(
            5, min(30, _coerce_int(cur_raw.get("meta_self_eval_rollouts_per_strategy"), 12))
        ),
        meta_self_eval_min_velocity_gain=max(
            0.0, _coerce_float(cur_raw.get("meta_self_eval_min_velocity_gain"), 0.003)
        ),
        meta_self_eval_velocity_floor=max(
            0.0, _coerce_float(cur_raw.get("meta_self_eval_velocity_floor"), 0.002)
        ),
        meta_self_eval_cooldown_rollouts=max(
            0, _coerce_int(cur_raw.get("meta_self_eval_cooldown_rollouts"), 20)
        ),
        plateau_detection_enabled=bool(cur_raw.get("plateau_detection_enabled", True)),
        plateau_winrate_gap=max(0.01, _coerce_float(cur_raw.get("plateau_winrate_gap"), 0.10)),
        plateau_trades_beyond_gate_multiplier=max(
            1, _coerce_int(cur_raw.get("plateau_trades_beyond_gate_multiplier"), 10)
        ),
        plateau_max_wall_sec=max(300, _coerce_int(cur_raw.get("plateau_max_wall_sec"), 7200)),
        plateau_max_evolution_steps=max(
            1, min(12, _coerce_int(cur_raw.get("plateau_max_evolution_steps"), 8))
        ),
        plateau_evolution_rollouts_per_step=max(
            1, _coerce_int(cur_raw.get("plateau_evolution_rollouts_per_step"), 12)
        ),
        max_forced_recoveries_per_plateau=max(
            1, _coerce_int(cur_raw.get("max_forced_recoveries_per_plateau"), 12)
        ),
        plateau_save_best_policy=bool(cur_raw.get("plateau_save_best_policy", True)),
        plateau_oracle_distill_top_pct=max(
            0.05,
            min(0.50, _coerce_float(cur_raw.get("plateau_oracle_distill_top_pct"), 0.25)),
        ),
        phoenix_reset_min_full_cycles=max(
            1, _coerce_int(cur_raw.get("phoenix_reset_min_full_cycles"), 3)
        ),
        phoenix_reset_max_winrate=max(
            0.05, min(0.50, _coerce_float(cur_raw.get("phoenix_reset_max_winrate"), 0.30))
        ),
        hold_trap_hold_ratio_threshold=max(
            0.40, min(0.90, _coerce_float(cur_raw.get("hold_trap_hold_ratio_threshold"), 0.55))
        ),
        hold_trap_winrate_gap=max(
            0.01, _coerce_float(cur_raw.get("hold_trap_winrate_gap"), 0.10)
        ),
        hold_trap_recovery_hold_cap=max(
            0.20, min(0.70, _coerce_float(cur_raw.get("hold_trap_recovery_hold_cap"), 0.40))
        ),
        stall_remediation_enabled=bool(cur_raw.get("stall_remediation_enabled", True)),
        stall_remediation_max_cycles=max(
            1, _coerce_int(cur_raw.get("stall_remediation_max_cycles"), 3)
        ),
        stall_remediation_max_steps=max(
            1, min(8, _coerce_int(cur_raw.get("stall_remediation_max_steps"), 5))
        ),
        stall_remediation_rollouts_per_step=max(
            1, _coerce_int(cur_raw.get("stall_remediation_rollouts_per_step"), 12)
        ),
    )

    news = BirthNewsConfig(
        primary=str(news_raw.get("primary", "finnhub") or "finnhub"),
        enable_cache=bool(news_raw.get("enable_cache", True)),
        cache_path=str(news_raw.get("cache_path", "state/birth_news_cache.json") or "state/birth_news_cache.json"),
    )

    reward = BirthRewardConfig(
        enabled=bool(reward_raw.get("enabled", True)),
        expectancy_coeff=_coerce_float(reward_raw.get("expectancy_coeff"), 0.5),
        quality_win_bonus_coeff=_coerce_float(reward_raw.get("quality_win_bonus_coeff"), 0.25),
        loss_asymmetry_coeff=_coerce_float(reward_raw.get("loss_asymmetry_coeff"), 1.25),
        volatility_penalty_coeff=_coerce_float(reward_raw.get("volatility_penalty_coeff"), 0.15),
        atr_floor=_coerce_float(reward_raw.get("atr_floor"), 0.0005),
        trend_align_bonus_coeff=_coerce_float(reward_raw.get("trend_align_bonus_coeff"), 0.10),
        drawdown_penalty_coeff=_coerce_float(reward_raw.get("drawdown_penalty_coeff"), 0.20),
        sharpe_bonus_coeff=_coerce_float(reward_raw.get("sharpe_bonus_coeff"), 0.05),
        min_risk_usd=max(1.0, _coerce_float(reward_raw.get("min_risk_usd"), 25.0)),
        reward_clip=max(0.5, _coerce_float(reward_raw.get("reward_clip"), 5.0)),
        rolling_trade_window=max(5, _coerce_int(reward_raw.get("rolling_trade_window"), 50)),
    )

    try:
        thresholds = BirthCertificateThresholds.model_validate(thr_raw or {})
    except Exception:
        thresholds = BirthCertificateThresholds()

    trade_budget_cap, budget_source = resolve_trade_budget_cap(raw)
    logger.info("birth.budget cap=%s source=%s", trade_budget_cap, budget_source)

    return BirthV2Config(
        curriculum=curriculum,
        news=news,
        reward=reward,
        holdout_pct=max(0.05, min(0.4, _coerce_float(section.get("holdout_pct"), 0.20))),
        certificate_thresholds=thresholds,
        prefer_real_data_only=bool(section.get("prefer_real_data_only", True)),
        max_real_days=max(30, min(3650, _coerce_int(section.get("max_real_days"), 90))),
        ppo_update_timesteps=max(1000, _coerce_int(section.get("ppo_update_timesteps"), 25_000)),
        chunk_size=max(2500, _coerce_int(section.get("chunk_size"), 50_000)),
        trade_budget_cap=trade_budget_cap,
    )
