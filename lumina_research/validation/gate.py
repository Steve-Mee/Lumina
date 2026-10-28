"""Validation Gate. Doubt = reject. Always returns the full report and always audits."""

from __future__ import annotations

import math
from pathlib import Path

from lumina_research.validation.audit import write_event
from lumina_research.validation.thresholds import FrozenThresholds, load_thresholds
from lumina_research.validation.types import (
    CostProvenance,
    DSRSnapshot,
    GateReport,
    OOSDistribution,
    PBOSnapshot,
    Thresholds,
    ValidationResults,
    WFESnapshot,
)


def passes_validation_gate(
    results: ValidationResults,
    *,
    thresholds: FrozenThresholds | Thresholds | None = None,
) -> tuple[bool, GateReport]:
    """Hard reject on PBO>0.50, DSR below threshold, negative median OOS after costs,
    WFE below threshold, fewer than 6 OOS windows, or missing costs.

    The report ALWAYS contains the OOS distribution, DSR, PBO, WFE and reject reasons.
    """
    loaded = _resolve_thresholds(thresholds)
    report: GateReport | None = None
    passed = False
    try:
        passed, report = _judge(results, loaded)
        return passed, report
    except Exception as exc:
        report = _doubt_report(
            results,
            loaded,
            reasons=(f"evaluation_error:{type(exc).__name__}",),
        )
        passed = False
        return passed, report
    finally:
        _audit_decision(results, passed, report)


def _judge(results: ValidationResults, thresholds: Thresholds) -> tuple[bool, GateReport]:
    reasons: list[str] = []
    warnings: list[str] = []
    doubt = False

    if results.n_oos_windows < thresholds.min_oos_windows:
        reasons.append("fewer_than_min_oos_windows")
        doubt = True
    if results.wfe.n_windows < thresholds.min_oos_windows:
        reasons.append("walk_forward_windows_below_min")
        doubt = True
    if not results.oos_distribution.is_complete():
        reasons.append("missing_oos_distribution")
        doubt = True
    if not math.isfinite(results.dsr.probability):
        reasons.append("missing_dsr")
        doubt = True
    if not math.isfinite(results.pbo.pbo):
        reasons.append("missing_pbo")
        doubt = True
    if not math.isfinite(results.wfe.wfe):
        reasons.append("missing_or_undefined_wfe")
        doubt = True
    if results.cost_provenance is None or not results.cost_provenance.is_valid():
        reasons.append("missing_costs")
        doubt = True
    if not math.isfinite(results.median_oos_after_costs):
        reasons.append("missing_median_oos_after_costs")
        doubt = True
    if results.dsr.n_trials < 1:
        reasons.append("trial_registry_empty")
        doubt = True
    if results.n_trials_registry != results.dsr.n_trials:
        reasons.append("trial_count_mismatch")
        doubt = True
    if results.pbo.n_configs > results.dsr.n_trials:
        reasons.append("trial_count_below_pbo_configs")
        doubt = True
    if results.pbo.n_configs < 2:
        reasons.append("pbo_requires_multiple_configs")
        doubt = True

    if math.isfinite(results.pbo.pbo) and results.pbo.pbo > thresholds.pbo_hard_reject:
        reasons.append("pbo_hard_reject")
    elif math.isfinite(results.pbo.pbo) and results.pbo.pbo >= thresholds.pbo_warning:
        warnings.append("pbo_warning")

    if math.isfinite(results.dsr.probability) and results.dsr.probability < thresholds.dsr_probability_min:
        reasons.append("dsr_below_threshold")

    if math.isfinite(results.median_oos_after_costs) and results.median_oos_after_costs < 0.0:
        reasons.append("negative_median_oos_after_costs")

    if math.isfinite(results.wfe.wfe) and results.wfe.wfe < thresholds.wfe_min:
        reasons.append("wfe_below_threshold")

    if doubt:
        reasons.append("doubt")

    unique_reasons = tuple(dict.fromkeys(reasons))
    passed = len(unique_reasons) == 0
    report = GateReport(
        passed=passed,
        doubt=doubt,
        reject_reasons=unique_reasons,
        warnings=tuple(warnings),
        oos_distribution=results.oos_distribution,
        dsr=results.dsr,
        pbo=results.pbo,
        wfe=results.wfe,
        n_oos_windows=results.n_oos_windows,
        median_oos_after_costs=results.median_oos_after_costs,
        cost_provenance=results.cost_provenance,
        regimes=results.regimes,
        thresholds=thresholds,
        agent_id=results.agent_id,
    )
    return passed, report


def _doubt_report(results: ValidationResults, thresholds: Thresholds, reasons: tuple[str, ...]) -> GateReport:
    oos = results.oos_distribution if results.oos_distribution.values else OOSDistribution.missing()
    dsr = results.dsr if results.dsr.n_trials else DSRSnapshot.missing()
    pbo = results.pbo if math.isfinite(results.pbo.pbo) else PBOSnapshot.missing()
    wfe = results.wfe if results.wfe.n_windows else WFESnapshot.missing()
    regimes = results.regimes
    provenance: CostProvenance | None = results.cost_provenance
    return GateReport(
        passed=False,
        doubt=True,
        reject_reasons=reasons + ("doubt",),
        warnings=(),
        oos_distribution=oos,
        dsr=dsr,
        pbo=pbo,
        wfe=wfe,
        n_oos_windows=results.n_oos_windows,
        median_oos_after_costs=results.median_oos_after_costs,
        cost_provenance=provenance,
        regimes=regimes,
        thresholds=thresholds,
        agent_id=results.agent_id,
    )


def _resolve_thresholds(thresholds: FrozenThresholds | Thresholds | None) -> Thresholds:
    if thresholds is None:
        return load_thresholds().as_thresholds()
    if isinstance(thresholds, FrozenThresholds):
        return thresholds.as_thresholds()
    return thresholds


def _audit_decision(results: ValidationResults, passed: bool, report: GateReport | None) -> None:
    path: Path = results.audit_path
    metrics = report.to_audit_metrics() if report is not None else {"passed": False, "reject_reasons": ["missing_report"]}
    write_event(path=path, agent_id=results.agent_id, event="gate", metrics=metrics)
    if not passed:
        write_event(path=path, agent_id=results.agent_id, event="reject", metrics=metrics)
