"""Birth curriculum stages (ADR-0014) + Stage 1 intra easy→hard curriculum (ADR-0020)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig

MIN_INTRA_POOL_TICKS = 100


class CurriculumStage(str, Enum):
    STAGE1_TREND = "stage1_trend"
    STAGE2_RANGE = "stage2_range"
    STAGE3_MIXED = "stage3_mixed"
    STAGE4_POLISH = "stage4_polish"


@dataclass(slots=True)
class StageResult:
    stage: CurriculumStage
    trades: int
    wins: int
    hold_ratio: float
    passed: bool
    message: str
    provisional: bool = False
    range_hold_ratio: float = 0.0
    range_flat_ratio: float = 0.0
    range_round_trips: int = 0


@dataclass(slots=True)
class Stage1IntraCurriculumState:
    hard_pct: float = 0.15
    easy_trades: int = 0
    easy_wins: int = 0
    easy_winrate_history: list[float] = field(default_factory=list)


def filter_ticks_for_stage(stage: CurriculumStage, ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if stage == CurriculumStage.STAGE1_TREND:
        return [t for t in ticks if "TREND" in str(t.get("regime", "")).upper()]
    if stage == CurriculumStage.STAGE2_RANGE:
        return [t for t in ticks if str(t.get("regime", "NEUTRAL")).upper() in {"NEUTRAL", "RANGING"}]
    return list(ticks)


def stage1_trend_difficulty_score(tick: dict[str, Any]) -> float:
    strength = abs(float(tick.get("trend_regime_strength", 0.0) or 0.0))
    duration = float(tick.get("trend_duration_norm", 0.0) or 0.0)
    adx = float(tick.get("trend_adx_14", 0.0) or 0.0)
    return strength * 0.50 + duration * 0.30 + adx * 0.20


def _percentile_cutoffs(scores: list[float], easy_pct: float, hard_pct: float) -> tuple[float, float]:
    if not scores:
        return 0.0, 0.0
    ordered = sorted(scores)
    n = len(ordered)
    easy_idx = max(0, min(n - 1, int(round((1.0 - easy_pct) * (n - 1)))))
    hard_idx = max(0, min(n - 1, int(round(hard_pct * (n - 1)))))
    return ordered[easy_idx], ordered[hard_idx]


def split_stage1_trend_ticks(
    ticks: list[dict[str, Any]],
    *,
    easy_percentile: float = 0.40,
    hard_percentile: float = 0.40,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Split trend ticks into easy (strong/long) and hard (weak/marginal) pools."""
    trend_ticks = [dict(t) for t in ticks if "TREND" in str(t.get("regime", "")).upper()]
    if not trend_ticks:
        return [], [], {"easy_count": 0, "hard_count": 0, "total": 0}

    scored = [(stage1_trend_difficulty_score(t), t) for t in trend_ticks]
    scored.sort(key=lambda item: item[0])
    scores = [s for s, _ in scored]

    easy_pct = max(0.05, min(0.80, float(easy_percentile)))
    hard_pct = max(0.05, min(0.80, float(hard_percentile)))
    easy_cutoff, hard_cutoff = _percentile_cutoffs(scores, easy_pct, hard_pct)

    easy_pool: list[dict[str, Any]] = []
    hard_pool: list[dict[str, Any]] = []
    for score, tick in scored:
        tick["_intra_difficulty"] = "hard"
        if score >= easy_cutoff:
            tick["_intra_difficulty"] = "easy"
            easy_pool.append(tick)
        else:
            hard_pool.append(tick)

    if len(easy_pool) < MIN_INTRA_POOL_TICKS and len(scored) >= MIN_INTRA_POOL_TICKS:
        split_at = max(1, int(len(scored) * (1.0 - easy_pct)))
        easy_pool = []
        hard_pool = []
        for score, tick in scored:
            tick = dict(tick)
            if score >= scored[split_at][0]:
                tick["_intra_difficulty"] = "easy"
                easy_pool.append(tick)
            else:
                tick["_intra_difficulty"] = "hard"
                hard_pool.append(tick)

    if not easy_pool and hard_pool:
        easy_pool = [dict(hard_pool[-1])]
        easy_pool[0]["_intra_difficulty"] = "easy"
    if not hard_pool and easy_pool:
        hard_pool = [dict(easy_pool[0])]
        hard_pool[0]["_intra_difficulty"] = "hard"

    meta = {
        "easy_count": len(easy_pool),
        "hard_count": len(hard_pool),
        "total": len(trend_ticks),
        "easy_cutoff": easy_cutoff,
        "hard_cutoff": hard_cutoff,
    }
    return easy_pool, hard_pool, meta


