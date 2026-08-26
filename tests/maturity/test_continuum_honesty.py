"""M6: continuum / READY / REAL honesty board."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import mark_phase_completed
from lumina_core.maturity.continuum_honesty import continuum_honesty_snapshot
from lumina_core.maturity.maturation_progress import (
    MaturationProgress,
    MaturationPhase,
    save_maturation_progress,
)
from lumina_core.maturity.phase_specs import hub_payload


@pytest.mark.unit
def test_honesty_completed_flag_alone_is_not_birth_exit(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_birth_completed.flag").write_text("ok\n", encoding="utf-8")
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=["setup"])
    snap = continuum_honesty_snapshot(tmp_path)
    assert snap["schema"] == "continuum_honesty_v1"
    assert snap["birth_exit"]["exited"] is False
    assert snap["ready_for_real"]["ready"] is False
    assert any("Birth" in s or "birth" in s.lower() for s in snap["next_honest_steps"]) or snap[
        "next_honest_steps"
    ]


@pytest.mark.unit
def test_honesty_ready_not_real_eligible(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    progress = MaturationProgress(
        current_phase=MaturationPhase.APPRENTICESHIP,
        milestones_reached=["sim_real_guard_stable"],
    )
    save_maturation_progress(tmp_path, progress)
    for phase in ("genesis", "birth", "awakening", "playground"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    snap = continuum_honesty_snapshot(tmp_path)
    assert snap["ready_for_real"]["ready"] is True
    assert snap["real_eligible"]["eligible"] is False
    assert any("READY_FOR_REAL" in w for w in snap["conflation_warnings"])


@pytest.mark.unit
def test_honesty_soft_complete_flag(tmp_path: Path) -> None:
    mark_phase_completed(
        tmp_path,
        "genesis",
        learned={"soft_complete": True},
        exit_proofs=["soft"],
    )
    snap = continuum_honesty_snapshot(tmp_path)
    assert any(f.get("phase") == "genesis" for f in snap["soft_complete_flags"])
    assert snap["honesty_ok"] is False


@pytest.mark.unit
def test_hub_payload_embeds_honesty(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    hub = hub_payload(tmp_path)
    assert "honesty" in hub
    assert hub["honesty"].get("schema") == "continuum_honesty_v1"
    assert "next_honest_steps" in hub
    assert "real_requires_human" in hub
    assert hub["real_requires_human"] is True


@pytest.mark.unit
def test_ready_from_stability_report_file(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "sim_stability_report.json").write_text(
        json.dumps({"READY_FOR_REAL": True, "consecutive_green_days": 5}),
        encoding="utf-8",
    )
    snap = continuum_honesty_snapshot(tmp_path)
    assert snap["ready_for_real"]["ready"] is True
    assert snap["ready_for_real"]["stability_report"].get("READY_FOR_REAL") is True
