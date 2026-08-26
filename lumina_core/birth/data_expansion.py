"""Birth data expansion ladder (BRO)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from lumina_core.birth.foundation_history import (
    FOUNDATION_HISTORY_START_DAYS,
    foundation_history_expand_steps,
    load_foundation_history_ticks,
)
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.purged_split import PurgedSplit, purged_train_holdout_split
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim, real_data_percentage
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.data_expansion")


@dataclass(slots=True)
class DataExpansionResult:
    train_ticks: list[dict[str, Any]]
    holdout_ticks: list[dict[str, Any]]
    all_ticks: list[dict[str, Any]]
    split: PurgedSplit
    days_back: int
    step_index: int
    real_data_pct: float
    exhausted: bool
    requested_days: int = 0
    actual_calendar_days: int = 0
    # True when history returned 0 ticks and no synthetic fallback filled the gap.
    # Callers MUST NOT clobber prior train data when this is set.
    load_failed: bool = False
    stitched: bool = False
    instruments: tuple[str, ...] = ()
    stitched_from: tuple[str, ...] = ()


def default_expansion_steps() -> list[int]:
    return list(foundation_history_expand_steps())


def clamp_expansion_steps(
    expansion_steps: list[int] | None,
    *,
    max_real_days: int,
) -> list[int]:
    """Clamp ladder rungs to max_real_days (dedupe, keep ascending order)."""
    cap = max(FOUNDATION_HISTORY_START_DAYS, min(3650, int(max_real_days)))
    raw = list(expansion_steps if expansion_steps is not None else default_expansion_steps())
    if not raw:
        raw = default_expansion_steps()
    clamped: list[int] = []
    seen: set[int] = set()
    for step in raw:
        days = min(cap, max(FOUNDATION_HISTORY_START_DAYS, int(step)))
        if days in seen:
            continue
        seen.add(days)
        clamped.append(days)
    if not clamped:
        clamped = [cap]
    # Ensure the final rung reaches the cap so expansion can saturate honestly.
    if clamped[-1] < cap:
        clamped.append(cap)
    return clamped


def expansion_ladder_at_max(
    current_step: int,
    expansion_steps: list[int] | None = None,
    *,
    has_train_ticks: bool,
) -> bool:
    """True when the expansion ladder is saturated and train ticks are already loaded."""
    steps = list(expansion_steps if expansion_steps is not None else default_expansion_steps())
    if not steps or not has_train_ticks:
        return False
    return int(current_step) >= len(steps)


def expand_birth_data(
    *,
    market_data_service: Any,
    runtime: Any,
    current_step: int,
    expansion_steps: list[int] | None = None,
    holdout_pct: float = 0.20,
    enrich_news_fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None,
    synthetic_fallback_fn: Callable[[int, float], list[dict[str, Any]]] | None = None,
    start_price: float = 5000.0,
    max_real_days: int | None = None,
) -> DataExpansionResult:
    """Load the next tranche of historical data for birth research.

    Fail-closed honesty:
    - 0 ticks after load (and no synthetic fill) → ``load_failed=True``.
    - Empty load never reports fake calendar depth.
    - ``exhausted`` is true when the ladder cannot yield more real data
      (empty load on the final rung, or step pointer past the ladder).
    """
    if max_real_days is not None:
        steps = clamp_expansion_steps(expansion_steps, max_real_days=int(max_real_days))
    else:
        steps = list(expansion_steps or default_expansion_steps())
        if not steps:
            steps = default_expansion_steps()
    step_index = min(max(0, current_step), len(steps) - 1)
    days_back = int(steps[step_index])
    on_final_rung = step_index >= len(steps) - 1
    # Past the ladder, or already on the last rung with a next-step request.
    ladder_past_end = int(current_step) >= len(steps)

    loaded = load_foundation_history_ticks(
        market_data_service=market_data_service,
        runtime=runtime,
        days_back=days_back,
    )
    ticks = list(loaded.ticks)
    used_synthetic = False
    if not ticks and synthetic_fallback_fn is not None:
        ticks = synthetic_fallback_fn(max(20_000, days_back * 1000), start_price)
        used_synthetic = bool(ticks)
        logger.info(
            "birth.data_expansion.synthetic_fallback",
            extra={"event_data": {"days_back": days_back, "ticks": len(ticks)}},
        )

    if enrich_news_fn is not None:
        try:
            ticks = enrich_news_fn(ticks)
        except Exception as exc:
            logger.warning("birth.data_expansion.news_enrich_failed detail=%s", exc)

    ticks = enrich_ticks_for_sim(ticks)
    split = purged_train_holdout_split(ticks, holdout_pct=holdout_pct)
    real_pct = real_data_percentage(ticks)
    actual_days = actual_calendar_days_from_ticks(ticks)
    load_failed = len(ticks) == 0 and not used_synthetic
    # Empty real load on the final rung (or past end) saturates the ladder.
    # Empty load on an earlier rung is still a failure — callers must not
    # clobber prior data — but may retry higher rungs if any remain.
    exhausted = load_failed and (on_final_rung or ladder_past_end)

    logger.info(
        "birth.data_expansion.complete",
        extra={
            "event_data": {
                "days_back": days_back,
                "requested_days": days_back,
                "actual_calendar_days": actual_days,
                "step_index": step_index,
                "train_ticks": len(split.train),
                "holdout_ticks": len(split.holdout),
                "real_data_pct": real_pct,
                "load_failed": load_failed,
                "exhausted": exhausted,
                "used_synthetic": used_synthetic,
                "stitched": bool(loaded.stitched) and not used_synthetic,
            }
        },
    )
    if load_failed:
        logger.warning(
            "birth.data_expansion.load_failed days_back=%s step_index=%s exhausted=%s "
            "(0 bars — preserve prior train data; do not clobber)",
            days_back,
            step_index,
            exhausted,
        )

    return DataExpansionResult(
        train_ticks=list(split.train),
        holdout_ticks=list(split.holdout),
        all_ticks=ticks,
        split=split,
        days_back=days_back,
        step_index=step_index + 1,
        real_data_pct=real_pct,
        exhausted=exhausted,
        requested_days=days_back,
        actual_calendar_days=actual_days,
        load_failed=load_failed,
        stitched=bool(loaded.stitched) and not used_synthetic,
        instruments=loaded.instruments,
        stitched_from=loaded.stitched_from,
    )
