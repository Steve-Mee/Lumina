"""Stage 1/2 intra-stage easy→hard curriculum helpers."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum_types import MIN_INTRA_POOL_TICKS

@dataclass(slots=True)
class Stage1IntraCurriculumState:
    hard_pct: float = 0.15
    easy_trades: int = 0
    easy_wins: int = 0
    easy_winrate_history: list[float] = field(default_factory=list)


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


@dataclass(slots=True)
class Stage2IntraCurriculumState:
    hard_pct: float = 0.15
    easy_flat_bars: int = 0
    easy_range_signals: int = 0
    easy_flat_ratio_history: list[float] = field(default_factory=list)


def stage2_range_patience_score(tick: dict[str, Any]) -> float:
    """Higher score = calmer range tick (easier to stay flat)."""
    adx = float(tick.get("trend_adx_14", 0.0) or 0.0)
    strength = abs(float(tick.get("trend_regime_strength", 0.0) or 0.0))
    atr_norm = float(tick.get("trend_atr_norm", 0.0) or 0.0)
    return max(0.0, 1.0 - adx * 0.02) * 0.50 + max(0.0, 1.0 - strength) * 0.35 + max(0.0, 1.0 - atr_norm) * 0.15


def split_stage2_range_ticks(
    ticks: list[dict[str, Any]],
    *,
    easy_percentile: float = 0.40,
    hard_percentile: float = 0.40,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Split range ticks: easy = calm range (patience-friendly), hard = marginal."""
    range_ticks = [
        dict(t)
        for t in ticks
        if str(t.get("regime", "NEUTRAL")).upper() in {"NEUTRAL", "RANGING"}
        or "RANGE" in str(t.get("regime", "")).upper()
    ]
    if not range_ticks:
        return [], [], {"easy_count": 0, "hard_count": 0, "total": 0}

    scored = [(stage2_range_patience_score(t), t) for t in range_ticks]
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

    if not easy_pool and hard_pool:
        easy_pool = [dict(hard_pool[-1])]
        easy_pool[0]["_intra_difficulty"] = "easy"
    if not hard_pool and easy_pool:
        hard_pool = [dict(easy_pool[0])]
        hard_pool[0]["_intra_difficulty"] = "hard"

    meta = {
        "easy_count": len(easy_pool),
        "hard_count": len(hard_pool),
        "total": len(range_ticks),
        "easy_cutoff": easy_cutoff,
        "hard_cutoff": hard_cutoff,
    }
    return easy_pool, hard_pool, meta


def sample_intra_stage2_pool(
    easy_ticks: list[dict[str, Any]],
    hard_ticks: list[dict[str, Any]],
    state: Stage2IntraCurriculumState,
    *,
    pool_size: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    return sample_intra_stage1_pool(
        easy_ticks,
        hard_ticks,
        Stage1IntraCurriculumState(hard_pct=state.hard_pct),
        pool_size=pool_size,
        rng=rng,
    )


def update_stage2_intra_state(
    state: Stage2IntraCurriculumState,
    *,
    chunk_flat_bars: int,
    chunk_range_signals: int,
    cfg: BirthCurriculumConfig,
) -> float:
    state.easy_flat_bars += max(0, int(chunk_flat_bars))
    state.easy_range_signals += max(0, int(chunk_range_signals))

    if chunk_range_signals > 0:
        chunk_flat = float(chunk_flat_bars) / float(chunk_range_signals)
        state.easy_flat_ratio_history.append(chunk_flat)
        window = max(1, int(cfg.intra_stage2_easy_stability_window))
        if len(state.easy_flat_ratio_history) > window:
            state.easy_flat_ratio_history = state.easy_flat_ratio_history[-window:]

    target = float(cfg.intra_stage2_easy_flat_target)
    stability = max(1, int(cfg.intra_stage2_easy_stability_window))
    if (
        len(state.easy_flat_ratio_history) >= stability
        and all(ratio >= target for ratio in state.easy_flat_ratio_history[-stability:])
    ):
        step = float(cfg.intra_stage2_hard_pct_step)
        max_hard = float(cfg.intra_stage2_max_hard_pct)
        state.hard_pct = min(max_hard, state.hard_pct + step)
        state.easy_flat_ratio_history.clear()

    return state.hard_pct


def stage2_intra_state_from_metrics(metrics: dict[str, Any], *, default_hard_pct: float) -> Stage2IntraCurriculumState:
    history_raw = metrics.get("intra_stage2_easy_flat_ratio_history")
    history: list[float] = []
    if isinstance(history_raw, list):
        history = [float(x) for x in history_raw if isinstance(x, (int, float))]
    return Stage2IntraCurriculumState(
        hard_pct=float(metrics.get("intra_stage2_hard_pct", default_hard_pct) or default_hard_pct),
        easy_flat_bars=max(0, int(metrics.get("intra_stage2_easy_flat_bars", 0) or 0)),
        easy_range_signals=max(0, int(metrics.get("intra_stage2_easy_range_signals", 0) or 0)),
        easy_flat_ratio_history=history,
    )


