"""Living Apprenticeship clock — incomplete is not failed; heartbeat writes."""
from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.apprenticeship.runner import run_apprenticeship_live
from lumina_core.maturity.apprenticeship.surface import apprenticeship_cinematic_wanted
from lumina_core.maturity.continuum import load_continuum, mark_phase_completed


@pytest.mark.unit
def test_live_clock_incomplete_is_not_failed(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening", "playground"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    result = run_apprenticeship_live(
        tmp_path,
        should_stop=lambda: True,
        poll_sec=0.0,
        sleep_fn=lambda _s: None,
    )
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    rec = (load_continuum(tmp_path).get("phase_records") or {}).get("apprenticeship") or {}
    assert rec.get("status") == "running" or rec.get("status") == "incomplete"
    assert rec.get("status") != "failed"


@pytest.mark.unit
def test_heartbeat_writes_activity(tmp_path: Path) -> None:
    from lumina_core.maturity.apprenticeship.progress import load_apprenticeship_progress

    for phase in ("genesis", "birth", "awakening", "playground"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=["x"])
    calls = {"n": 0}

    def stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    run_apprenticeship_live(tmp_path, should_stop=stop, poll_sec=0.0, sleep_fn=lambda _s: None)
    prog = load_apprenticeship_progress(tmp_path)
    assert prog.get("activity") == "session_watch"
    assert prog.get("updated_at")


@pytest.mark.unit
def test_cinematic_wanted_when_running(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=["x"])
    from lumina_core.maturity.continuum import mark_phase_running

    mark_phase_running(tmp_path, "apprenticeship", learned={"status": "starting"})
    wanted, why = apprenticeship_cinematic_wanted(tmp_path)
    assert wanted is True
    assert why == "apprenticeship_running"


@pytest.mark.unit
def test_cinematic_not_wanted_before_start(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=["x"])
    wanted, why = apprenticeship_cinematic_wanted(tmp_path)
    assert wanted is False
    assert why == "apprenticeship_pending"
