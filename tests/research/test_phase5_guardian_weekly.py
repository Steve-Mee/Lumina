"""Guardian mutation/sealed-gate checks and weekly two-horizon metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import GuardianEvidence, GuardianFinding
from lumina_research.diagnostics import diagnose_kill_rate
from lumina_research.monitoring.cli import main as monitoring_main
from lumina_research.monitoring.mutation_report import evaluate_mutation_floor
from lumina_research.monitoring.report import KindMetrics
from lumina_research.monitoring.weekly import build_weekly_metrics, load_hypothesis_rows, write_weekly_metrics
from lumina_research.proof.cli import main as proof_main
from tests.research.phase4_harness import admit_signal, make_runtime


def _finding(*, check_id: str, passed: bool) -> GuardianFinding:
    return GuardianFinding(
        finding_id=f"g-{check_id}",
        cadence="weekly",
        check_id=check_id,
        signal_id="*",
        agent_id="guardian_agent",
        passed=passed,
        severity="ok" if passed else "violation",
        suspend_proposed=False,
        evidence=GuardianEvidence(metric=check_id, observed="x", required="y"),
        provenance_mac="b" * 64,
    )


@pytest.mark.unit
def test_guardian_asserts_mutation_and_sealed_gate(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    admit_signal(runtime, "hyp-a", trial_id=1)
    runtime.trials.record(config_id="hyp-a", agent_id="hypothesis_agent", metrics={"phase": "test"})
    report = runtime.guardian_scan(
        "daily",
        report_dir=tmp_path / "g",
        mutation_report=Path("experiments/reports/phase4_mutation.json"),
    )
    assert report.passed is True
    checks = {item.check_id for item in runtime.guardian.findings()}
    assert "risk_core_untouched" in checks
    assert "mutation_kill_rate" in checks
    assert "sealed_gate_passage" in checks
    missing = runtime.guardian_scan(
        "weekly",
        mutation_report=tmp_path / "absent.json",
    )
    assert missing.passed is False
    assert any(item.check_id == "mutation_kill_rate" and item.passed is False for item in runtime.guardian.findings())


@pytest.mark.unit
def test_weekly_metrics_two_horizons_and_capital_zero(tmp_path: Path) -> None:
    mutation = evaluate_mutation_floor(Path("experiments/reports/phase4_mutation.json"))
    slow = (
        KindMetrics(
            kind="slow_gradual_45",
            n=10,
            n_detected=9,
            n_false_alarms=0,
            detection_rate=0.9,
            false_alarm_rate=0.0,
            median_time_to_detect=38.0,
            p90_time_to_detect=42.0,
            max_time_to_detect=44.0,
        ),
    )
    weekly = build_weekly_metrics(
        hypotheses=(
            {"event": "hypothesis", "passed": True},
            {"event": "validation", "passed": False},
            {"event": "validation", "passed": True},
        ),
        guardian=None,
        findings=(_finding(check_id="risk_core_untouched", passed=True),),
        slow_decay=slow,
        mutation=mutation,
    )
    assert weekly.capital_preservation_violations == 0
    assert weekly.medium_detection_rate == 0.9
    assert weekly.medium_median_ttd == 38.0
    assert weekly.kill_rate_flag in {"within_expectation", "expected_high_kill", "flag_structurally_low"}
    assert weekly.passed is True
    path = write_weekly_metrics(weekly, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["capital_preservation_violations"] == 0
    assert "medium_detection_rate" in payload
    broken = build_weekly_metrics(
        findings=(_finding(check_id="risk_core_untouched", passed=False),),
        mutation=mutation,
    )
    assert broken.capital_preservation_violations == 1
    assert broken.passed is False


@pytest.mark.unit
def test_kill_rate_diagnostic_flags() -> None:
    assert diagnose_kill_rate(kill_rate=0.5, n_hypotheses=24, n_survivors=12) == (
        "flag_gate_too_weak_or_generator_overfit"
    )
    assert diagnose_kill_rate(kill_rate=0.99, n_hypotheses=24, n_survivors=0) == (
        "flag_all_dead_check_known_good_synthetics"
    )


@pytest.mark.unit
def test_load_hypothesis_rows_and_cli_weekly(tmp_path: Path) -> None:
    log = tmp_path / "experiments.jsonl"
    log.write_text(
        json.dumps({"event": "hypothesis", "metrics": {"passed": True}})
        + "\n"
        + json.dumps({"event": "validation", "metrics": {"passed": False, "reject_reason": "pbo"}})
        + "\nnot-json\n",
        encoding="utf-8",
    )
    rows = load_hypothesis_rows(log)
    assert len(rows) == 2
    state = tmp_path / "state"
    reports = tmp_path / "reports"
    code = monitoring_main(["weekly", "--state-dir", str(state), "--report-dir", str(reports)])
    assert code == 0
    assert (reports / "weekly-metrics.json").is_file()
    proof_code = proof_main(
        [
            "weekly",
            "--state-dir",
            str(state),
            "--report-dir",
            str(tmp_path / "proof-weekly"),
        ]
    )
    assert proof_code == 0
