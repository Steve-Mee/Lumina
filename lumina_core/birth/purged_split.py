"""Purged train/holdout split on calendar days (ADR-0004 alignment)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class PurgedSplit:
    train: list[dict[str, Any]]
    holdout: list[dict[str, Any]]
    holdout_days: int
    train_days: int


def _day_key(tick: dict[str, Any]) -> str:
    raw = str(tick.get("timestamp", "") or "").strip()
    if not raw:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        return raw[:10] if len(raw) >= 10 else "unknown"


@dataclass(slots=True)
class PurgedValidationSplit:
    """Train core + validation slice carved from train days (holdout untouched)."""

    train_core: list[dict[str, Any]]
    validation: list[dict[str, Any]]
    validation_days: int
    train_core_days: int


def purged_validation_split(
    train_ticks: list[dict[str, Any]],
    *,
    validation_pct: float = 0.15,
    embargo_sessions: int = 1,
) -> PurgedValidationSplit:
    """Hold out the last validation_pct of train calendar days for runway val gates."""
    if not train_ticks:
        return PurgedValidationSplit(train_core=[], validation=[], validation_days=0, train_core_days=0)

    day_buckets: dict[str, list[dict[str, Any]]] = {}
    for tick in train_ticks:
        key = _day_key(tick)
        day_buckets.setdefault(key, []).append(tick)

    ordered_days = sorted(day for day in day_buckets if day != "unknown")
    if not ordered_days:
        split_idx = max(1, int(len(train_ticks) * (1.0 - validation_pct)))
        return PurgedValidationSplit(
            train_core=list(train_ticks[:split_idx]),
            validation=list(train_ticks[split_idx:]),
            validation_days=1,
            train_core_days=1,
        )

    val_count = max(1, int(round(len(ordered_days) * max(0.05, min(0.35, validation_pct)))))
    val_days = ordered_days[-val_count:]
    core_days = ordered_days[: max(0, len(ordered_days) - val_count - embargo_sessions)]

    train_core: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for day in core_days:
        train_core.extend(day_buckets.get(day, []))
    for day in val_days:
        validation.extend(day_buckets.get(day, []))

    if not train_core:
        train_core = list(train_ticks[: max(1, len(train_ticks) // 2)])
    if not validation:
        validation = list(train_ticks[len(train_core) :])

    return PurgedValidationSplit(
        train_core=train_core,
        validation=validation,
        validation_days=len(val_days),
        train_core_days=len(core_days),
    )


def purged_train_holdout_split(
    ticks: list[dict[str, Any]],
    *,
    holdout_pct: float = 0.20,
    embargo_sessions: int = 1,
) -> PurgedSplit:
    if not ticks:
        return PurgedSplit(train=[], holdout=[], holdout_days=0, train_days=0)

    day_buckets: dict[str, list[dict[str, Any]]] = {}
    for tick in ticks:
        key = _day_key(tick)
        day_buckets.setdefault(key, []).append(tick)

    ordered_days = sorted(day for day in day_buckets if day != "unknown")
    if not ordered_days:
        split_idx = max(1, int(len(ticks) * (1.0 - holdout_pct)))
        return PurgedSplit(
            train=list(ticks[:split_idx]),
            holdout=list(ticks[split_idx:]),
            holdout_days=1,
            train_days=1,
        )

    holdout_count = max(1, int(round(len(ordered_days) * holdout_pct)))
    holdout_days = ordered_days[-holdout_count:]
    train_days = ordered_days[: max(0, len(ordered_days) - holdout_count - embargo_sessions)]

    train: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for day in train_days:
        train.extend(day_buckets.get(day, []))
    for day in holdout_days:
        holdout.extend(day_buckets.get(day, []))

    if not train:
        train = list(ticks[: max(1, len(ticks) // 2)])
    if not holdout:
        holdout = list(ticks[len(train) :])

    return PurgedSplit(
        train=train,
        holdout=holdout,
        holdout_days=len(holdout_days),
        train_days=len(train_days),
    )
