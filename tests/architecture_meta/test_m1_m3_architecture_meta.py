"""M1–M3: architecture meta scanner/pipeline, meta-agent approval, evolution axes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lumina_core.architecture_meta.controller import (
    ArchitectureMetaController,
    ArchMutationProposal,
    ArchMutationType,
)
from lumina_core.architecture_meta.evolution_axes import (
    axis_allowed_for_mode,
    evolution_axes_snapshot,
)
from lumina_core.architecture_meta.journal import append_architecture_event, tail_architecture_events
from lumina_core.architecture_meta.meta_agent_approval import (
    meta_agent_approval_snapshot,
    meta_agent_may_auto_approve,
)
from lumina_core.architecture_meta.pipeline import (
    architecture_meta_status,
    proposal_is_actionable,
    run_architecture_meta_dry_cycle,
)
from lumina_core.architecture_meta.scanner import scan_architecture_counts


@pytest.mark.unit
def test_scanner_counts_repo() -> None:
    counts = scan_architecture_counts()
    assert counts.module_count > 0
    assert counts.total_core_loc > 0
    assert counts.god_file_count >= 0
    assert isinstance(counts.god_files, list)


@pytest.mark.unit
def test_dry_cycle_never_auto_applies(tmp_path: Path) -> None:
    result = run_architecture_meta_dry_cycle(
        enabled=True,
        workspace_root=tmp_path,
        write_journal=True,
        capital_mode="sim",
    )
    assert result["auto_apply"] is False
    assert "never auto-apply" in result["apply_blocked_reason"].lower() or "APPROVED" in result[
        "apply_blocked_reason"
    ]
    assert result["schema"] == "architecture_meta_cycle_v1"
    assert "snapshot" in result
    assert result.get("journal_written") is True
    events = tail_architecture_events(workspace_root=tmp_path)
    assert events
    assert events[-1].get("action") == "dry_cycle"


@pytest.mark.unit
def test_inventory_stubs_not_actionable() -> None:
    ctrl = ArchitectureMetaController(enabled=True, max_proposals_per_scan=3)
    snap = ctrl.build_snapshot(
        god_file_count=2,
        boundary_violations=1,
        pydantic_model_count=5,
        ruff_violations_core=0,
        avg_module_loc=500,
        todo_density=1.0,
        total_core_loc=10000,
    )
    props = ctrl.propose(snap)
    assert props  # inventory stubs may still appear
    for p in props:
        assert not proposal_is_actionable(p)
        assert ctrl.should_promote_candidate(p, MagicMock(passed=True, score_delta=1.0)) is False


@pytest.mark.unit
def test_should_promote_requires_real_diff() -> None:
    ctrl = ArchitectureMetaController(enabled=True, min_health_delta=0.1)
    good = ArchMutationProposal(
        proposal_id="x",
        mutation_type=ArchMutationType.EXTRACT_PURE_HELPER,
        target_file="lumina_core/safety/constitutional_guard.py",
        description="real",
        diff="--- a\n+++ b\n@@\n+def helper():\n+    return 1\n",
        expected_delta=0.2,
        rationale="r",
        before_score=5.0,
        constitution_passed=True,
    )
    assert ctrl.should_promote_candidate(good, MagicMock(passed=True, score_delta=0.25)) is True
    bad = ArchMutationProposal(
        proposal_id="y",
        mutation_type=ArchMutationType.SIMPLIFY_GUARD,
        target_file="lumina_core/safety/constitutional_guard.py",
        description="stub",
        diff="",
        expected_delta=0.2,
        rationale="r",
        before_score=5.0,
        constitution_passed=True,
    )
    assert ctrl.should_promote_candidate(bad, MagicMock(passed=True, score_delta=0.25)) is False


@pytest.mark.unit
def test_meta_agent_never_auto_real_or_architecture() -> None:
    arch = meta_agent_may_auto_approve("architecture_promotion", capital_mode="sim")
    assert arch["allowed"] is False
    assert "architecture" in arch["reason"] or arch.get("requires_human")

    real = meta_agent_may_auto_approve("twin_judgment", capital_mode="real")
    assert real["allowed"] is False
    assert real["real_like"] is True

    real_cap = meta_agent_may_auto_approve("real_capital_mode", capital_mode="real")
    assert real_cap["allowed"] is False
    real_human = meta_agent_may_auto_approve(
        "real_capital_mode", capital_mode="real", human_approved=True
    )
    assert real_human["allowed"] is True


@pytest.mark.unit
def test_meta_agent_approval_snapshot() -> None:
    snap = meta_agent_approval_snapshot(capital_mode="sim")
    assert snap["schema"] == "meta_agent_approval_v1"
    assert len(snap["surfaces"]) >= 5
    ids = {s["surface_id"] for s in snap["surfaces"]}
    assert "architecture_promotion" in ids
    assert "real_capital_mode" in ids


@pytest.mark.unit
def test_evolution_axes_real_blocks_auto() -> None:
    arch = axis_allowed_for_mode("architecture", capital_mode="sim")
    assert arch["allowed"] is True
    assert arch["auto"] is False

    dna_real = axis_allowed_for_mode("dna_json", capital_mode="real")
    assert dna_real.get("auto") is False

    board = evolution_axes_snapshot(capital_mode="sim")
    assert board["schema"] == "evolution_axes_v1"
    assert board["meta_agent_approval"]["schema"] == "meta_agent_approval_v1"
    assert any(a["axis_id"] == "architecture" for a in board["axes"])


@pytest.mark.unit
def test_architecture_meta_status_embeds_m2_m3(tmp_path: Path) -> None:
    st = architecture_meta_status(
        workspace_root=tmp_path,
        capital_mode="sim",
        enabled=False,
    )
    assert st["schema"] == "architecture_meta_status_v1"
    assert st["auto_apply"] is False
    assert st["require_human_approval"] is True
    assert "evolution_axes" in st
    assert "meta_agent_approval" in st


@pytest.mark.unit
def test_journal_blocks_apply_action(tmp_path: Path) -> None:
    p = append_architecture_event({"action": "apply", "foo": 1}, workspace_root=tmp_path)
    assert p.is_file()
    events = tail_architecture_events(workspace_root=tmp_path)
    assert events[-1]["action"] == "apply_blocked"
