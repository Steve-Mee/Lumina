"""Synthetic paper/shadow paths and sealed promotion fixtures for continuity tests."""

from __future__ import annotations

import random
from typing import Sequence

from lumina_core.agent_orchestration.schemas_research import (
    DSRPayload,
    OOSDistributionPayload,
    PBOPayload,
    PromotionCandidate,
    RegimePayload,
    ValidationResult,
    WFEPayload,
)
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.types import Instrument
from lumina_research.validation.cost_model import COST_MODEL_ID
from lumina_research.validation.dsr import DSR_FORMULATION
from lumina_research.validation.pbo import PBO_FORMULATION

DEFAULT_OOS: tuple[float, ...] = (0.70, 0.75, 0.80, 0.78, 0.82, 0.85)


def healthy_path(rng: random.Random, *, oos_mean: float, oos_stdev: float, n: int) -> tuple[float, ...]:
    sigma = max(oos_stdev * 0.45, 1e-6)
    return tuple(rng.gauss(oos_mean, sigma) for _ in range(n))


def decaying_path(
    rng: random.Random,
    *,
    oos_mean: float,
    oos_stdev: float,
    n: int,
    decay_start: int,
) -> tuple[float, ...]:
    sigma = max(oos_stdev * 0.45, 1e-6)
    shift = oos_mean - 2.8 * max(oos_stdev, 1e-6)
    out: list[float] = []
    for index in range(n):
        mu = oos_mean if index < decay_start else shift
        out.append(rng.gauss(mu, sigma))
    return tuple(out)


def gradual_decay_path(
    rng: random.Random,
    *,
    oos_mean: float,
    oos_stdev: float,
    n: int,
    decay_start: int,
) -> tuple[float, ...]:
    sigma = max(oos_stdev * 0.45, 1e-6)
    depth = 2.8 * max(oos_stdev, 1e-6)
    span = max(n - 1 - decay_start, 1)
    out: list[float] = []
    for index in range(n):
        if index < decay_start:
            mu = oos_mean
        else:
            mu = oos_mean - depth * float(index - decay_start) / float(span)
        out.append(rng.gauss(mu, sigma))
    return tuple(out)


def high_vol_healthy_path(
    rng: random.Random,
    *,
    oos_mean: float,
    oos_stdev: float,
    n: int,
) -> tuple[float, ...]:
    sigma = max(oos_stdev, 1e-6)
    return tuple(rng.gauss(oos_mean, sigma) for _ in range(n))


def regime_shift_path(
    rng: random.Random,
    *,
    oos_mean: float,
    oos_stdev: float,
    n: int,
    decay_start: int,
) -> tuple[float, ...]:
    quiet = max(oos_stdev * 0.45, 1e-6)
    loud = max(oos_stdev, 1e-6)
    shift = oos_mean - 2.4 * max(oos_stdev, 1e-6)
    out: list[float] = []
    for index in range(n):
        if index < decay_start:
            out.append(rng.gauss(oos_mean, quiet))
        else:
            out.append(rng.gauss(shift, loud))
    return tuple(out)


def oos_stats(values: Sequence[float]) -> tuple[float, float]:
    series = tuple(float(item) for item in values)
    mean = sum(series) / float(len(series))
    var = sum((item - mean) ** 2 for item in series) / float(len(series))
    return mean, var**0.5


def seal_promotion_pair(
    authority: ProvenanceAuthority,
    *,
    hypothesis_id: str,
    config_id: str,
    trial_id: int,
    instrument: Instrument,
    quantity: float,
    notional: float,
    oos: Sequence[float] = DEFAULT_OOS,
    pbo: float = 0.12,
    dsr: float = 0.97,
    wfe: float = 0.7,
    n_oos_windows: int | None = None,
    purge_applied: bool = True,
    embargo_applied: bool = True,
    cost_applied: bool = True,
    regimes_complete: bool = True,
    passed: bool = True,
    reject_reasons: tuple[str, ...] = (),
) -> tuple[PromotionCandidate, ValidationResult]:
    values = tuple(float(item) for item in oos)
    windows = n_oos_windows if n_oos_windows is not None else len(values)
    median = sorted(values)[len(values) // 2] if values else 0.0
    mean, stdev = oos_stats(values) if values else (0.0, 0.0)
    val_fields: dict[str, object] = {
        "schema_version": "research.validation.result.v1",
        "hypothesis_id": hypothesis_id,
        "config_id": config_id,
        "trial_id": trial_id,
        "agent_id": "validation_agent",
        "passed": passed,
        "reject_reasons": list(reject_reasons),
        "oos_distribution": OOSDistributionPayload(
            values=values,
            median=median,
            mean=mean,
            stdev=stdev,
            worst=min(values) if values else None,
            best=max(values) if values else None,
            pct_positive=sum(1 for item in values if item > 0.0) / len(values) if values else None,
        ).model_dump(mode="json"),
        "dsr": DSRPayload(
            probability=dsr,
            observed_sr=median,
            expected_max_sr=1.0,
            sr_standard_error=0.1,
            n_trials=trial_id,
            n_observations=360,
            skew=0.0,
            kurtosis=3.0,
            formulation=DSR_FORMULATION,
        ).model_dump(mode="json"),
        "pbo": PBOPayload(
            pbo=pbo,
            n_slices=8,
            n_combinations=16,
            n_configs=4,
            n_below_median=2,
            formulation=PBO_FORMULATION,
            logit_mean=-1.0,
        ).model_dump(mode="json"),
        "wfe": WFEPayload(
            wfe=wfe,
            mean_is_sharpe=median,
            mean_oos_sharpe=median,
            n_windows=windows,
            mode="rolling",
            parameter_stability=0.8,
        ).model_dump(mode="json"),
        "regimes": RegimePayload(
            vol_high_sharpe=0.4,
            vol_low_sharpe=0.5,
            trend_up_sharpe=0.6,
            trend_down_sharpe=0.3,
            robustness=0.7,
        ).model_dump(mode="json"),
        "n_oos_windows": windows,
        "median_oos_after_costs": median,
        "purge_applied": purge_applied,
        "embargo_applied": embargo_applied,
        "cost_applied": cost_applied,
        "cost_contract_root": instrument,
        "cost_model_id": COST_MODEL_ID,
        "regimes_complete": regimes_complete,
    }
    digest, mac = authority.seal_validation(val_fields)
    validation = ValidationResult.model_validate({**val_fields, "report_sha256": digest, "provenance_mac": mac})
    issue: dict[str, object] = {
        "schema_version": "research.promotion.candidate.v1",
        "hypothesis_id": hypothesis_id,
        "config_id": config_id,
        "trial_id": trial_id,
        "agent_id": "promotion_agent",
        "instrument": instrument,
        "decision_kind": "approved",
        "scaled": False,
        "quantity": float(quantity),
        "notional": float(notional),
        "risk_reason": "approved",
        "validation_report_sha256": digest,
        "validation_mac": mac,
    }
    issue_mac = authority.seal_issue(issue)
    candidate = PromotionCandidate.model_validate({**issue, "issue_mac": issue_mac})
    return candidate, validation
