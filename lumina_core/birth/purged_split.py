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
