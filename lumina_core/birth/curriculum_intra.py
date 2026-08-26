"""Stage 1/2 intra-stage easy→hard curriculum helpers."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.birth_trade_geometry import SEGMENT_BREAK_KEY, SEGMENT_ID_KEY
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


def _tick_time_key(tick: dict[str, Any]) -> tuple[float, float]:
    """Sort key: bar_index preferred, else timestamp, else 0."""
    bi = tick.get("bar_index", tick.get("bar_idx"))
    try:
        bi_f = float(bi) if bi is not None else 0.0
    except (TypeError, ValueError):
        bi_f = 0.0
    ts = tick.get("timestamp") or tick.get("ts") or 0
    try:
        if isinstance(ts, (int, float)):
            ts_f = float(ts)
        else:
            from datetime import datetime

            ts_f = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        ts_f = 0.0
    return (bi_f, ts_f)


def _sort_ticks_chrono(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(t) for t in ticks), key=_tick_time_key)


def sample_contiguous_intra_windows(
    easy_ticks: list[dict[str, Any]],
    hard_ticks: list[dict[str, Any]],
    *,
    hard_pct: float,
    pool_size: int,
    rng: random.Random,
    window_len: int = 256,
    chrono_source: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build a rollout pool from **contiguous** windows (truthful path continuity).

    Prefer slices from ``chrono_source`` (full stage series in time order) tagged
    by easy/hard membership. Fallback: time-sort each difficulty pool and take
    contiguous index windows — never per-bar IID sample + full shuffle.
    """
    size = max(1, int(pool_size))
    win = max(32, int(window_len))
    hard_pct = max(0.0, min(1.0, float(hard_pct)))

    if chrono_source and len(chrono_source) >= win:
        chrono = list(chrono_source)
        # Membership via bar_index / object identity / content id.
        def _mid(t: dict[str, Any]) -> Any:
            # Normalize bar_index so int/float membership matches (easy pool vs chrono).
            if t.get("bar_index") is not None:
                try:
                    return ("bi", int(float(t.get("bar_index"))))
                except (TypeError, ValueError):
                    return ("bi", t.get("bar_index"))
            if t.get("timestamp") is not None:
                return ("ts", str(t.get("timestamp")))
            return ("px", t.get("last"), t.get("close"))

        easy_ids = {_mid(t) for t in easy_ticks}
        hard_ids = {_mid(t) for t in hard_ticks}
        n = len(chrono)
        max_start = max(0, n - win)
        if max_start <= 0:
            return [dict(t) for t in chrono[:size]]

        def _window_hard_frac(start: int) -> float:
            sl = chrono[start : start + win]
            if not sl:
                return 0.0
            h = sum(1 for t in sl if _mid(t) in hard_ids)
            e = sum(1 for t in sl if _mid(t) in easy_ids)
            known = h + e
            if known <= 0:
                return 0.5
            return h / float(known)

        hard_starts = [i for i in range(0, max_start + 1, max(1, win // 4)) if _window_hard_frac(i) >= 0.45]
        easy_starts = [i for i in range(0, max_start + 1, max(1, win // 4)) if _window_hard_frac(i) < 0.45]
        if not hard_starts:
            hard_starts = list(range(0, max_start + 1, max(1, win // 2)))
        if not easy_starts:
            easy_starts = list(range(0, max_start + 1, max(1, win // 2)))

        n_windows = max(1, (size + win - 1) // win)
        n_hard_w = int(round(n_windows * hard_pct))
        n_easy_w = max(0, n_windows - n_hard_w)
        windows: list[list[dict[str, Any]]] = []
        for _ in range(n_easy_w):
            st = int(rng.choice(easy_starts))
            windows.append(
                _stamp_difficulty_on_slice(
                    chrono[st : st + win], easy_ids=easy_ids, hard_ids=hard_ids, mid_fn=_mid
                )
            )
        for _ in range(n_hard_w):
            st = int(rng.choice(hard_starts))
            windows.append(
                _stamp_difficulty_on_slice(
                    chrono[st : st + win], easy_ids=easy_ids, hard_ids=hard_ids, mid_fn=_mid
                )
            )
        rng.shuffle(windows)  # window order only — never bar order inside
        return _stamp_and_concat_windows(windows, size=size)

    # Fallback: contiguous windows inside time-sorted difficulty pools.
    easy_c = _sort_ticks_chrono(easy_ticks) if easy_ticks else []
    hard_c = _sort_ticks_chrono(hard_ticks) if hard_ticks else []
    if not easy_c and not hard_c:
        return []
    if not easy_c:
        easy_c = list(hard_c)
    if not hard_c:
        hard_c = list(easy_c)

    def _windows_from(series: list[dict[str, Any]], count: int) -> list[list[dict[str, Any]]]:
        if count <= 0 or not series:
            return []
        wlen = min(win, len(series))
        max_st = max(0, len(series) - wlen)
        out_w: list[list[dict[str, Any]]] = []
        for _ in range(count):
            st = int(rng.randint(0, max_st)) if max_st > 0 else 0
            out_w.append([dict(t) for t in series[st : st + wlen]])
        return out_w

    n_windows = max(1, (size + win - 1) // win)
    n_hard_w = int(round(n_windows * hard_pct))
    n_easy_w = max(0, n_windows - n_hard_w)
    windows = _windows_from(easy_c, n_easy_w) + _windows_from(hard_c, n_hard_w)
    if not windows:
        return [dict(t) for t in (easy_c + hard_c)[:size]]
    rng.shuffle(windows)
    return _stamp_and_concat_windows(windows, size=size)


def _stamp_difficulty_on_slice(
    slice_ticks: list[dict[str, Any]],
    *,
    easy_ids: set[Any],
    hard_ids: set[Any],
    mid_fn: Any,
) -> list[dict[str, Any]]:
    """Tag each bar with easy/hard so sim_runner easy_trades telemetry works."""
    out: list[dict[str, Any]] = []
    for t in slice_ticks:
        row = dict(t)
        mid = mid_fn(row)
        if mid in easy_ids and mid not in hard_ids:
            row["_intra_difficulty"] = "easy"
        elif mid in hard_ids:
            row["_intra_difficulty"] = "hard"
        elif mid in easy_ids:
            row["_intra_difficulty"] = "easy"
        else:
            # Unknown membership: treat as hard (fail-closed for "easy" metrics).
            row.setdefault("_intra_difficulty", "hard")
        out.append(row)
    return out


def _stamp_and_concat_windows(
    windows: list[list[dict[str, Any]]],
    *,
    size: int,
) -> list[dict[str, Any]]:
    """Concatenate windows with segment markers (SIM flatten + geometry gap break)."""
    out: list[dict[str, Any]] = []
    for seg_id, w in enumerate(windows):
        for j, t in enumerate(w):
            row = dict(t)
            row[SEGMENT_ID_KEY] = int(seg_id)
            if j == 0:
                row[SEGMENT_BREAK_KEY] = True
            else:
                row.pop(SEGMENT_BREAK_KEY, None)
            # Preserve difficulty if already stamped; fallback pool windows already have it.
            if "_intra_difficulty" not in row:
                row["_intra_difficulty"] = str(t.get("_intra_difficulty") or "hard")
            out.append(row)
            if len(out) >= size:
                return out[:size]
    return out[:size] if len(out) >= size else out


def sample_intra_stage1_pool(
    easy_ticks: list[dict[str, Any]],
    hard_ticks: list[dict[str, Any]],
    state: Stage1IntraCurriculumState,
    *,
    pool_size: int,
    rng: random.Random,
    window_len: int = 256,
    chrono_source: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Sample intra pool via contiguous windows (not IID bar shuffle)."""
    return sample_contiguous_intra_windows(
        easy_ticks,
        hard_ticks,
        hard_pct=float(state.hard_pct),
        pool_size=pool_size,
        rng=rng,
        window_len=window_len,
        chrono_source=chrono_source,
    )


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
    easy_trades: int = 0
    easy_wins: int = 0
    easy_winrate_history: list[float] = field(default_factory=list)


def stage2_range_patience_score(tick: dict[str, Any]) -> float:
    """Higher score = calmer range tick (easier to stay flat)."""
    adx = float(tick.get("trend_adx_14", 0.0) or 0.0)
    strength = abs(float(tick.get("trend_regime_strength", 0.0) or 0.0))
    atr_norm = float(tick.get("trend_atr_norm", 0.0) or 0.0)
    return max(0.0, 1.0 - adx * 0.02) * 0.50 + max(0.0, 1.0 - strength) * 0.35 + max(0.0, 1.0 - atr_norm) * 0.15


def stage2_range_quality_score(tick: dict[str, Any]) -> float:
    """Higher = better early-quality range tick for selective win learning.

    Combines calm range (patience) with mean-reversion clarity: low ADX,
    non-zero short slope disagreement vs long slope (fade edge), compressed ATR.
    Pure noise (zero slopes + zero strength) scores lower than clear fade setups.
    """
    patience = stage2_range_patience_score(tick)
    slope5 = float(tick.get("trend_slope_5", 0.0) or 0.0)
    slope30 = float(tick.get("trend_slope_30", 0.0) or 0.0)
    # Disagreement magnitude: short moved, long flat → mean-reversion opportunity.
    disagree = abs(slope5 - slope30)
    disagree_term = min(1.0, disagree * 50.0)
    imb = float(tick.get("imbalance", 1.0) or 1.0)
    # Mild tape extreme helps selective entries (not required).
    imb_term = min(1.0, abs(imb - 1.0) * 2.0)
    return patience * 0.55 + disagree_term * 0.30 + imb_term * 0.15


def split_stage2_range_ticks(
    ticks: list[dict[str, Any]],
    *,
    easy_percentile: float = 0.40,
    hard_percentile: float = 0.40,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Split range ticks: easy = quality+patience friendly, hard = marginal."""
    range_ticks = [
        dict(t)
        for t in ticks
        if str(t.get("regime", "NEUTRAL")).upper() in {"NEUTRAL", "RANGING"}
        or "RANGE" in str(t.get("regime", "")).upper()
    ]
    if not range_ticks:
        return [], [], {"easy_count": 0, "hard_count": 0, "total": 0}

    scored = [(stage2_range_quality_score(t), t) for t in range_ticks]
    scored.sort(key=lambda item: item[0])
    scores = [s for s, _ in scored]
    easy_pct = max(0.05, min(0.80, float(easy_percentile)))
    hard_pct = max(0.05, min(0.80, float(hard_percentile)))
    easy_cutoff, hard_cutoff = _percentile_cutoffs(scores, easy_pct, hard_pct)

    easy_pool: list[dict[str, Any]] = []
    hard_pool: list[dict[str, Any]] = []
    for score, tick in scored:
        tick["_intra_difficulty"] = "hard"
        tick["_intra_quality_score"] = float(score)
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
    window_len: int = 256,
    chrono_source: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    return sample_intra_stage1_pool(
        easy_ticks,
        hard_ticks,
        Stage1IntraCurriculumState(hard_pct=state.hard_pct),
        pool_size=pool_size,
        rng=rng,
        window_len=window_len,
        chrono_source=chrono_source,
    )


def update_stage2_intra_state(
    state: Stage2IntraCurriculumState,
    *,
    chunk_flat_bars: int,
    chunk_range_signals: int,
    cfg: BirthCurriculumConfig,
    chunk_easy_trades: int = 0,
    chunk_easy_wins: int = 0,
) -> float:
    """Ramp hard only when occupancy target **and** early-quality WR hold on easy pool.

    Flat-only ramp previously pushed hard% while WR sat at ~26% (forensics 2026-08).
    """
    state.easy_flat_bars += max(0, int(chunk_flat_bars))
    state.easy_range_signals += max(0, int(chunk_range_signals))
    state.easy_trades += max(0, int(chunk_easy_trades))
    state.easy_wins += max(0, int(chunk_easy_wins))

    if chunk_range_signals > 0:
        chunk_flat = float(chunk_flat_bars) / float(chunk_range_signals)
        state.easy_flat_ratio_history.append(chunk_flat)
        window = max(1, int(cfg.intra_stage2_easy_stability_window))
        if len(state.easy_flat_ratio_history) > window:
            state.easy_flat_ratio_history = state.easy_flat_ratio_history[-window:]

    if int(chunk_easy_trades) > 0:
        chunk_wr = float(chunk_easy_wins) / float(max(1, chunk_easy_trades))
        state.easy_winrate_history.append(chunk_wr)
        window = max(1, int(cfg.intra_stage2_easy_stability_window))
        if len(state.easy_winrate_history) > window:
            state.easy_winrate_history = state.easy_winrate_history[-window:]

    target_flat = float(cfg.intra_stage2_easy_flat_target)
    # Early-quality floor 35% + small buffer before admitting harder ticks.
    target_wr = float(getattr(cfg, "intra_stage2_easy_winrate_target", 0.38) or 0.38)
    target_wr = max(0.35, min(0.55, target_wr))
    stability = max(1, int(cfg.intra_stage2_easy_stability_window))
    flat_ok = (
        len(state.easy_flat_ratio_history) >= stability
        and all(ratio >= target_flat * 0.75 for ratio in state.easy_flat_ratio_history[-stability:])
        and all(ratio <= 0.70 for ratio in state.easy_flat_ratio_history[-stability:])
    )
    # If no easy trade samples yet, do not ramp hard on flat alone.
    wr_ok = (
        len(state.easy_winrate_history) >= stability
        and all(wr >= target_wr for wr in state.easy_winrate_history[-stability:])
    )
    if flat_ok and wr_ok:
        step = float(cfg.intra_stage2_hard_pct_step)
        max_hard = float(cfg.intra_stage2_max_hard_pct)
        state.hard_pct = min(max_hard, state.hard_pct + step)
        state.easy_flat_ratio_history.clear()
        state.easy_winrate_history.clear()
    elif (
        len(state.easy_winrate_history) >= stability
        and int(chunk_easy_trades) > 0
        and all(wr + 1e-12 < target_wr * 0.90 for wr in state.easy_winrate_history[-stability:])
    ):
        # P2: de-ramp hard when easy quality collapses (truthful curriculum reverse).
        step = float(cfg.intra_stage2_hard_pct_step)
        init = float(getattr(cfg, "intra_stage2_initial_hard_pct", 0.15) or 0.15)
        state.hard_pct = max(init, float(state.hard_pct) - step)

    return state.hard_pct


def stage2_intra_state_from_metrics(metrics: dict[str, Any], *, default_hard_pct: float) -> Stage2IntraCurriculumState:
    history_raw = metrics.get("intra_stage2_easy_flat_ratio_history")
    history: list[float] = []
    if isinstance(history_raw, list):
        history = [float(x) for x in history_raw if isinstance(x, (int, float))]
    wr_hist_raw = metrics.get("intra_stage2_easy_winrate_history")
    wr_hist: list[float] = []
    if isinstance(wr_hist_raw, list):
        wr_hist = [float(x) for x in wr_hist_raw if isinstance(x, (int, float))]
    return Stage2IntraCurriculumState(
        hard_pct=float(metrics.get("intra_stage2_hard_pct", default_hard_pct) or default_hard_pct),
        easy_flat_bars=max(0, int(metrics.get("intra_stage2_easy_flat_bars", 0) or 0)),
        easy_range_signals=max(0, int(metrics.get("intra_stage2_easy_range_signals", 0) or 0)),
        easy_flat_ratio_history=history,
        easy_trades=max(0, int(metrics.get("intra_stage2_easy_trades", 0) or 0)),
        easy_wins=max(0, int(metrics.get("intra_stage2_easy_wins", 0) or 0)),
        easy_winrate_history=wr_hist,
    )


