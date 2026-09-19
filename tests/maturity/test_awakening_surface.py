"""Awakening cinematic surface — hub until started, cinematic while live/incomplete."""
from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.awakening.progress import save_awakening_progress
from lumina_core.maturity.awakening.surface import awakening_cinematic_wanted
from lumina_core.maturity.continuum import mark_phase_completed, mark_phase_failed, mark_phase_running
from lumina_launcher.core.onboarding import resolve_app_surface


def _birth_ready_kwargs(tmp_path: Path) -> dict[str, object]:
    return {
        "setup_complete": True,
        "birth_status": "completed",
        "artifacts_ok": True,
        "birth_exit_ok": True,
        "backend_reachable": True,
        "required_steps": ["welcome"],
        "workspace_root": tmp_path,
    }


@pytest.mark.unit
def test_never_started_stays_hub(tmp_path: Path) -> None:
    wanted, why = awakening_cinematic_wanted(tmp_path)
    assert wanted is False
    assert why == "awakening_pending"
    surface, reason = resolve_app_surface(**_birth_ready_kwargs(tmp_path))
    assert surface == "hub"
    assert reason == "maturation_hub"


@pytest.mark.unit
def test_running_opens_cinematic(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_running(tmp_path, "awakening")
    wanted, why = awakening_cinematic_wanted(tmp_path)
    assert wanted is True
    assert why == "awakening_running"
    surface, reason = resolve_app_surface(**_birth_ready_kwargs(tmp_path))
    assert surface == "awakening"
    assert reason == "awakening_running"


@pytest.mark.unit
def test_failed_stays_cinematic_until_complete(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_failed(tmp_path, "awakening", error="n_B=133 < 500")
    surface, reason = resolve_app_surface(**_birth_ready_kwargs(tmp_path))
    assert surface == "awakening"
    assert reason == "awakening_incomplete"


@pytest.mark.unit
def test_progress_file_opens_cinematic(tmp_path: Path) -> None:
    save_awakening_progress(tmp_path, {"n_b": 133, "cycle": 2})
    wanted, why = awakening_cinematic_wanted(tmp_path)
    assert wanted is True
    assert why == "awakening_incomplete"


@pytest.mark.unit
def test_completed_returns_hub(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=["evolution_proof_passed"])
    wanted, _ = awakening_cinematic_wanted(tmp_path)
    assert wanted is False
    surface, reason = resolve_app_surface(**_birth_ready_kwargs(tmp_path))
    assert surface == "hub"
    assert reason == "maturation_hub"
