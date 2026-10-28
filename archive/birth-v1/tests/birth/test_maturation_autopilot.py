"""Maturation autopilot tick tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.maturity.autopilot import run_maturation_autopilot_tick


@pytest.mark.unit
def test_autopilot_tick_without_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    tick = run_maturation_autopilot_tick(tmp_path)
    assert "milestones_reached" in tick
    assert tick["real_eligible"] is False


@pytest.mark.unit
def test_shadow_gate_from_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    state = tmp_path / "state"
    state.mkdir(parents=True)
    audit = state / "promotion_gate_audit.jsonl"
    audit.write_text(
        json.dumps({"promoted": True, "mode": "sim", "dna_hash": "abc"}) + "\n",
        encoding="utf-8",
    )
    (state / "lumina_maturity_progress.json").write_text(
        json.dumps(
            {
                "current_phase": "apprenticeship",
                "milestones_reached": [
                    "birth_certificate_issued",
                    "evolution_proof_passed",
                    "sim_real_guard_stable",
                ],
            }
        ),
        encoding="utf-8",
    )
    tick = run_maturation_autopilot_tick(tmp_path)
    assert tick.get("shadow_gate_passed") is True