"""R2 cadence aggregator tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.unit
def test_cadence_report_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "phase": "curriculum_learning",
                "needs_attention": False,
                "constitution_violations": 0,
                "requested_days": 90,
                "actual_calendar_days": 90,
                "data_manifest": {"requested_days": 90, "days_loaded": 90},
            }
        ),
        encoding="utf-8",
    )
    from scripts.validation.birth_zero_human_cadence import _run_report

    report = _run_report(tmp_path, fabric_mock=False)
    assert report["schema"] == "birth_zero_human_cadence_v1"
    assert "residuals" in report
    assert "perfect_birth" in report
    assert "phase2" in report
    assert "training_window_sla" in report
    assert report["training_window_sla"]["ok"] is True
    assert report["policy"]["never_auto_real"] is True


@pytest.mark.unit
def test_cadence_flags_silent_stall(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "phase": "stage_stalled",
                "needs_attention": False,
                "terminal_stall_reason": "plateau_evolution_exhausted",
                "recovery": {
                    "schema": "recovery_compress_v1",
                    "active": "terminal_stall",
                    "productive": False,
                    "flags": {
                        "needs_attention": False,
                        "terminal_stall_reason": "plateau_evolution_exhausted",
                    },
                    "next_action": "expand_data_or_wipe_genesis",
                },
            }
        ),
        encoding="utf-8",
    )
    from scripts.validation.birth_zero_human_cadence import _run_report

    report = _run_report(tmp_path, fabric_mock=False)
    assert report["progress_attention"]["silent_stall"] is True
    assert report["ok"] is False
