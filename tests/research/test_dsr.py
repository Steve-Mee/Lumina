"""DSR unit tests against Bailey & López de Prado (2014) closed forms."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.validation.dsr import (
    EULER_MASCHERONI,
    deflated_sharpe_from_moments,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
    sharpe_standard_error,
)
from lumina_research.validation.trial_registry import TrialRegistry

# Independently computed from Φ^{-1} and Euler-Mascheroni (not from our module output).
# Φ^{-1}(0.99) = 2.3263478740408408
# Φ^{-1}(1 - 1/(100 e)) = 2.680210444966887
# (1-γ)*z1 + γ*z2 = 2.5306028932016846
N100_EXPECTED_MAX_SR_UNIT_VARIANCE = 2.5306028932016846
# T=1250, SR=0.1, γ3=-1, γ4=6, N=100 → DSR probability
MOMENTS_DSR_N100 = 0.7939100888623702
# SRE-frontier-style PSR(0): SR=1.16/√12, T=24, γ3=-2.44, γ4=10.16, N=1
PSR_EXAMPLE = 0.8676119727397289


@pytest.mark.unit
def test_expected_max_sr_n100_matches_paper_formula() -> None:
    assert EULER_MASCHERONI == pytest.approx(0.5772156649015329, rel=0, abs=1e-15)
    got = expected_max_sharpe(n_trials=100, sr_std=1.0, sr_mean=0.0)
    assert got == pytest.approx(N100_EXPECTED_MAX_SR_UNIT_VARIANCE, rel=0, abs=1e-12)


@pytest.mark.unit
def test_n1_has_no_selection_bias() -> None:
    assert expected_max_sharpe(n_trials=1, sr_std=0.2, sr_mean=0.0) == 0.0


@pytest.mark.unit
def test_dsr_from_moments_against_closed_form(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "audit.jsonl")
    for index in range(100):
        registry.record(config_id=f"t{index}", agent_id="tester", metrics={"sr": 0.0})
    snapshot = deflated_sharpe_from_moments(
        sr=0.1,
        n_observations=1250,
        skew=-1.0,
        kurtosis=6.0,
        registry=registry,
    )
    assert snapshot.n_trials == 100
    assert snapshot.formulation == "bailey_lopez_de_prado_2014"
    assert snapshot.probability == pytest.approx(MOMENTS_DSR_N100, rel=0, abs=1e-12)


@pytest.mark.unit
def test_psr_zero_benchmark_reference(tmp_path: Path) -> None:
    sr = 1.16 / (12.0**0.5)
    psr = probabilistic_sharpe_ratio(sr=sr, sr_star=0.0, n_observations=24, skew=-2.44, kurtosis=10.16)
    assert psr == pytest.approx(PSR_EXAMPLE, rel=0, abs=1e-12)
    registry = TrialRegistry(tmp_path / "audit.jsonl")
    registry.record(config_id="only", agent_id="tester", metrics={})
    dsr = deflated_sharpe_from_moments(
        sr=sr,
        n_observations=24,
        skew=-2.44,
        kurtosis=10.16,
        registry=registry,
    )
    assert dsr.n_trials == 1
    assert dsr.probability == pytest.approx(PSR_EXAMPLE, rel=0, abs=1e-12)


@pytest.mark.unit
def test_n_trials_cannot_be_passed_lower(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "audit.jsonl")
    registry.record(config_id="a", agent_id="tester", metrics={})
    registry.record(config_id="b", agent_id="tester", metrics={})
    with pytest.raises(TypeError, match="n_trials"):
        deflated_sharpe_ratio([0.01, 0.02, -0.01, 0.03], registry=registry, n_trials=1)
    se = sharpe_standard_error(sr=0.1, n_observations=100, skew=0.0, kurtosis=3.0)
    assert se > 0.0


@pytest.mark.unit
def test_empty_registry_refuses_dsr(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "audit.jsonl")
    with pytest.raises(Exception, match="registry"):
        deflated_sharpe_from_moments(sr=0.2, n_observations=50, skew=0.0, kurtosis=3.0, registry=registry)
