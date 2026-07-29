"""Birth data expansion ladder (BRO)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from lumina_core.birth.history_loader import (
    actual_calendar_days_from_ticks,
    load_historical_ticks,
)
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


def default_expansion_steps() -> list[int]:
    return [90, 180, 365, 730]


def clamp_expansion_steps(
    expansion_steps: list[int] | None,
    *,
    max_real_days: int,
) -> list[int]:
    """Clamp ladder rungs to max_real_days (dedupe, keep ascending order)."""
    cap = max(1, int(max_real_days))
    raw = list(expansion_steps if expansion_steps is not None else default_expansion_steps())
    if not raw:
        raw = default_expansion_steps()
    clamped: list[int] = []
    seen: set[int] = set()
    for step in raw:
        days = min(max(1, int(step)), cap)
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
    """Load the next tranche of historical data for birth research."""
    if max_real_days is not None:
        steps = clamp_expansion_steps(expansion_steps, max_real_days=int(max_real_days))
    else:
        steps = list(expansion_steps or default_expansion_steps())
        if not steps:
            steps = default_expansion_steps()
    step_index = min(max(0, current_step), len(steps) - 1)
    days_back = int(steps[step_index])
    exhausted = step_index >= len(steps) - 1 and current_step >= len(steps)

    ticks = load_historical_ticks(
        market_data_service=market_data_service,
        runtime=runtime,
        days_back=days_back,
        limit=None,
    )
    if not ticks and synthetic_fallback_fn is not None:
        ticks = synthetic_fallback_fn(max(20_000, days_back * 1000), start_price)
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
            }
        },
    )

    return DataExpansionResult(
        train_ticks=list(split.train),
        holdout_ticks=list(split.holdout),
        all_ticks=ticks,
        split=split,
        days_back=days_back,
        step_index=step_index + 1,
        real_data_pct=real_pct,
        exhausted=exhausted and len(ticks) == 0,
        requested_days=days_back,
        actual_calendar_days=actual_days,
    )