def sample_intra_stage1_pool(
    easy_ticks: list[dict[str, Any]],
    hard_ticks: list[dict[str, Any]],
    state: Stage1IntraCurriculumState,
    *,
    pool_size: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    size = max(1, int(pool_size))
    if not easy_ticks and not hard_ticks:
        return []
    if not easy_ticks:
        return [dict(rng.choice(hard_ticks)) for _ in range(size)]
    if not hard_ticks:
        return [dict(rng.choice(easy_ticks)) for _ in range(size)]

    hard_pct = max(0.0, min(1.0, float(state.hard_pct)))
    hard_count = int(round(size * hard_pct))
    easy_count = max(0, size - hard_count)

    pool: list[dict[str, Any]] = []
    for _ in range(easy_count):
        pool.append(dict(rng.choice(easy_ticks)))
    for _ in range(hard_count):
        pool.append(dict(rng.choice(hard_ticks)))
    while len(pool) < size:
        pool.append(dict(rng.choice(easy_ticks if rng.random() >= hard_pct else hard_ticks)))
    rng.shuffle(pool)
    return pool


def update_stage1_intra_state(
    state: Stage1IntraCurriculumState,
    *,
    chunk_easy_trades: int,
    chunk_easy_wins: int,
    cfg: BirthCurriculumConfig,
) -> float:
    """Update cumulative easy metrics and possibly increase hard_pct."""
    state.easy_trades += max(0, int(chunk_easy_trades))
    state.easy_wins += max(0, int(chunk_easy_wins))

    if chunk_easy_trades > 0:
        chunk_wr = float(chunk_easy_wins) / float(chunk_easy_trades)
        state.easy_winrate_history.append(chunk_wr)
        window = max(1, int(cfg.intra_easy_stability_window))
        if len(state.easy_winrate_history) > window:
            state.easy_winrate_history = state.easy_winrate_history[-window:]

    target = float(cfg.intra_easy_winrate_target)
    stability = max(1, int(cfg.intra_easy_stability_window))
    if (
        len(state.easy_winrate_history) >= stability
        and all(wr >= target for wr in state.easy_winrate_history[-stability:])
    ):
        step = float(cfg.intra_hard_pct_step)
        max_hard = float(cfg.intra_max_hard_pct)
        state.hard_pct = min(max_hard, state.hard_pct + step)
        state.easy_winrate_history.clear()

    return state.hard_pct


def stage1_intra_state_from_metrics(metrics: dict[str, Any], *, default_hard_pct: float) -> Stage1IntraCurriculumState:
    history_raw = metrics.get("intra_stage1_easy_winrate_history")
    history: list[float] = []
    if isinstance(history_raw, list):
        history = [float(x) for x in history_raw if isinstance(x, (int, float))]
    return Stage1IntraCurriculumState(
        hard_pct=float(metrics.get("intra_stage1_hard_pct", default_hard_pct) or default_hard_pct),
        easy_trades=max(0, int(metrics.get("intra_stage1_easy_trades", 0) or 0)),
        easy_wins=max(0, int(metrics.get("intra_stage1_easy_wins", 0) or 0)),
        easy_winrate_history=history,
    )


def stage_trade_target(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    if stage == CurriculumStage.STAGE1_TREND:
        return cfg.stage1_trend_trades
    if stage == CurriculumStage.STAGE2_RANGE:
        return cfg.stage2_range_trades
    if stage == CurriculumStage.STAGE3_MIXED:
        return cfg.stage3_mixed_trades
    return 0


def stage_pass_trades(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    """Minimum cumulative trades required to graduate a curriculum stage."""
    target = stage_trade_target(stage, cfg)
    if target <= 0:
        return 50
    pct = max(0.05, min(1.0, float(cfg.stage_pass_trade_pct)))
    floor = max(50, int(cfg.stage_pass_min_trades))
    computed = max(floor, int(round(float(target) * pct)))
    return max(50, min(target, computed))


def stage_progress_pct(stage_trades: int, cfg: BirthCurriculumConfig, *, stage: CurriculumStage) -> float:
    required = stage_pass_trades(stage, cfg)
    if required <= 0:
        return 0.0
    return min(100.0, (float(stage_trades) / float(required)) * 100.0)


def should_gen0_soft_pass(
    *,
    stage_trades: int,
    buffer_size: int,
    attempt: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    if attempt < cfg.max_rollouts_per_stage:
        return False
    if stage_trades < cfg.gen0_provisional_min_trades:
        return False
    return buffer_size >= 256


def stage1_winrate_pass_threshold(cfg: BirthCurriculumConfig) -> float:
    """SSOT for stage1 trend winrate graduation gate (clamped to floor)."""
    floor = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35))
    threshold = float(getattr(cfg, "stage1_winrate_pass_threshold", 0.45))
    return max(floor, min(0.60, threshold))


def stage1_winrate_recommended(cfg: BirthCurriculumConfig) -> float:
    return float(getattr(cfg, "stage1_winrate_recommended", 0.45))


def evaluate_stage_pass(
    stage: CurriculumStage,
    *,
    trades: int,
    wins: int,
    hold_signals: int,
    total_signals: int,
    range_hold_signals: int = 0,
    range_total_signals: int = 0,
    range_flat_bars: int = 0,
    range_round_trips: int = 0,
    constitution_violations: int,
    target_trades: int,
    cfg: BirthCurriculumConfig | None = None,
    provisional: bool = False,
    allow_provisional: bool = False,
    oracle_patterns: int = 0,
    buffer_size: int = 0,
    oracle_soft_min_patterns: int = 100,
) -> StageResult:
    winrate = float(wins) / float(max(1, trades))
    hold_ratio = float(hold_signals) / float(max(1, total_signals))
    range_hold_ratio = float(range_hold_signals) / float(max(1, range_total_signals))
    range_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
    if cfg is not None:
        required = stage_pass_trades(stage, cfg)
    else:
        required = max(50, min(100, max(1, int(target_trades))))
    passed = False
    message = ""

    if stage == CurriculumStage.STAGE1_TREND:
        wr_gate = stage1_winrate_pass_threshold(cfg) if cfg is not None else 0.45
        passed = trades >= required and winrate >= wr_gate
        message = f"trend winrate={winrate:.2%} trades={trades}/{required} gate={wr_gate:.0%}"
    elif stage == CurriculumStage.STAGE2_RANGE:
        if range_total_signals >= 50:
            metric = range_flat_ratio
            metric_label = "range_flat"
            min_round_trips = max(3, required // 10)
            passed = (
                trades >= required
                and 0.30 <= metric <= 0.70
                and range_round_trips >= min_round_trips
            )
            message = (
                f"{metric_label}_ratio={metric:.2%} round_trips={range_round_trips} "
                f"trades={trades}/{required} (range_ticks={range_total_signals})"
            )
        else:
            metric = hold_ratio
            metric_label = "hold"
            passed = trades >= required and 0.30 <= metric <= 0.70
            message = (
                f"{metric_label}_ratio={metric:.2%} trades={trades}/{required} "
                f"(range_ticks={range_total_signals})"
            )
    elif stage == CurriculumStage.STAGE3_MIXED:
        passed = trades >= required and constitution_violations == 0
        message = f"mixed violations={constitution_violations} trades={trades}/{required}"
    elif stage == CurriculumStage.STAGE4_POLISH:
        passed = True
        message = "polish complete"

    if allow_provisional and provisional and not passed and trades >= max(1, required // 4):
        passed = True
        message = f"{message} gen0_provisional"

    if (
        allow_provisional
        and not passed
        and oracle_patterns >= oracle_soft_min_patterns
        and buffer_size >= 256
        and trades >= max(1, required // 4)
    ):
        passed = True
        message = f"{message} oracle_soft_pass"

    if (
        allow_provisional
        and not passed
        and provisional
        and oracle_patterns >= oracle_soft_min_patterns
        and buffer_size >= max(80, oracle_soft_min_patterns)
        and trades >= 1
    ):
        passed = True
        message = f"{message} oracle_gen0_research_pass"

    return StageResult(
        stage=stage,
        trades=trades,
        wins=wins,
        hold_ratio=hold_ratio,
        passed=passed,
        message=message,
        provisional=provisional,
        range_hold_ratio=range_hold_ratio,
        range_flat_ratio=range_flat_ratio,
        range_round_trips=int(range_round_trips),
    )


def ordered_stages() -> list[CurriculumStage]:
    return [
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_POLISH,
    ]
