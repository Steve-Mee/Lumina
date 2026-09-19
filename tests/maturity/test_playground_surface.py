"""Playground habitat surface — hub until started, deck habitat while live/incomplete."""
from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.continuum import mark_phase_completed, mark_phase_failed, mark_phase_running
from lumina_core.maturity.playground.progress import save_playground_progress
from lumina_core.maturity.playground.surface import playground_habitat_wanted
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


def _awakening_done(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=["x"])


@pytest.mark.unit
def test_never_started_stays_hub(tmp_path: Path) -> None:
    _awakening_done(tmp_path)
    wanted, why = playground_habitat_wanted(tmp_path)
    assert wanted is False
    assert why == "playground_pending"
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "hub"
    assert reason == "maturation_hub"


@pytest.mark.unit
def test_running_opens_habitat(tmp_path: Path) -> None:
    _awakening_done(tmp_path)
    mark_phase_running(tmp_path, "playground")
    wanted, why = playground_habitat_wanted(tmp_path)
    assert wanted is True
    assert why == "playground_running"
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "playground"
    assert reason == "playground_running"


@pytest.mark.unit
def test_failed_stays_habitat_until_complete(tmp_path: Path) -> None:
    _awakening_done(tmp_path)
    mark_phase_failed(tmp_path, "playground", error="n_P=12 < 150")
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "playground"
    assert reason == "playground_incomplete"


@pytest.mark.unit
def test_progress_file_opens_habitat(tmp_path: Path) -> None:
    _awakening_done(tmp_path)
    save_playground_progress(tmp_path, {"n_p": 12})
    wanted, why = playground_habitat_wanted(tmp_path)
    assert wanted is True
    assert why == "playground_incomplete"


@pytest.mark.unit
def test_completed_returns_hub(tmp_path: Path) -> None:
    _awakening_done(tmp_path)
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=["x"])
    wanted, _ = playground_habitat_wanted(tmp_path)
    assert wanted is False
    surface, reason = resolve_app_surface(**_ready_kwargs(tmp_path))
    assert surface == "hub"
    assert reason == "maturation_hub"
