"""H2: REAL multi-gate non-bypassable; Twin judgment inside gates only."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.maturity.maturation_progress import (
    REAL_ELIGIBILITY_MILESTONES,
    record_maturation_milestone,
)
from lumina_core.risk.real_multi_gate import (
    assert_twin_cannot_authorize_real_mode,
    evaluate_real_capital_readiness,
    real_dna_promotion_allowed,
    real_mode_switch_allowed,
    twin_judgment_subordinate_to_real_gates,
)


@pytest.mark.unit
def test_twin_full_auto_cannot_authorize_real_capital() -> None:
    result = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode="full_auto",
        capital_mode="real",
    )
    assert result["executable"] is False
    assert result["effective_recommendation"] is False
    assert result["real_capital_floor"] is True
    assert_twin_cannot_authorize_real_mode(twin_full_auto=True, twin_recommendation=True)


@pytest.mark.unit
def test_twin_full_auto_can_execute_judgment_in_sim() -> None:
    result = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode="full_auto",
        capital_mode="sim",
    )
    assert result["effective_recommendation"] is True
    assert result["executable"] is True
    assert result["real_capital_floor"] is False


@pytest.mark.unit
def test_real_dna_promotion_requires_human() -> None:
    ok, reason = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=False,
        explicit_human_approval=True,
        base_promoted=True,
        has_approval_signatures=True,
    )
    assert ok is False
    assert reason == "real_human_approval_mandatory"

    ok2, reason2 = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=True,
        explicit_human_approval=False,
        base_promoted=True,
        has_approval_signatures=False,
    )
    assert ok2 is False
    assert "explicit_human" in reason2 or "signatures" in reason2

    ok3, reason3 = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=True,
        explicit_human_approval=False,
        base_promoted=True,
        has_approval_signatures=True,
    )
    assert ok3 is True
    assert "approval_chain" in reason3


@pytest.mark.unit
def test_real_mode_switch_requires_human_and_maturation(tmp_path: Path) -> None:
    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
        side_effect=lambda root: None,
    ), patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ):
        ok, blockers = real_mode_switch_allowed(tmp_path)
    assert ok is False
    assert any("approval" in b.lower() or "Birth" in b or "Evolution" in b for b in blockers)

    for mid in REAL_ELIGIBILITY_MILESTONES:
        record_maturation_milestone(tmp_path, mid)
    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
        side_effect=lambda root: __import__(
            "lumina_core.maturity.maturation_progress", fromlist=["load_maturation_progress"]
        ).load_maturation_progress(root),
    ), patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ):
        ok2, blockers2 = real_mode_switch_allowed(tmp_path)
        assert ok2 is False
        assert any("approval" in b.lower() for b in blockers2)

        record_maturation_milestone(tmp_path, "human_real_approval")
        ok3, blockers3 = real_mode_switch_allowed(tmp_path)
        assert ok3 is True
        assert blockers3 == []


@pytest.mark.unit
def test_readiness_snapshot_flags_twin_cannot_bypass(tmp_path: Path) -> None:
    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
        side_effect=lambda root: None,
    ), patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ):
        snap = evaluate_real_capital_readiness(tmp_path)
    assert snap["twin_can_bypass"] is False
    assert snap["policy"]["human_required_for_real_mode"] is True
    assert snap["ready_for_real_capital"] is False


@pytest.mark.unit
def test_real_multi_gate_dry_run_invariants(tmp_path: Path) -> None:
    from lumina_core.risk.real_multi_gate import run_real_multi_gate_dry_run

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
        side_effect=lambda root: None,
    ), patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ):
        dry = run_real_multi_gate_dry_run(tmp_path)
    assert dry["schema"] == "real_multi_gate_dry_run_v1"
    assert dry["ok"] is True  # invariants hold
    assert dry["ready_for_real_capital"] is False  # empty workspace not ready
    assert dry["invariants"]["twin_cannot_authorize_real"] is True
    assert dry["invariants"]["real_dna_requires_human"] is True
    assert dry["policy"]["never_arms_real"] is True
    assert dry["twin_floor"]["real_capital_floor"] is True
