"""Basic tests for ArchitectureMetaController (pure logic)."""

from __future__ import annotations


from lumina_core.architecture_meta.controller import (
    ArchitectureMetaController,
    ArchMutationType,
    compute_health_score_from_counts,
)


def test_disabled_returns_no_proposals():
    ctrl = ArchitectureMetaController(enabled=False)
    snap = ctrl.build_snapshot(
        god_file_count=3,
        boundary_violations=1,
        pydantic_model_count=10,
        ruff_violations_core=5,
        avg_module_loc=420.0,
        todo_density=0.8,
        total_core_loc=12000,
    )
    assert not ctrl.is_enabled
    assert ctrl.propose(snap) == []


def test_enabled_produces_proposals_and_score():
    ctrl = ArchitectureMetaController(enabled=True, max_proposals_per_scan=2, min_health_delta=0.1)
    snap = ctrl.build_snapshot(
        god_file_count=2,
        boundary_violations=0,
        pydantic_model_count=5,
        ruff_violations_core=2,
        avg_module_loc=550,
        todo_density=1.2,
        total_core_loc=18000,
        timestamp="2026-07-13",
    )
    assert snap.arch_health_score < 8.0
    props = ctrl.propose(snap)
    assert len(props) >= 1
    assert all(p.expected_delta >= 0.1 for p in props)
    assert any(p.mutation_type in (ArchMutationType.EXTRACT_PURE_HELPER, ArchMutationType.INTRODUCE_TYPED_MODEL) for p in props)


def test_health_score_is_deterministic_and_bounded():
    s1 = compute_health_score_from_counts(god_file_count=0, boundary_violations=0, pydantic_model_count=50, ruff_violations_core=0, avg_module_loc=200, todo_density=0)
    s2 = compute_health_score_from_counts(god_file_count=5, boundary_violations=3, pydantic_model_count=5, ruff_violations_core=40, avg_module_loc=600, todo_density=3)
    assert 0.0 <= s1 <= 10.0
    assert 0.0 <= s2 <= 10.0
    assert s1 > s2  # better inputs -> higher score


def test_metrics_and_format():
    ctrl = ArchitectureMetaController(enabled=True)
    snap = ctrl.build_snapshot(god_file_count=1, boundary_violations=0, pydantic_model_count=10, ruff_violations_core=0, avg_module_loc=300, todo_density=0, total_core_loc=5000)
    props = ctrl.propose(snap)
    log = ctrl.format_decision_log(props[0] if props else None)
    assert "arch_meta" in log
    m = ctrl.metrics_payload()
    assert "arch_meta_proposals_generated" in m
