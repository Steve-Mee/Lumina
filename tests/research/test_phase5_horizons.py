"""Two-horizon decay, material breaks, and vol-regime FAR classification."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from lumina_research.monitoring.acceptance import (
    FAR_HIGH_VOL_MAX,
    FAR_HIGH_VOL_TARGET,
    HIGH_VOL_VIX,
    MEDIUM_WINDOW,
    TTD_MAX_TRADING_DAYS,
    TTD_MEDIUM_MAX_TRADING_DAYS,
)
from lumina_research.monitoring.campaign import DEFAULT_CAMPAIGN_SEEDS as PHASE4_SEEDS
from lumina_research.monitoring.config import load_default_config
from lumina_research.monitoring.horizons import combined_assessment
from lumina_research.monitoring.material import assess_material
from lumina_research.monitoring.types import ContinuityRefused
from lumina_research.monitoring.vol_regime import classify_vol_regime, realized_vol, trailing_percentile
from lumina_research.proof.independent import (
    INDEPENDENT_SEEDS,
    assert_independent_seeds,
    decaying_kind,
    healthy_kind,
    path_for,
)
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_independent_seeds_do_not_overlap_phase4() -> None:
    assert_independent_seeds(INDEPENDENT_SEEDS)
    assert set(INDEPENDENT_SEEDS).isdisjoint(set(PHASE4_SEEDS))
    with pytest.raises(ContinuityRefused, match="overlap"):
        assert_independent_seeds(PHASE4_SEEDS)


@pytest.mark.unit
def test_unknown_kind_and_slow_ramp_refused() -> None:
    rng = random.Random(1)
    with pytest.raises(ContinuityRefused, match="unknown"):
        path_for("gaussian_phase4", rng, oos_mean=0.7, oos_stdev=0.05, n=10, decay_start=3)
    with pytest.raises(ContinuityRefused, match="unknown"):
        decaying_kind("nope")
    assert decaying_kind("material_break") is True
    assert decaying_kind("slow_gradual_45") is True
    assert healthy_kind("healthy_laplace") == "healthy"
    assert healthy_kind("high_vol_mixture") == "high_vol"


@pytest.mark.unit
def test_vix_and_realized_vol_classify_high() -> None:
    quiet = tuple(0.70 + 0.001 * i for i in range(80))
    assert classify_vol_regime(quiet, vix=10.0) == "normal"
    assert classify_vol_regime(quiet, vix=HIGH_VOL_VIX + 0.1) == "high_vol"
    with pytest.raises(ContinuityRefused):
        classify_vol_regime(quiet, vix=-1.0)
    loud = tuple(1.0 for _ in range(50)) + tuple(20.0 + float(index) for index in range(30))
    assert classify_vol_regime(loud, instrument="ES") == "high_vol"
    assert realized_vol(quiet, window=20) is not None
    assert trailing_percentile((1.0, 2.0, 3.0, 4.0), pct=0.75) == 3.0
    assert trailing_percentile((), pct=0.75) is None


@pytest.mark.unit
def test_material_break_flags_ic_and_drawdown() -> None:
    cfg = load_default_config()
    oos = (0.70, 0.72, 0.74, 0.76, 0.78, 0.80)
    healthy = tuple(0.75 for _ in range(30))
    quiet = assess_material(healthy, oos, cfg)
    assert quiet.ready is True
    assert quiet.stage == "active"
    broken = tuple(0.75 for _ in range(20)) + tuple(0.20 for _ in range(15))
    hit = assess_material(broken, oos, cfg)
    assert hit.ready is True
    assert hit.severity >= 1


@pytest.mark.unit
def test_medium_window_not_ready_before_40(tmp_path: Path) -> None:
    cfg = load_default_config()
    oos = (0.70, 0.72, 0.74, 0.76, 0.78, 0.80)
    short = tuple(0.75 for _ in range(25))
    combined = combined_assessment(short, oos, cfg)
    assert combined.assessment.window <= MEDIUM_WINDOW
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-m", trial_id=1)
    for _ in range(19):
        runtime.observe("hyp-m", 0.2)
    assert runtime.registry.require("hyp-m").stage == "active"


@pytest.mark.unit
def test_confirm_windows_still_two_on_material(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-c", trial_id=1)
    dropped = 0.10
    for _ in range(20):
        stage = runtime.observe("hyp-c", dropped).stage
    assert stage == "active"
    confirmed = runtime.observe("hyp-c", dropped)
    assert confirmed.stage != "active"


@pytest.mark.unit
def test_high_vol_far_cap_is_not_twelve_percent() -> None:
    assert FAR_HIGH_VOL_MAX == 0.10
    assert FAR_HIGH_VOL_TARGET == 0.08
    assert FAR_HIGH_VOL_MAX < 0.12
    assert TTD_MAX_TRADING_DAYS == 15
    assert TTD_MEDIUM_MAX_TRADING_DAYS == 45
