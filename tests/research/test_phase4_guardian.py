"""Guardian charter scan, seeded violations, and scheduler CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_research.monitoring.cli import load_decisions, main
from lumina_research.monitoring.types import ContinuityRefused
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_guardian_daily_passes_sealed_signals(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-a", trial_id=1)
    runtime.trials.record(config_id="hyp-a", agent_id="hypothesis_agent", metrics={"phase": "test"})
    report = runtime.guardian_scan("daily", report_dir=tmp_path / "reports")
    assert report.n_signals == 1
    assert report.n_violations == 0
    assert report.passed is True
    assert (tmp_path / "reports" / "guardian-daily.json").is_file()


@pytest.mark.unit
def test_guardian_detects_seeded_ungated_promotion(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-live", trial_id=1)
    runtime.trials.record(config_id="hyp-live", agent_id="hypothesis_agent", metrics={"phase": "test"})
    report = runtime.guardian_scan(
        "weekly",
        decisions=({"hypothesis_id": "hyp-live", "kind": "ungated_promotion", "gated": False},),
        report_dir=tmp_path / "g",
    )
    assert report.n_violations >= 1
    assert report.passed is False
    assert "hyp-live" in report.suspend_proposals
    assert runtime.registry.require("hyp-live").stage in {"deweighted", "suspended", "retired"}


@pytest.mark.unit
def test_guardian_flags_missing_trial_log(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-orphan", trial_id=9)
    report = runtime.guardian_scan("daily")
    assert report.passed is False
    assert any(item.check_id == "trial_logged" and item.passed is False for item in runtime.guardian.findings())


@pytest.mark.unit
def test_cli_scheduler_entrypoint_seeded_violation(tmp_path: Path) -> None:
    state = tmp_path / "state"
    reports = tmp_path / "reports"
    state.mkdir()
    (state / "decisions.json").write_text(
        json.dumps([{"hypothesis_id": "ghost", "kind": "ungated_promotion", "gated": False}]),
        encoding="utf-8",
    )
    evo = tmp_path / "brain"
    code = main(
        [
            "daily",
            "--state-dir",
            str(state),
            "--report-dir",
            str(reports),
            "--evolution-log-dir",
            str(evo),
        ]
    )
    assert code == 2
    payload = json.loads((reports / "guardian-daily.json").read_text(encoding="utf-8"))
    assert payload["passed"] is False
    assert payload["n_violations"] >= 1
    assert (evo / "phase4-continuity.jsonl").is_file()


@pytest.mark.unit
def test_cli_weekly_clean_state_is_zero(tmp_path: Path) -> None:
    state = tmp_path / "state"
    reports = tmp_path / "reports"
    code = main(["weekly", "--state-dir", str(state), "--report-dir", str(reports)])
    assert code == 0
    payload = json.loads((reports / "guardian-weekly.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True


@pytest.mark.unit
def test_cli_rejects_bad_decisions_file(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "decisions.json").write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(ContinuityRefused):
        load_decisions(state)
