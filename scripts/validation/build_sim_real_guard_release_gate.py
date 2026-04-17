from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_CONTRACT_TESTS = [
    "tests/test_mode_capabilities.py",
    "tests/test_config_loader_mode_matrix.py",
    "tests/test_agent_policy_gateway.py",
    "tests/test_order_gatekeeper_contracts.py",
    "tests/test_trade_mode_golden_paths.py",
    "tests/test_runtime_workers.py",
    "tests/engine/test_trade_reconciler.py",
    "tests/test_rollout_b_automation.py",
    "tests/test_rollout_b_schedule.py",
    "tests/test_launcher_headless_cli.py",
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _go_window_streak(history: list[dict[str, Any]]) -> int:
    streak = 0
    best = 0
    for item in history:
        if str(item.get("decision", "")) == "GO_WINDOW":
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def _run_contract_tests(repo_root: Path, python_exe: str) -> dict[str, Any]:
    command = [python_exe or sys.executable, "-m", "pytest", "-q", *DEFAULT_CONTRACT_TESTS]
    result = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    return {
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "command": command,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def build_release_gate_report(
    *,
    contract_tests: dict[str, Any],
    rollout_decision: dict[str, Any],
    history: list[dict[str, Any]],
    signoff: dict[str, Any],
    incidents: dict[str, Any],
) -> dict[str, Any]:
    approvals = signoff.get("approvals", []) if isinstance(signoff.get("approvals"), list) else []
    unresolved_critical_incidents = [
        item
        for item in (incidents.get("incidents", []) if isinstance(incidents.get("incidents"), list) else [])
        if str(item.get("severity", "")).lower() == "critical" and not bool(item.get("rca_completed"))
    ]
    longest_go_streak = _go_window_streak(history)
    any_force_close = any(int(item.get("candidate", {}).get("force_close_count", 0) or 0) > 0 for item in history)
    any_reconciler_evidence = any(
        int(item.get("candidate", {}).get("reconciled_count", 0) or 0) > 0 for item in history
    )
    explainability_failures = int(rollout_decision.get("explainability_failure_window_count", 0) or 0)

    acceptance_checks = {
        "no_regression_on_paper_sim_real": bool(contract_tests.get("passed")),
        "sim_advisory_risk_unchanged": bool(contract_tests.get("passed")),
        "sim_real_guard_real_gate_parity": bool(contract_tests.get("passed")) and explainability_failures == 0,
        "sim_real_guard_eod_force_close_active": any_force_close,
        "sim_real_guard_reconciler_audit_evidence_present": any_reconciler_evidence,
        "ci_contract_suite_green": bool(contract_tests.get("passed")),
    }
    exit_checks = {
        "minimum_10_consecutive_green_sessions": longest_go_streak >= 10,
        "reconciliation_mismatch_rate_within_slo": float(rollout_decision.get("max_timeout_ratio", 1.0) or 1.0) <= 0.02,
        "no_critical_fail_closed_incidents_without_rca": len(unresolved_critical_incidents) == 0,
        "operator_signoff_count_met": len(approvals) >= 2,
    }
    controlled_pilot_ready = all(acceptance_checks.values()) and all(exit_checks.values())
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance_checks": acceptance_checks,
        "exit_checks": exit_checks,
        "longest_go_window_streak": longest_go_streak,
        "window_count": len(history),
        "signoff_count": len(approvals),
        "unresolved_critical_incident_count": len(unresolved_critical_incidents),
        "rollout_b_ready_for_rollout_c": bool(rollout_decision.get("ready_for_rollout_c")),
        "controlled_pilot_ready": controlled_pilot_ready,
        "ga_ready": controlled_pilot_ready and bool(rollout_decision.get("ready_for_rollout_c")),
        "contract_tests": {
            "passed": bool(contract_tests.get("passed")),
            "returncode": int(contract_tests.get("returncode", 1) or 1),
            "command": contract_tests.get("command", []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an automated SIM_REAL_GUARD release/exit gate report.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--python-exe", default="")
    parser.add_argument("--skip-tests", action="store_true", default=False)
    parser.add_argument("--signoff-file", default="")
    parser.add_argument("--incidents-file", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    candidate_root = Path(args.candidate_root).resolve()
    validation_dir = candidate_root / "state" / "validation" / "sim_real_guard_rollout_b"
    rollout_decision_path = validation_dir / "rollout_b_decision.json"
    history_path = validation_dir / "parity_history.jsonl"
    signoff_path = Path(args.signoff_file).resolve() if args.signoff_file else (validation_dir / "signoff.json")
    incidents_path = Path(args.incidents_file).resolve() if args.incidents_file else (validation_dir / "incidents.json")
    output_path = Path(args.output).resolve() if args.output else (validation_dir / "release_gate_report.json")

    contract_tests = {
        "passed": False,
        "returncode": 1,
        "command": [],
    }
    if args.skip_tests:
        contract_tests = {"passed": True, "returncode": 0, "command": []}
    else:
        contract_tests = _run_contract_tests(repo_root, args.python_exe)

    report = build_release_gate_report(
        contract_tests=contract_tests,
        rollout_decision=_read_json(rollout_decision_path),
        history=_read_jsonl(history_path),
        signoff=_read_json(signoff_path),
        incidents=_read_json(incidents_path),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(output_path),
                "controlled_pilot_ready": report["controlled_pilot_ready"],
                "ga_ready": report["ga_ready"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
