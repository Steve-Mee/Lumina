"""Validation Gate hard rejects and mandatory report fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.validation.cost_model import COST_COMPONENTS, COST_MODEL_ID, COST_MODEL_VERSION
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.thresholds import default_thresholds, load_thresholds
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import (
    CostProvenance,
    DSRSnapshot,
    OOSDistribution,
    PBOSnapshot,
    RegimeSnapshot,
    ValidationResults,
    WFESnapshot,
)


def _provenance() -> CostProvenance:
    return CostProvenance(
        model_id=COST_MODEL_ID,
        model_version=COST_MODEL_VERSION,
        components=COST_COMPONENTS,
        applied=True,
        contract_root="MES",
        tick_size=0.25,
        tick_value_usd=1.25,
        commission_ticks=0.75,
    )


def _registry(path: Path, n: int = 5, agent_id: str = "gate-tester") -> TrialRegistry:
    registry = TrialRegistry(path)
    for index in range(n):
        registry.record(config_id=f"cfg-{index}", agent_id=agent_id, metrics={"i": index})
    return registry


def _good(path: Path, **overrides: object) -> ValidationResults:
    payload: dict[str, object] = {
        "agent_id": "gate-tester",
        "audit_path": path,
        "oos_distribution": OOSDistribution.from_values((1.2, 0.9, 1.1, 0.8, 1.0, 0.95)),
        "dsr": DSRSnapshot(
            probability=0.97,
            observed_sr=0.2,
            expected_max_sr=0.05,
            sr_standard_error=0.04,
            n_trials=5,
            n_observations=300,
            skew=0.0,
            kurtosis=3.0,
            formulation="bailey_lopez_de_prado_2014",
        ),
        "pbo": PBOSnapshot(
            pbo=0.10,
            n_slices=8,
            n_combinations=70,
            n_configs=5,
            n_below_median=7,
            formulation="cscv_logit_bailey_2014",
            logit_mean=0.4,
        ),
        "wfe": WFESnapshot(
            wfe=0.8,
            mean_is_sharpe=1.2,
            mean_oos_sharpe=0.96,
            n_windows=6,
            mode="rolling",
            parameter_stability=0.9,
        ),
        "cost_provenance": _provenance(),
        "median_oos_after_costs": 0.002,
        "n_oos_windows": 6,
        "regimes": RegimeSnapshot(
            vol_high_sharpe=0.8,
            vol_low_sharpe=0.7,
            trend_up_sharpe=0.9,
            trend_down_sharpe=0.4,
            robustness=0.7,
        ),
        "n_trials_registry": 5,
    }
    payload.update(overrides)
    return ValidationResults(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
def test_thresholds_defaults() -> None:
    loaded = load_thresholds().as_thresholds()
    defaults = default_thresholds()
    assert loaded.dsr_probability_min == 0.95
    assert loaded.wfe_min == 0.5
    assert loaded.pbo_warning == 0.25
    assert loaded.pbo_hard_reject == 0.50
    assert loaded.min_oos_windows == 6
    assert defaults.min_oos_windows == 6


@pytest.mark.unit
def test_good_bundle_passes_and_report_has_mandatory_fields(tmp_path: Path) -> None:
    path = tmp_path / "a.jsonl"
    registry = _registry(path)
    passed, report = passes_validation_gate(_good(path), registry=registry)
    assert passed is True
    assert report.oos_distribution.is_complete()
    assert report.dsr.probability >= 0.95
    assert report.pbo.pbo < 0.50
    assert report.wfe.wfe >= 0.5
    metrics = report.to_audit_metrics()
    for key in ("oos_distribution", "dsr", "pbo", "wfe", "reject_reasons"):
        assert key in metrics


@pytest.mark.unit
@pytest.mark.parametrize(
    "override",
    [
        {
            "pbo": PBOSnapshot(
                pbo=0.51,
                n_slices=8,
                n_combinations=70,
                n_configs=5,
                n_below_median=36,
                formulation="cscv_logit_bailey_2014",
                logit_mean=-0.1,
            )
        },
        {
            "dsr": DSRSnapshot(
                probability=0.5,
                observed_sr=0.05,
                expected_max_sr=0.08,
                sr_standard_error=0.04,
                n_trials=5,
                n_observations=300,
                skew=0.0,
                kurtosis=3.0,
                formulation="bailey_lopez_de_prado_2014",
            )
        },
        {"median_oos_after_costs": -0.001},
        {
            "wfe": WFESnapshot(
                wfe=0.2,
                mean_is_sharpe=1.2,
                mean_oos_sharpe=0.24,
                n_windows=6,
                mode="rolling",
                parameter_stability=0.9,
            )
        },
        {"n_oos_windows": 5},
        {"cost_provenance": None},
    ],
)
def test_hard_rejects(tmp_path: Path, override: dict[str, object]) -> None:
    path = tmp_path / "r.jsonl"
    registry = _registry(path)
    passed, report = passes_validation_gate(_good(path, **override), registry=registry)
    assert passed is False
    assert report.reject_reasons
    assert "oos_distribution" in report.to_audit_metrics()
    assert "dsr" in report.to_audit_metrics()
    assert "pbo" in report.to_audit_metrics()


@pytest.mark.unit
def test_pbo_warning_does_not_by_itself_pass_or_skip_report(tmp_path: Path) -> None:
    pbo = PBOSnapshot(
        pbo=0.30,
        n_slices=8,
        n_combinations=70,
        n_configs=5,
        n_below_median=21,
        formulation="cscv_logit_bailey_2014",
        logit_mean=0.05,
    )
    path = tmp_path / "w.jsonl"
    registry = _registry(path)
    passed, report = passes_validation_gate(_good(path, pbo=pbo), registry=registry)
    assert passed is True
    assert "pbo_warning" in report.warnings


@pytest.mark.unit
def test_weak_runtime_thresholds_cannot_pass_a_failing_bundle(tmp_path: Path) -> None:
    from lumina_research.validation.types import Thresholds

    path = tmp_path / "weak.jsonl"
    registry = _registry(path)
    weak = Thresholds(
        dsr_probability_min=0.0,
        wfe_min=0.0,
        pbo_hard_reject=1.0,
        pbo_warning=1.0,
        min_oos_windows=1,
    )
    results = _good(
        path,
        dsr=DSRSnapshot(
            probability=0.50,
            observed_sr=0.2,
            expected_max_sr=0.05,
            sr_standard_error=0.04,
            n_trials=5,
            n_observations=300,
            skew=0.0,
            kurtosis=3.0,
            formulation="bailey_lopez_de_prado_2014",
        ),
        wfe=WFESnapshot(
            wfe=0.1,
            mean_is_sharpe=1.2,
            mean_oos_sharpe=0.12,
            n_windows=6,
            mode="rolling",
            parameter_stability=0.9,
        ),
    )
    passed, report = passes_validation_gate(results, registry=registry, thresholds=weak)
    assert passed is False
    assert "dsr_below_threshold" in report.reject_reasons
    assert "wfe_below_threshold" in report.reject_reasons


@pytest.mark.unit
def test_missing_regimes_and_nan_metrics_reject(tmp_path: Path) -> None:
    import math

    path = tmp_path / "nan.jsonl"
    registry = _registry(path)
    passed, report = passes_validation_gate(
        _good(path, regimes=RegimeSnapshot.missing(), median_oos_after_costs=math.nan),
        registry=registry,
    )
    assert passed is False
    assert "missing_regimes" in report.reject_reasons
    assert "missing_median_oos_after_costs" in report.reject_reasons
    inf_path = tmp_path / "inf.jsonl"
    inf_registry = _registry(inf_path)
    inf_passed, inf_report = passes_validation_gate(
        _good(
            inf_path,
            dsr=DSRSnapshot(
                probability=float("inf"),
                observed_sr=0.2,
                expected_max_sr=0.05,
                sr_standard_error=0.04,
                n_trials=5,
                n_observations=300,
                skew=0.0,
                kurtosis=3.0,
                formulation="bailey_lopez_de_prado_2014",
            ),
        ),
        registry=inf_registry,
    )
    assert inf_passed is False
    assert "missing_dsr" in inf_report.reject_reasons


@pytest.mark.unit
def test_missing_registry_rejects(tmp_path: Path) -> None:
    passed, report = passes_validation_gate(_good(tmp_path / "noreg.jsonl"))
    assert passed is False
    assert "trial_registry_missing" in report.reject_reasons


@pytest.mark.unit
def test_oos_distribution_nonfinite_is_incomplete() -> None:
    dist = OOSDistribution.from_values((float("inf"), 1.0, 2.0))
    assert dist.is_complete() is False
    nan_dist = OOSDistribution.from_values((float("nan"), 1.0, 2.0))
    assert nan_dist.is_complete() is False
