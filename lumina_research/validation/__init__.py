"""Research Validation Gate. Propose-only. Doubt = reject."""

from __future__ import annotations

from lumina_research.validation.audit import AuditLog, AuditRecord
from lumina_research.validation.contracts import CONTRACTS, ContractSpec, spec_for
from lumina_research.validation.cost_model import CostModel, CostedSeries, MarketSnapshot, apply_costs
from lumina_research.validation.cpcv import CPCVConfig, CPCVResult, path_count, reconstruct_paths, run_cpcv
from lumina_research.validation.dsr import deflated_sharpe_from_moments, deflated_sharpe_ratio, expected_max_sharpe
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.pbo import probability_of_backtest_overfitting
from lumina_research.validation.thresholds import FrozenThresholds, default_thresholds, load_thresholds
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import GateReport, ValidationResults
from lumina_research.validation.walk_forward import WalkForwardConfig, run_walk_forward, static_return_scorer

__all__ = [
    "AuditLog",
    "AuditRecord",
    "CONTRACTS",
    "CPCVConfig",
    "CPCVResult",
    "ContractSpec",
    "CostModel",
    "CostedSeries",
    "FrozenThresholds",
    "GateReport",
    "MarketSnapshot",
    "TrialRegistry",
    "ValidationResults",
    "WalkForwardConfig",
    "apply_costs",
    "default_thresholds",
    "deflated_sharpe_from_moments",
    "deflated_sharpe_ratio",
    "expected_max_sharpe",
    "load_thresholds",
    "passes_validation_gate",
    "path_count",
    "probability_of_backtest_overfitting",
    "reconstruct_paths",
    "run_cpcv",
    "run_walk_forward",
    "spec_for",
    "static_return_scorer",
]
