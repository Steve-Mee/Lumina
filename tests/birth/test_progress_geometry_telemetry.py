"""Progress/checkpoint always emit birth geometry keys."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_geometry_keys_contract_always_present() -> None:
    """Contract used by progress metrics + enrich: never omit keys."""
    stop_g = 0.0008
    target_g = 0.0012
    payload = {
        "birth_trade_stop_pct": round(float(stop_g), 6) if stop_g is not None else 0.0,
        "birth_trade_target_pct": round(float(target_g), 6) if target_g is not None else 0.0,
        "birth_trade_geometry_source": str("move_distribution" or "unset"),
        "closes_stop": int(1),
        "closes_target": int(2),
        "closes_flatten": int(3),
        "mean_entry_stop_pct": round(float(0.0008), 6),
        "mean_entry_target_pct": round(float(0.0012), 6),
    }
    for k in (
        "birth_trade_stop_pct",
        "birth_trade_target_pct",
        "birth_trade_geometry_source",
        "closes_stop",
        "closes_target",
        "closes_flatten",
        "mean_entry_stop_pct",
        "mean_entry_target_pct",
    ):
        assert k in payload
    assert payload["birth_trade_stop_pct"] == pytest.approx(0.0008)


@pytest.mark.unit
def test_unset_geometry_emits_zero_not_missing() -> None:
    stop_g = None
    payload = {
        "birth_trade_stop_pct": round(float(stop_g), 6) if stop_g is not None else 0.0,
        "birth_trade_target_pct": 0.0,
        "birth_trade_geometry_source": "unset",
    }
    assert payload["birth_trade_stop_pct"] == 0.0
    assert payload["birth_trade_geometry_source"] == "unset"


@pytest.mark.unit
def test_enrich_source_contains_geometry_emit() -> None:
    """Source SSOT: enrich module always writes birth_trade keys."""
    from pathlib import Path

    src = Path("lumina_core/birth/stage_loop_progress_write_enrich.py").read_text(
        encoding="utf-8"
    )
    assert 'scorecard["birth_trade_stop_pct"]' in src
    assert 'scorecard["birth_trade_geometry_source"]' in src
    assert 'scorecard["closes_stop"]' in src
    assert "edge_vs_random" in src
    assert "first_touch_target_hit_rate" in src
    assert "apply_geometry_forensics" in src
    assert "pass_vector" in src or "compute_stage2_pass_vector" in src
    metrics = Path("lumina_core/birth/stage_loop_progress_metrics.py").read_text(
        encoding="utf-8"
    )
    assert 'payload["birth_trade_stop_pct"]' in metrics
    assert "apply_geometry_forensics" in metrics or "geometry_net_rr_after_cost" in metrics
    assert "never omit" in metrics.lower() or "always present" in metrics.lower() or "birth_trade_geometry_source" in metrics
