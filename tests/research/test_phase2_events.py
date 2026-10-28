"""Frozen, versioned, schema-validated research events."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.schemas_research import (
    HYPOTHESIS_SCHEMA_VERSION,
    PROMOTION_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
    DSRPayload,
    EconomicRationale,
    HypothesisProposed,
    OOSDistributionPayload,
    PBOPayload,
    PromotionCandidate,
    RegimePayload,
    ValidationResult,
    WFEPayload,
)


def _rationale() -> EconomicRationale:
    return EconomicRationale(
        mechanism="Inventory-holding premium after four-leg costs xx",
        why_edge_exists="Impatient demand pays spread and impact to move inventory",
        other_side="Noise traders demanding immediacy on the tape",
        expected_regime="trend-up moderate volatility",
        falsification_criterion="median OOS after costs <= 0 or PBO > 0.50",
    )


@pytest.mark.unit
def test_rationale_blank_or_missing_is_refused() -> None:
    with pytest.raises(ValidationError):
        EconomicRationale(
            mechanism="   ",
            why_edge_exists="Impatient demand pays spread and impact to move inventory",
            other_side="Noise traders demanding immediacy on the tape",
            expected_regime="trend-up moderate volatility",
            falsification_criterion="median OOS after costs <= 0 or PBO > 0.50",
        )
    with pytest.raises(ValidationError):
        HypothesisProposed.model_validate(
            {
                "hypothesis_id": "h",
                "config_id": "c",
                "trial_id": 1,
                "agent_id": "hypothesis_agent",
                "generator_id": "noise",
                "kind": "noise",
                "instrument": "MES",
                "seed": 1,
                "n_obs": 360,
                "mu": 0.0,
                "sigma": 0.01,
                "planted": False,
                "proposed_quantity": 1.0,
                "proposed_price": 5000.0,
                "proposed_notional": 5000.0,
            }
        )


@pytest.mark.unit
def test_events_are_frozen_versioned_and_forbid_extras() -> None:
    hyp = HypothesisProposed(
        hypothesis_id="hyp-1",
        config_id="c1",
        trial_id=1,
        agent_id="hypothesis_agent",
        generator_id="noise",
        kind="noise",
        instrument="MES",
        seed=1,
        n_obs=360,
        mu=0.0,
        sigma=0.01,
        planted=False,
        proposed_quantity=1.0,
        proposed_price=5000.0,
        proposed_notional=5000.0,
        rationale=_rationale(),
    )
    assert hyp.schema_version == HYPOTHESIS_SCHEMA_VERSION
    with pytest.raises(ValidationError):
        hyp.model_validate({**hyp.model_dump(), "extra": 1})
    with pytest.raises(Exception):
        hyp.hypothesis_id = "mutated"  # type: ignore[misc]

    result = ValidationResult(
        hypothesis_id="hyp-1",
        config_id="c1",
        trial_id=2,
        agent_id="validation_agent",
        passed=False,
        reject_reasons=("dsr_below_threshold",),
        oos_distribution=OOSDistributionPayload(
            values=(0.1, -0.2, 0.0, 0.05, 0.02, -0.01),
            median=0.01,
            mean=0.0,
            stdev=0.1,
            worst=-0.2,
            best=0.1,
            pct_positive=0.5,
        ),
        dsr=DSRPayload(
            probability=0.4,
            observed_sr=0.01,
            expected_max_sr=0.2,
            sr_standard_error=0.05,
            n_trials=5,
            n_observations=240,
            skew=0.0,
            kurtosis=3.0,
            formulation="bailey_lopez_de_prado_2014",
        ),
        pbo=PBOPayload(
            pbo=0.6,
            n_slices=8,
            n_combinations=70,
            n_configs=5,
            n_below_median=40,
            formulation="cscv_logit_bailey_2014",
            logit_mean=-0.1,
        ),
        wfe=WFEPayload(
            wfe=0.2,
            mean_is_sharpe=0.4,
            mean_oos_sharpe=0.08,
            n_windows=6,
            mode="rolling",
            parameter_stability=0.1,
        ),
        regimes=RegimePayload(
            vol_high_sharpe=0.0,
            vol_low_sharpe=0.0,
            trend_up_sharpe=0.0,
            trend_down_sharpe=0.0,
            robustness=0.0,
        ),
        n_oos_windows=6,
        median_oos_after_costs=-0.01,
        report_sha256="a" * 64,
        provenance_mac="b" * 64,
    )
    assert result.schema_version == VALIDATION_SCHEMA_VERSION
    assert result.oos_distribution.values
    assert result.dsr.n_trials == 5
    assert result.pbo.pbo == pytest.approx(0.6)
    assert result.wfe.n_windows == 6
    assert result.reject_reasons == ("dsr_below_threshold",)

    cand = PromotionCandidate(
        hypothesis_id="hyp-1",
        config_id="c1",
        trial_id=2,
        agent_id="promotion_agent",
        instrument="MES",
        decision_kind="scaled",
        scaled=True,
        quantity=2.0,
        notional=10_000.0,
        risk_reason="max_position_pct",
        validation_report_sha256="a" * 64,
        validation_mac="b" * 64,
        issue_mac="c" * 64,
    )
    assert cand.schema_version == PROMOTION_SCHEMA_VERSION
    with pytest.raises(ValidationError):
        PromotionCandidate.model_validate({**cand.model_dump(), "decision_kind": "rejected"})
