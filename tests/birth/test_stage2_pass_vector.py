"""Stage-2 multi-blocker pass vector SSOT."""

from __future__ import annotations

import pytest

from lumina_core.birth.stage2_pass_vector import compute_stage2_pass_vector


@pytest.mark.unit
def test_pass_vector_over_trading_and_anti_edge() -> None:
    """Live stuck case: flat 28%, exp -0.22, edge -0.12."""
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.28,
        expectancy=-0.22,
        exp_floor=-0.15,
        edge_vs_random=-0.12,
    )
    assert pv.occupancy_over_gap == pytest.approx(0.02, abs=1e-6)
    assert pv.occupancy_under_gap == 0.0
    assert pv.exp_gap == pytest.approx(0.07, abs=1e-6)
    assert pv.edge_gap == pytest.approx(0.12, abs=1e-6)
    assert pv.dominant == "mixed_quality"
    assert pv.action == "suppress_churn"
    assert pv.beat_random is False
    assert pv.in_flat_band is False
    fields = pv.as_progress_fields()
    assert fields["pass_vector_dominant"] == "mixed_quality"
    assert fields["pass_vector_edge_gap"] == pytest.approx(0.12, abs=1e-4)


@pytest.mark.unit
def test_pass_vector_under_activity_selective_open() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.92,
        expectancy=-0.20,
        exp_floor=-0.15,
        edge_vs_random=-0.05,
    )
    assert pv.occupancy_under_gap == pytest.approx(0.22, abs=1e-6)
    assert pv.action == "selective_quality_open"
    assert pv.dominant == "mixed_quality"


@pytest.mark.unit
def test_pass_vector_edge_only_beat_random() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.50,
        expectancy=-0.10,  # above floor
        exp_floor=-0.15,
        edge_vs_random=-0.08,
    )
    assert pv.exp_gap == 0.0
    assert pv.edge_gap == pytest.approx(0.08, abs=1e-6)
    assert pv.dominant == "edge"
    assert pv.action == "beat_random_quality"
    assert pv.in_flat_band is True


@pytest.mark.unit
def test_pass_vector_all_clear() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.45,
        expectancy=-0.10,
        exp_floor=-0.15,
        edge_vs_random=0.02,
    )
    assert pv.dominant == "none"
    assert pv.action == "hold_pass_path"
    assert pv.beat_random is True


@pytest.mark.unit
def test_pass_vector_in_band_anti_edge_owns_beat_random() -> None:
    """Live forensics: flat OK + edge < 0 + exp gap → beat_random, not inject flood."""
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.32,
        expectancy=-0.20,
        exp_floor=-0.15,
        edge_vs_random=-0.05,
    )
    assert pv.in_flat_band is True
    assert pv.action == "beat_random_quality"
    assert pv.dominant in ("edge", "mixed_quality")
