"""Proving Ground cinematic surface — hub until started, cinematic while live/incomplete."""
from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.continuum import mark_phase_completed, mark_phase_failed, mark_phase_running
from lumina_core.maturity.proving_ground.progress import save_proving_ground_progress
from lumina_core.maturity.proving_ground.surface import proving_ground_cinematic_wanted
from lumina_launcher.core.onboarding import resolve_app_surface


def _ready_kwargs(tmp_path: Path) -> dict[str, object]:
    return {
        "setup_complete": True,
        "birth_status": "completed",
        "artifacts_ok": True,
        "birth_exit_ok": True,
        "backend_reachable": True,
        "required_steps": ["welcome"],
        "workspace_root": tmp_path,
    }


def _ladder(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])


@pytest.mark.unit
def test_never_started_stays_hub(tmp_path: Path) -> None:
    _ladder(tmp_path)
    wanted, why = proving_ground_cinematic_wanted(tmp_path)
    assert wanted is False
    assert why == "proving_ground_pending"
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "hub"
    assert reason == "maturation_hub"


@pytest.mark.unit
def test_running_opens_cinematic(tmp_path: Path) -> None:
    _ladder(tmp_path)
    mark_phase_running(tmp_path, "proving_ground")
    wanted, why = proving_ground_cinematic_wanted(tmp_path)
    assert wanted is True
    assert why == "proving_ground_running"
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "proving_ground"
    assert reason == "proving_ground_running"


@pytest.mark.unit
def test_failed_stays_cinematic_until_complete(tmp_path: Path) -> None:
    _ladder(tmp_path)
    mark_phase_failed(tmp_path, "proving_ground", error="n_G=40 < 150")
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "proving_ground"
    assert reason == "proving_ground_incomplete"


@pytest.mark.unit
def test_progress_file_opens_cinematic(tmp_path: Path) -> None:
    _ladder(tmp_path)
    save_proving_ground_progress(tmp_path, {"n_g": 40})
    wanted, why = proving_ground_cinematic_wanted(tmp_path)
    assert wanted is True
    assert why == "proving_ground_incomplete"


@pytest.mark.unit
def test_completed_returns_hub(tmp_path: Path) -> None:
    _ladder(tmp_path)
    mark_phase_completed(tmp_path, "proving_ground", learned={}, exit_proofs=["certificate_oos_walls"])
    wanted, _ = proving_ground_cinematic_wanted(tmp_path)
    assert wanted is False
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "hub"
    assert reason == "maturation_hub"
