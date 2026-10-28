"""Stage-2 min_net oracle floor is stage-scoped (not Stage-1 starve)."""

from __future__ import annotations

from pathlib import Path


def test_mine_inject_source_scopes_stage2_min_net() -> None:
    src = Path("lumina_core/birth/stage_loop_data_cache.py").read_text(encoding="utf-8")
    assert "STAGE2_RANGE" in src
    assert "stage2_min_net_oracle_pnl" in src
    assert "min_net = 0.01" in src


def test_swarm_defer_passes_edge_vs_random() -> None:
    src = Path("lumina_core/birth/plateau_evolution_detect.py").read_text(encoding="utf-8")
    assert "edge_vs_random=edge_vr_f" in src
    assert "beat_random" in src
