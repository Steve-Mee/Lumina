from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


QualityBand = Literal["green", "amber", "red"]
RealityGapBand = Literal["acceptable", "elevated", "critical"]


@dataclass(slots=True)
class MarginSnapshotContract:
    source: str
    as_of: str
    confidence: float
    stale_after_hours: int
    stale: bool


@dataclass(slots=True)
class VaRQualityContract:
    quality_score: float
    quality_band: QualityBand
    data_points: int
    effective_max_var_usd: float
    effective_max_total_open_risk: float


@dataclass(slots=True)
class FinancialReportingContract:
    learning_label: str
    realism_label: str
    metrics_for_readiness_gate: Literal["realism"]
    parity_delta_pnl_realized: float
    parity_delta_max_drawdown: float
    parity_delta_sharpe_annualized: float


@dataclass(slots=True)
class StressSuiteContract:
    method: str
    worst_case_drawdown: float
    worst_case_var_breach_count: int
    stress_ready_for_real_gate: bool


@dataclass(slots=True)
class PurgedCVContract:
    """Results of purged walk-forward cross-validation (no look-ahead bias)."""

    windows: int
    embargo_bars: int
    train_days: int
    test_days: int
    mean_pnl: float
    mean_sharpe: float
    mean_winrate: float
    pnl_std: float

    @property
    def quality_band(self) -> QualityBand:
        if self.windows >= 5 and self.mean_sharpe >= 0.5:
            return "green"
        if self.windows >= 2 and self.mean_sharpe >= 0.0:
            return "amber"
        return "red"


@dataclass(slots=True)
class RealityGapContract:
    """Tracks divergence between SIM Sharpe and rolling REAL Sharpe."""

    window_observations: int
    mean_sim_real_gap: float  # positive = SIM is better than REAL (optimism bias)
    penalty_score: float  # 0.0 = no penalty, higher = more overfit
    max_gap: float

    @property
    def band(self) -> RealityGapBand:
        if self.mean_sim_real_gap <= 0.3:
            return "acceptable"
        if self.mean_sim_real_gap <= 0.7:
            return "elevated"
        return "critical"

    @property
    def blocks_real_promotion(self) -> bool:
        """True when the reality gap is so large it should block REAL promotion."""
        return self.band == "critical"


@dataclass(slots=True)
class OrderBookContract:
    """Describes order-book replay simulation parameters used in a backtest."""

    spread_atr_ratio: float
    market_impact_alpha: float
    market_impact_beta: float
    mean_half_spread_ticks: float
    mean_market_impact_ticks: float


@dataclass(slots=True)
class DynamicKellyContract:
    """Snapshot of the dynamic Kelly estimator state."""

    estimated_kelly: float  # Raw Kelly fraction (before clipping)
    fractional_kelly: float  # After safety cap (e.g., 0.25 × raw_kelly)
    rolling_win_rate: float
    rolling_avg_win: float
    rolling_avg_loss: float
    rolling_profit_factor: float  # avg_win / avg_loss (or inf)
    window_trades: int  # Number of trades in the rolling window
