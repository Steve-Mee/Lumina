"""Birth data expansion ladder (BRO)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from lumina_core.birth.history_loader import load_historical_ticks
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


def default_expansion_steps() -> list[int]:
    return [90, 180, 365, 730]


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
) -> DataExpansionResult:
    """Load the next tranche of historical data for birth research."""
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

    logger.info(
        "birth.data_expansion.complete",
        extra={
            "event_data": {
                "days_back": days_back,
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
    )
