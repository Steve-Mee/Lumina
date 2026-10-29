"""Block-bootstrap OOS distribution for static rules (researchers A3).

CPCV with no fit step reconstructs the same path every time. For static
templates we report a moving-block bootstrap of daily net returns instead,
keeping purge/embargo on the walk-forward split that feeds the gate.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.types import OOSDistribution

DEFAULT_BLOCK = 5
DEFAULT_PATHS = 48


def block_bootstrap_sharpes(
    returns: Sequence[float],
    *,
    block: int = DEFAULT_BLOCK,
    n_paths: int = DEFAULT_PATHS,
    seed: int = 20261029,
    periods_per_year: float = 252.0,
) -> OOSDistribution:
    series = tuple(float(item) for item in returns)
    n = len(series)
    if n < max(block, 8) or block < 1 or n_paths < 2:
        return OOSDistribution.missing()
    rng = random.Random(seed)
    sharpes: list[float] = []
    n_blocks = math.ceil(n / block)
    max_start = n - block
    if max_start < 0:
        return OOSDistribution.missing()
    for _ in range(n_paths):
        stitched: list[float] = []
        for _step in range(n_blocks):
            start = rng.randint(0, max_start)
            stitched.extend(series[start : start + block])
        path = tuple(stitched[:n])
        sharpes.append(annualized_sharpe(path, periods_per_year=periods_per_year))
    return OOSDistribution.from_values(sharpes)
