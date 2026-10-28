"""DSR unit tests against Bailey & López de Prado (2014) closed forms."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from lumina_research.validation.dsr import (
    DSRError,
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


def _acklam_inv_norm(p: float) -> float:
    """Independent Φ^{-1} (Acklam), not the module's NormalDist."""
    a = (
        -3.969683028665376e01,
        2.209460984245380e02,
        -2.759285104469687e02,
        1.383577509590705e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068071618818e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


@pytest.mark.unit
def test_dsr_matches_independent_mlfinlab_style_formula(tmp_path: Path) -> None:
    import math as math_mod

    gamma = 0.5772156649015328606
    n_trials = 100
    z_hi = _acklam_inv_norm(1.0 - 1.0 / n_trials)
    z_lo = _acklam_inv_norm(1.0 - 1.0 / (n_trials * math_mod.e))
    expected_unit = (1.0 - gamma) * z_hi + gamma * z_lo
    assert expected_max_sharpe(n_trials=n_trials, sr_std=1.0) == pytest.approx(expected_unit, rel=0, abs=1e-8)

    sr, n_obs, skew, kurtosis = 0.1, 1250, -1.0, 6.0
    variance = (1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr) / (n_obs - 1)
    se = math_mod.sqrt(variance)
    sr0 = se * expected_unit
    z_score = (sr - sr0) / se
    independent = 0.5 * (1.0 + math_mod.erf(z_score / math_mod.sqrt(2.0)))
    registry = TrialRegistry(tmp_path / "audit.jsonl")
    for index in range(n_trials):
        registry.record(config_id=f"t{index}", agent_id="tester", metrics={})
    snapshot = deflated_sharpe_from_moments(
        sr=sr, n_observations=n_obs, skew=skew, kurtosis=kurtosis, registry=registry
    )
    assert snapshot.probability == pytest.approx(independent, rel=0, abs=1e-8)


@pytest.mark.unit
def test_negative_sr_variance_is_undefined() -> None:
    with pytest.raises(DSRError, match="non-positive"):
        sharpe_standard_error(sr=2.0, n_observations=100, skew=2.0, kurtosis=3.0)
