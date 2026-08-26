"""Multi-day SIM evaluation runner for DNA variants.

Split (Wave D): multi_day_sim_types / evaluate / backtest / day mixins.
"""
from __future__ import annotations

from typing import Any

from .multi_day_sim_backtest import MultiDaySimBacktestMixin
from .multi_day_sim_day import MultiDaySimDayMixin
from .multi_day_sim_evaluate import MultiDaySimEvaluateMixin
from .multi_day_sim_types import ShadowFill, SimResult, stable_seed

# Re-export historical private helper name
_stable_seed = stable_seed

__all__ = ["MultiDaySimRunner", "SimResult", "ShadowFill", "_stable_seed"]


class MultiDaySimRunner(
    MultiDaySimEvaluateMixin,
    MultiDaySimBacktestMixin,
    MultiDaySimDayMixin,
):
    """Runs parallel multi-day SIM evaluations for DNA variants."""

    def __init__(
        self,
        *,
        max_workers: int = 8,
        drawdown_limit_ratio: float = 0.02,
        real_market_data: bool = True,
        true_backtest_mode: bool = True,
        market_data_service: Any | None = None,
        allow_heuristic_fitness: bool = False,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.drawdown_limit_ratio = max(0.0, float(drawdown_limit_ratio))
        self.real_market_data = bool(real_market_data)
        self.true_backtest_mode = bool(true_backtest_mode)
        self.market_data_service = market_data_service
        self.allow_heuristic_fitness = bool(allow_heuristic_fitness)
