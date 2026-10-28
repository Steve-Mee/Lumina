"""Shared frozen types for the research Validation Gate."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence


def _pct_positive(values: Sequence[float]) -> float:
    if not values:
        return math.nan
    return float(sum(1 for item in values if item > 0.0) / len(values))


@dataclass(frozen=True, slots=True)
class OOSDistribution:
    """Mandatory OOS distribution: median, spread, worst window, share positive."""

    values: tuple[float, ...]
    median: float
    mean: float
    stdev: float
    worst: float
    best: float
    pct_positive: float

    @classmethod
    def missing(cls) -> OOSDistribution:
        return cls(
            values=(),
            median=math.nan,
            mean=math.nan,
            stdev=math.nan,
            worst=math.nan,
            best=math.nan,
            pct_positive=math.nan,
        )

    @classmethod
    def from_values(cls, values: Sequence[float]) -> OOSDistribution:
        cleaned = tuple(float(item) for item in values)
        if not cleaned:
            return cls.missing()
        if any(not math.isfinite(item) for item in cleaned):
            return cls(
                values=cleaned,
                median=math.nan,
                mean=math.nan,
                stdev=math.nan,
                worst=math.nan,
                best=math.nan,
                pct_positive=math.nan,
            )
        stdev = float(statistics.pstdev(cleaned)) if len(cleaned) >= 2 else 0.0
        return cls(
            values=cleaned,
            median=float(statistics.median(cleaned)),
            mean=float(statistics.fmean(cleaned)),
            stdev=stdev,
            worst=float(min(cleaned)),
            best=float(max(cleaned)),
            pct_positive=_pct_positive(cleaned),
        )

    def is_complete(self) -> bool:
        return (
            len(self.values) > 0
            and math.isfinite(self.median)
            and math.isfinite(self.mean)
            and math.isfinite(self.worst)
            and all(math.isfinite(item) for item in self.values)
        )


@dataclass(frozen=True, slots=True)
class CostProvenance:
    model_id: str
    model_version: str
    components: tuple[str, ...]
    applied: bool
    contract_root: str
    tick_size: float
    tick_value_usd: float
    commission_ticks: float

    def is_valid(self) -> bool:
        required = ("commission", "half_spread", "slippage", "market_impact")
        return (
            self.applied
            and self.model_id == "lumina_research.validation.cost_model"
            and self.model_version != ""
            and all(name in self.components for name in required)
            and self.tick_size > 0.0
            and self.tick_value_usd > 0.0
            and self.commission_ticks >= 0.0
            and self.contract_root != ""
        )


@dataclass(frozen=True, slots=True)
class DSRSnapshot:
    probability: float
    observed_sr: float
    expected_max_sr: float
    sr_standard_error: float
    n_trials: int
    n_observations: int
    skew: float
    kurtosis: float
    formulation: str

    @classmethod
    def missing(cls) -> DSRSnapshot:
        return cls(
            probability=math.nan,
            observed_sr=math.nan,
            expected_max_sr=math.nan,
            sr_standard_error=math.nan,
            n_trials=0,
            n_observations=0,
            skew=math.nan,
            kurtosis=math.nan,
            formulation="bailey_lopez_de_prado_2014",
        )


@dataclass(frozen=True, slots=True)
class PBOSnapshot:
    pbo: float
    n_slices: int
    n_combinations: int
    n_configs: int
    n_below_median: int
    formulation: str
    logit_mean: float

    @classmethod
    def missing(cls) -> PBOSnapshot:
        return cls(
            pbo=math.nan,
            n_slices=0,
            n_combinations=0,
            n_configs=0,
            n_below_median=0,
            formulation="cscv_logit_bailey_2014",
            logit_mean=math.nan,
        )


@dataclass(frozen=True, slots=True)
class WFESnapshot:
    wfe: float
    mean_is_sharpe: float
    mean_oos_sharpe: float
    n_windows: int
    mode: str
    parameter_stability: float

    @classmethod
    def missing(cls) -> WFESnapshot:
        return cls(
            wfe=math.nan,
            mean_is_sharpe=math.nan,
            mean_oos_sharpe=math.nan,
            n_windows=0,
            mode="",
            parameter_stability=math.nan,
        )


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    vol_high_sharpe: float
    vol_low_sharpe: float
    trend_up_sharpe: float
    trend_down_sharpe: float
    robustness: float

    def is_complete(self) -> bool:
        return all(
            math.isfinite(part)
            for part in (
                self.vol_high_sharpe,
                self.vol_low_sharpe,
                self.trend_up_sharpe,
                self.trend_down_sharpe,
                self.robustness,
            )
        )

    @classmethod
    def missing(cls) -> RegimeSnapshot:
        return cls(
            vol_high_sharpe=math.nan,
            vol_low_sharpe=math.nan,
            trend_up_sharpe=math.nan,
            trend_down_sharpe=math.nan,
            robustness=math.nan,
        )


@dataclass(frozen=True, slots=True)
class Thresholds:
    dsr_probability_min: float
    wfe_min: float
    pbo_hard_reject: float
    pbo_warning: float
    min_oos_windows: int


@dataclass(frozen=True, slots=True)
class GateReport:
    passed: bool
    doubt: bool
    reject_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    oos_distribution: OOSDistribution
    dsr: DSRSnapshot
    pbo: PBOSnapshot
    wfe: WFESnapshot
    n_oos_windows: int
    median_oos_after_costs: float
    cost_provenance: CostProvenance | None
    regimes: RegimeSnapshot
    thresholds: Thresholds
    agent_id: str
    purge_applied: bool = True
    embargo_applied: bool = True

    def to_audit_metrics(self) -> dict[str, object]:
        provenance: dict[str, object] | None
        if self.cost_provenance is None:
            provenance = None
        else:
            provenance = {
                "model_id": self.cost_provenance.model_id,
                "model_version": self.cost_provenance.model_version,
                "components": list(self.cost_provenance.components),
                "applied": self.cost_provenance.applied,
                "contract_root": self.cost_provenance.contract_root,
                "tick_size": self.cost_provenance.tick_size,
                "tick_value_usd": self.cost_provenance.tick_value_usd,
                "commission_ticks": self.cost_provenance.commission_ticks,
            }
        return {
            "passed": self.passed,
            "doubt": self.doubt,
            "reject_reasons": list(self.reject_reasons),
            "warnings": list(self.warnings),
            "oos_distribution": {
                "values": list(self.oos_distribution.values),
                "median": _json_float(self.oos_distribution.median),
                "mean": _json_float(self.oos_distribution.mean),
                "stdev": _json_float(self.oos_distribution.stdev),
                "worst": _json_float(self.oos_distribution.worst),
                "best": _json_float(self.oos_distribution.best),
                "pct_positive": _json_float(self.oos_distribution.pct_positive),
            },
            "dsr": {
                "probability": _json_float(self.dsr.probability),
                "observed_sr": _json_float(self.dsr.observed_sr),
                "expected_max_sr": _json_float(self.dsr.expected_max_sr),
                "sr_standard_error": _json_float(self.dsr.sr_standard_error),
                "n_trials": self.dsr.n_trials,
                "n_observations": self.dsr.n_observations,
                "skew": _json_float(self.dsr.skew),
                "kurtosis": _json_float(self.dsr.kurtosis),
                "formulation": self.dsr.formulation,
            },
            "pbo": {
                "pbo": _json_float(self.pbo.pbo),
                "n_slices": self.pbo.n_slices,
                "n_combinations": self.pbo.n_combinations,
                "n_configs": self.pbo.n_configs,
                "n_below_median": self.pbo.n_below_median,
                "formulation": self.pbo.formulation,
                "logit_mean": _json_float(self.pbo.logit_mean),
            },
            "wfe": {
                "wfe": _json_float(self.wfe.wfe),
                "mean_is_sharpe": _json_float(self.wfe.mean_is_sharpe),
                "mean_oos_sharpe": _json_float(self.wfe.mean_oos_sharpe),
                "n_windows": self.wfe.n_windows,
                "mode": self.wfe.mode,
                "parameter_stability": _json_float(self.wfe.parameter_stability),
            },
            "n_oos_windows": self.n_oos_windows,
            "median_oos_after_costs": _json_float(self.median_oos_after_costs),
            "cost_provenance": provenance,
            "regimes": {
                "vol_high_sharpe": _json_float(self.regimes.vol_high_sharpe),
                "vol_low_sharpe": _json_float(self.regimes.vol_low_sharpe),
                "trend_up_sharpe": _json_float(self.regimes.trend_up_sharpe),
                "trend_down_sharpe": _json_float(self.regimes.trend_down_sharpe),
                "robustness": _json_float(self.regimes.robustness),
            },
            "thresholds": {
                "dsr_probability_min": self.thresholds.dsr_probability_min,
                "wfe_min": self.thresholds.wfe_min,
                "pbo_hard_reject": self.thresholds.pbo_hard_reject,
                "pbo_warning": self.thresholds.pbo_warning,
                "min_oos_windows": self.thresholds.min_oos_windows,
            },
            "agent_id": self.agent_id,
            "purge_applied": self.purge_applied,
            "embargo_applied": self.embargo_applied,
        }

    def as_promotion_fragments(self) -> dict[str, dict[str, object]]:
        """Propose-only dicts compatible with KEEP PromotionGate evidence keys."""
        dsr_value = self.dsr.probability
        pbo_value = self.pbo.pbo
        return {
            "cv_combinatorial": {
                "combinations": self.pbo.n_combinations,
                "mean_oos_sharpe": _json_float(self.oos_distribution.mean),
                "sharpe_positive_pct": _json_float(self.oos_distribution.pct_positive),
                "pbo": _json_float(pbo_value),
                "dsr": _json_float(dsr_value),
                "purge_applied": self.purge_applied,
                "embargo_applied": self.embargo_applied,
                "regime_volatility_checked": math.isfinite(self.regimes.vol_high_sharpe),
                "regime_trend_checked": math.isfinite(self.regimes.trend_up_sharpe),
            },
            "cv_walk_forward": {
                "windows": self.n_oos_windows,
                "n_windows": self.n_oos_windows,
                "sharpe_positive_pct": _json_float(self.oos_distribution.pct_positive),
                "purge_applied": self.purge_applied,
                "embargo_applied": self.embargo_applied,
                "regime_volatility_checked": math.isfinite(self.regimes.vol_high_sharpe),
                "regime_trend_checked": math.isfinite(self.regimes.trend_up_sharpe),
                "wfe": _json_float(self.wfe.wfe),
            },
        }


@dataclass(frozen=True, slots=True)
class ValidationResults:
    """Input to passes_validation_gate. Missing pieces are doubt and therefore reject."""

    agent_id: str
    audit_path: Path
    oos_distribution: OOSDistribution
    dsr: DSRSnapshot
    pbo: PBOSnapshot
    wfe: WFESnapshot
    cost_provenance: CostProvenance | None
    median_oos_after_costs: float
    n_oos_windows: int
    regimes: RegimeSnapshot
    n_trials_registry: int
    purge_applied: bool = True
    embargo_applied: bool = True


def freeze_params(params: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType({str(key): float(value) for key, value in params.items()})


def _json_float(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    return float(value)
