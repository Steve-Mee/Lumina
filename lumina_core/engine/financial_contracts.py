from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


QualityBand = Literal["green", "amber", "red"]


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
