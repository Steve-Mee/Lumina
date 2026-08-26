"""Pass-vector is the Stage-2 multi-blocker meta controller."""

from __future__ import annotations

import pytest

from lumina_core.birth.stage2_pass_vector import (
    compute_stage2_pass_vector,
    meta_fields_from_pass_vector,
)


@pytest.mark.unit
def test_meta_fields_suppress_churn() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.25,
        expectancy=-0.22,
        edge_vs_random=-0.10,
    )
    fields = meta_fields_from_pass_vector(pv, base_explore_steps=2000, exploration_steps=2000)
    assert fields["pass_vector_action"] == "suppress_churn"
    assert fields["primary"] == "explore_reduce"
    assert fields["mine"] is True
    assert "explore_boost" not in str(fields.get("secondary"))


@pytest.mark.unit
def test_meta_fields_selective_open() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.90,
        expectancy=-0.20,
        edge_vs_random=-0.05,
    )
    fields = meta_fields_from_pass_vector(pv)
    assert fields["pass_vector_action"] == "selective_quality_open"
    assert fields["primary"] == "pattern_inject"
    assert fields["mine"] is True


@pytest.mark.unit
def test_meta_fields_beat_random() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.50,
        expectancy=-0.10,
        exp_floor=-0.15,
        edge_vs_random=-0.12,
    )
    fields = meta_fields_from_pass_vector(pv, remediation_step=2)
    assert fields["pass_vector_action"] == "beat_random_quality"
    assert "beat_random" in str(fields.get("rationale") or "") or fields.get("mine")


@pytest.mark.unit
def test_meta_fields_hold_when_clear() -> None:
    pv = compute_stage2_pass_vector(
        range_flat_ratio=0.45,
        expectancy=-0.10,
        edge_vs_random=0.02,
    )
    fields = meta_fields_from_pass_vector(pv)
    assert fields["primary"] == "hold"
    assert fields["pass_vector_action"] == "hold_pass_path"
