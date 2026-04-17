from __future__ import annotations

from scripts.validation.build_sim_real_guard_release_gate import build_release_gate_report


def test_release_gate_report_requires_signoff_and_evidence() -> None:
    history = [
        {
            "decision": "GO_WINDOW",
            "candidate": {
                "force_close_count": 1,
                "reconciled_count": 2,
            },
        }
        for _ in range(10)
    ]
    report = build_release_gate_report(
        contract_tests={"passed": True, "returncode": 0, "command": ["python", "-m", "pytest"]},
        rollout_decision={
            "max_timeout_ratio": 0.01,
            "explainability_failure_window_count": 0,
            "ready_for_rollout_c": True,
        },
        history=history,
        signoff={"approvals": [{"name": "ops-1"}, {"name": "ops-2"}]},
        incidents={"incidents": []},
    )

    assert report["acceptance_checks"]["ci_contract_suite_green"] is True
    assert report["exit_checks"]["minimum_10_consecutive_green_sessions"] is True
    assert report["controlled_pilot_ready"] is True
    assert report["ga_ready"] is True


def test_release_gate_report_stays_blocked_without_signoff() -> None:
    report = build_release_gate_report(
        contract_tests={"passed": True, "returncode": 0, "command": []},
        rollout_decision={
            "max_timeout_ratio": 0.01,
            "explainability_failure_window_count": 0,
            "ready_for_rollout_c": True,
        },
        history=[
            {"decision": "GO_WINDOW", "candidate": {"force_close_count": 1, "reconciled_count": 1}} for _ in range(10)
        ],
        signoff={"approvals": [{"name": "ops-1"}]},
        incidents={"incidents": []},
    )

    assert report["exit_checks"]["operator_signoff_count_met"] is False
    assert report["controlled_pilot_ready"] is False
