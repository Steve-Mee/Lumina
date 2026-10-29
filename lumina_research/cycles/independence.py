"""Survivor independence: different family and |corr| < 0.5. Fail-closed on doubt."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

CORR_MAX = 0.5


@dataclass(frozen=True, slots=True)
class IndependenceRow:
    config_id: str
    family: str
    kept: bool
    reason: str
    max_abs_corr: float | None


def pearson_corr(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 3:
        return math.nan
    xs = tuple(float(item) for item in left)
    ys = tuple(float(item) for item in right)
    if any(not math.isfinite(item) for item in (*xs, *ys)):
        return math.nan
    mean_x = float(statistics.fmean(xs))
    mean_y = float(statistics.fmean(ys))
    var_x = sum((item - mean_x) ** 2 for item in xs)
    var_y = sum((item - mean_y) ** 2 for item in ys)
    if var_x <= 1e-18 or var_y <= 1e-18:
        return math.nan
    cov = sum((xs[index] - mean_x) * (ys[index] - mean_y) for index in range(len(xs)))
    return cov / math.sqrt(var_x * var_y)


def select_independent(
    *,
    config_ids: Sequence[str],
    families: Sequence[str],
    series: Sequence[Sequence[float]],
    scores: Sequence[float],
) -> tuple[IndependenceRow, ...]:
    n = len(config_ids)
    if n != len(families) or n != len(series) or n != len(scores):
        raise ValueError("independence inputs must align")
    order = sorted(range(n), key=lambda index: (-float(scores[index]), config_ids[index]))
    kept_index: list[int] = []
    rows: list[IndependenceRow] = []
    used_families: set[str] = set()
    for index in order:
        family = families[index]
        if family in used_families:
            rows.append(
                IndependenceRow(
                    config_id=config_ids[index],
                    family=family,
                    kept=False,
                    reason="duplicate_family",
                    max_abs_corr=None,
                )
            )
            continue
        max_corr: float | None = None
        blocked = False
        reason = "blocked"
        for other in kept_index:
            corr = pearson_corr(series[index], series[other])
            if not math.isfinite(corr):
                blocked = True
                max_corr = corr
                reason = "corr_undefined"
                break
            abs_corr = abs(corr)
            max_corr = abs_corr if max_corr is None else max(max_corr, abs_corr)
            if abs_corr >= CORR_MAX:
                blocked = True
                reason = f"corr_{abs_corr:.3f}>={CORR_MAX}"
                break
        if blocked:
            rows.append(
                IndependenceRow(
                    config_id=config_ids[index],
                    family=family,
                    kept=False,
                    reason=reason,
                    max_abs_corr=max_corr,
                )
            )
            continue
        kept_index.append(index)
        used_families.add(family)
        rows.append(
            IndependenceRow(
                config_id=config_ids[index],
                family=family,
                kept=True,
                reason="independent",
                max_abs_corr=max_corr,
            )
        )
    by_id = {item.config_id: item for item in rows}
    return tuple(by_id[config_id] for config_id in config_ids)
