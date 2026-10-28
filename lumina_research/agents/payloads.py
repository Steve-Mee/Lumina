"""Convert Phase 1 GateReport snapshots into versioned bus payloads."""

from __future__ import annotations

import math
from typing import Mapping

from pydantic import BaseModel

from lumina_core.agent_orchestration.schemas_research import (
    DSRPayload,
    OOSDistributionPayload,
    PBOPayload,
    RegimePayload,
    WFEPayload,
)
from lumina_research.validation.types import (
    DSRSnapshot,
    GateReport,
    OOSDistribution,
    PBOSnapshot,
    RegimeSnapshot,
    WFESnapshot,
)


def dump_json(model: BaseModel) -> dict[str, object]:
    dumped = model.model_dump(mode="json", exclude_none=False)
    out: dict[str, object] = {}
    for key in dumped:
        out[str(key)] = dumped[key]
    return out


def json_float(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    return float(value)


def oos_payload(snapshot: OOSDistribution) -> OOSDistributionPayload:
    return OOSDistributionPayload(
        values=tuple(json_float(item) for item in snapshot.values),
        median=json_float(snapshot.median),
        mean=json_float(snapshot.mean),
        stdev=json_float(snapshot.stdev),
        worst=json_float(snapshot.worst),
        best=json_float(snapshot.best),
        pct_positive=json_float(snapshot.pct_positive),
    )


def dsr_payload(snapshot: DSRSnapshot) -> DSRPayload:
    return DSRPayload(
        probability=json_float(snapshot.probability),
        observed_sr=json_float(snapshot.observed_sr),
        expected_max_sr=json_float(snapshot.expected_max_sr),
        sr_standard_error=json_float(snapshot.sr_standard_error),
        n_trials=int(snapshot.n_trials),
        n_observations=int(snapshot.n_observations),
        skew=json_float(snapshot.skew),
        kurtosis=json_float(snapshot.kurtosis),
        formulation=snapshot.formulation,
    )


def pbo_payload(snapshot: PBOSnapshot) -> PBOPayload:
    return PBOPayload(
        pbo=json_float(snapshot.pbo),
        n_slices=int(snapshot.n_slices),
        n_combinations=int(snapshot.n_combinations),
        n_configs=int(snapshot.n_configs),
        n_below_median=int(snapshot.n_below_median),
        formulation=snapshot.formulation,
        logit_mean=json_float(snapshot.logit_mean),
    )


def wfe_payload(snapshot: WFESnapshot) -> WFEPayload:
    return WFEPayload(
        wfe=json_float(snapshot.wfe),
        mean_is_sharpe=json_float(snapshot.mean_is_sharpe),
        mean_oos_sharpe=json_float(snapshot.mean_oos_sharpe),
        n_windows=int(snapshot.n_windows),
        mode=snapshot.mode,
        parameter_stability=json_float(snapshot.parameter_stability),
    )


def regime_payload(snapshot: RegimeSnapshot) -> RegimePayload:
    return RegimePayload(
        vol_high_sharpe=json_float(snapshot.vol_high_sharpe),
        vol_low_sharpe=json_float(snapshot.vol_low_sharpe),
        trend_up_sharpe=json_float(snapshot.trend_up_sharpe),
        trend_down_sharpe=json_float(snapshot.trend_down_sharpe),
        robustness=json_float(snapshot.robustness),
    )


def report_metric_fields(report: GateReport) -> Mapping[str, object]:
    return {
        "oos_distribution": dump_json(oos_payload(report.oos_distribution)),
        "dsr": dump_json(dsr_payload(report.dsr)),
        "pbo": dump_json(pbo_payload(report.pbo)),
        "wfe": dump_json(wfe_payload(report.wfe)),
        "regimes": dump_json(regime_payload(report.regimes)),
        "n_oos_windows": report.n_oos_windows,
        "median_oos_after_costs": json_float(report.median_oos_after_costs),
        "reject_reasons": list(report.reject_reasons),
        "passed": report.passed,
        "full_audit": report.to_audit_metrics(),
    }
