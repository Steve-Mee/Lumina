"""Composite research fitness. Never in-sample PnL. Requires a gate report."""

from __future__ import annotations

import math
from dataclasses import dataclass

from lumina_research.validation.types import GateReport


class FitnessRefused(ValueError):
    """Fitness refuses input that skips the gate or smuggles in-sample PnL."""


@dataclass(frozen=True, slots=True)
class FitnessScore:
    value: float
    median_oos_term: float
    pbo_term: float
    wfe_term: float
    regime_term: float
    turnover_penalty: float
    dsr_penalty: float
    gate_passed: bool


def compute_fitness(
    report: object,
    *,
    turnover: float,
    in_sample_pnl: None = None,
    **kwargs: object,
) -> FitnessScore:
    """median OOS Sharpe after costs + (1-PBO) + WFE + regime robustness,
    with penalties for high turnover and low DSR.
    """
    if in_sample_pnl is not None:
        raise FitnessRefused("in-sample PnL is forbidden")
    if "is_pnl" in kwargs or "insample_pnl" in kwargs or "in_sample" in kwargs:
        raise FitnessRefused("in-sample PnL is forbidden")
    if kwargs:
        raise FitnessRefused(f"unknown fitness argument(s): {sorted(kwargs)}")
    if not isinstance(report, GateReport):
        raise FitnessRefused("fitness requires a GateReport from passes_validation_gate")
    _require_gate_metrics(report)
    if turnover < 0.0 or not math.isfinite(turnover):
        raise FitnessRefused("turnover must be a finite number >= 0")

    median_oos = _finite(report.oos_distribution.median, "oos_distribution.median")
    pbo = _finite(report.pbo.pbo, "pbo")
    wfe = _finite(report.wfe.wfe, "wfe")
    regime = _finite(report.regimes.robustness, "regime_robustness")
    dsr = _finite(report.dsr.probability, "dsr")

    median_term = _squash(median_oos)
    pbo_term = 1.0 - pbo
    wfe_term = max(0.0, min(wfe, 2.0)) / 2.0
    regime_term = max(0.0, min(regime, 1.0))
    turnover_penalty = 1.0 - math.exp(-turnover)
    dsr_penalty = max(0.0, report.thresholds.dsr_probability_min - dsr)

    value = median_term + pbo_term + wfe_term + regime_term - turnover_penalty - 2.0 * dsr_penalty
    if not report.passed:
        value -= 1.0
    return FitnessScore(
        value=float(value),
        median_oos_term=float(median_term),
        pbo_term=float(pbo_term),
        wfe_term=float(wfe_term),
        regime_term=float(regime_term),
        turnover_penalty=float(turnover_penalty),
        dsr_penalty=float(2.0 * dsr_penalty),
        gate_passed=report.passed,
    )


def _require_gate_metrics(report: GateReport) -> None:
    required_ok = (
        report.oos_distribution.is_complete(),
        math.isfinite(report.dsr.probability),
        math.isfinite(report.pbo.pbo),
        math.isfinite(report.wfe.wfe),
        math.isfinite(report.regimes.robustness),
        report.dsr.n_trials >= 1,
    )
    if not all(required_ok):
        raise FitnessRefused("gate report is missing OOS distribution, DSR, PBO, WFE or regimes")


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise FitnessRefused(f"gate report field {name} is missing")
    return float(value)


def _squash(sharpe: float) -> float:
    return 1.0 / (1.0 + math.exp(-sharpe))
