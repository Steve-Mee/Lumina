"""Validation Gate. Doubt = reject. Always returns the full report and always audits."""

from __future__ import annotations

import math
from pathlib import Path

from lumina_research.validation.audit import write_event
from lumina_research.validation.dsr import DSR_FORMULATION
from lumina_research.validation.pbo import PBO_FORMULATION
from lumina_research.validation.thresholds import (
    FLOOR_DSR_PROBABILITY_MIN,
    FLOOR_MIN_OOS_WINDOWS,
    FLOOR_PBO_HARD_REJECT,
    FLOOR_PBO_WARNING,
    FLOOR_WFE_MIN,
    FrozenThresholds,
    enforce_floors,
    load_thresholds,
)
from lumina_research.validation.trial_registry import TrialRegistry
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
    registry: TrialRegistry | None = None,
    thresholds: FrozenThresholds | Thresholds | None = None,
) -> tuple[bool, GateReport]:
    """Hard reject on PBO>0.50, DSR below threshold, negative median OOS after costs,
    WFE below threshold, fewer than 6 OOS windows, missing costs, missing regimes,
    or a missing/NaN/inf metric.

    The report ALWAYS contains the OOS distribution, DSR, PBO, WFE and reject reasons.
    Caller-supplied thresholds cannot weaken the packaged floors.
    """
    loaded = _resolve_thresholds(thresholds)
    report: GateReport | None = None
    passed = False
    try:
        passed, report = _judge(results, loaded, registry)
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


def _judge(
    results: ValidationResults,
    thresholds: Thresholds,
    registry: TrialRegistry | None,
) -> tuple[bool, GateReport]:
    reasons: list[str] = []
    warnings: list[str] = []
    doubt = False
    floors = enforce_floors(thresholds)

    if results.n_oos_windows < max(floors.min_oos_windows, FLOOR_MIN_OOS_WINDOWS):
        reasons.append("fewer_than_min_oos_windows")
        doubt = True
    if results.wfe.n_windows < max(floors.min_oos_windows, FLOOR_MIN_OOS_WINDOWS):
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
    if not results.regimes.is_complete():
        reasons.append("missing_regimes")
        doubt = True
    if results.dsr.formulation != DSR_FORMULATION:
        reasons.append("dsr_formulation")
        doubt = True
    if results.pbo.formulation != PBO_FORMULATION:
        reasons.append("pbo_formulation")
        doubt = True
    if not results.purge_applied or not results.embargo_applied:
        reasons.append("purge_or_embargo_missing")
        doubt = True

    n_trials = registry.n_trials if registry is not None else 0
    if registry is None:
        reasons.append("trial_registry_missing")
        doubt = True
    if n_trials < 1 or results.dsr.n_trials < 1:
        reasons.append("trial_registry_empty")
        doubt = True
    if registry is not None and results.n_trials_registry != n_trials:
        reasons.append("trial_count_mismatch")
        doubt = True
    if registry is not None and results.dsr.n_trials != n_trials:
        reasons.append("trial_count_mismatch")
        doubt = True
    if results.pbo.n_configs > max(n_trials, results.dsr.n_trials):
        reasons.append("trial_count_below_pbo_configs")
        doubt = True
    if results.pbo.n_configs < 2:
        reasons.append("pbo_requires_multiple_configs")
        doubt = True

    pbo_hard = min(floors.pbo_hard_reject, FLOOR_PBO_HARD_REJECT)
    pbo_warn = min(floors.pbo_warning, FLOOR_PBO_WARNING, pbo_hard)
    dsr_min = max(floors.dsr_probability_min, FLOOR_DSR_PROBABILITY_MIN)
    wfe_min = max(floors.wfe_min, FLOOR_WFE_MIN)

    if math.isfinite(results.pbo.pbo) and results.pbo.pbo > pbo_hard:
        reasons.append("pbo_hard_reject")
    elif math.isfinite(results.pbo.pbo) and results.pbo.pbo >= pbo_warn:
        warnings.append("pbo_warning")

    if math.isfinite(results.dsr.probability) and results.dsr.probability < dsr_min:
        reasons.append("dsr_below_threshold")

    if math.isfinite(results.median_oos_after_costs) and results.median_oos_after_costs < 0.0:
        reasons.append("negative_median_oos_after_costs")

    if math.isfinite(results.wfe.wfe) and results.wfe.wfe < wfe_min:
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
        thresholds=floors,
        agent_id=results.agent_id,
        purge_applied=results.purge_applied,
        embargo_applied=results.embargo_applied,
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
        thresholds=enforce_floors(thresholds),
        agent_id=results.agent_id,
        purge_applied=results.purge_applied,
        embargo_applied=results.embargo_applied,
    )


def _resolve_thresholds(thresholds: FrozenThresholds | Thresholds | None) -> Thresholds:
    if thresholds is None:
        return enforce_floors(load_thresholds().as_thresholds())
    if isinstance(thresholds, FrozenThresholds):
        return enforce_floors(thresholds.as_thresholds())
    return enforce_floors(thresholds)


def _audit_decision(results: ValidationResults, passed: bool, report: GateReport | None) -> None:
    path: Path = results.audit_path
    metrics = (
        report.to_audit_metrics() if report is not None else {"passed": False, "reject_reasons": ["missing_report"]}
    )
    write_event(path=path, agent_id=results.agent_id, event="gate", metrics=metrics)
    if not passed:
        write_event(path=path, agent_id=results.agent_id, event="reject", metrics=metrics)
