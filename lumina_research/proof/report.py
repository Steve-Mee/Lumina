"""Write Phase 5 empirical reports under experiments/reports/."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_research.monitoring.mutation_report import MutationFloorResult
from lumina_research.monitoring.report import MultiSeedDetectionReport
from lumina_research.proof.continuity_suite import ContinuitySuiteReport
from lumina_research.proof.gate_suite import GateSuiteReport
from lumina_research.validation.audit import utc_now_iso


def write_empirical_reports(
    *,
    directory: Path,
    gate: GateSuiteReport,
    continuity: ContinuitySuiteReport,
    mutation: MutationFloorResult,
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "generated_at": utc_now_iso(),
        "agent_id": "empirical_proof_agent",
        "gate": {
            "passed": gate.passed,
            "cases": [
                {
                    "name": item.name,
                    "seed": item.seed,
                    "expected_pass": item.expected_pass,
                    "passed": item.passed,
                    "reject_reasons": list(item.reject_reasons),
                    "pbo": item.pbo,
                    "dsr": item.dsr,
                    "wfe": item.wfe,
                    "n_oos_windows": item.n_oos_windows,
                    "purge_applied": item.purge_applied,
                    "embargo_applied": item.embargo_applied,
                    "n_trials": item.n_trials,
                    "median_oos": item.median_oos,
                }
                for item in gate.cases
            ],
        },
        "continuity_floor": _multiseed_body(continuity.floor),
        "slow_decay": {
            "notes": continuity.slow_notes,
            "report": _multiseed_body(continuity.slow),
        },
        "mutation": {
            "passed": mutation.passed,
            "kill_rate": mutation.kill_rate,
            "n_mutants": mutation.n_mutants,
            "n_killed": mutation.n_killed,
            "n_non_equivalent": mutation.n_non_equivalent,
            "n_excluded": mutation.n_excluded,
            "observed": mutation.observed,
            "required": mutation.required,
            "path": mutation.path,
        },
        "floor_passed": gate.passed and continuity.floor_passed and mutation.passed,
        "continuity_floor_passed": continuity.floor_passed,
        "short_horizon_passed": continuity.short_passed,
        "medium_horizon_passed": continuity.medium_passed,
    }
    json_path = directory / "phase5_empirical.json"
    json_path.write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path = directory / "phase5_empirical.md"
    md_path.write_text(_markdown(gate, continuity, mutation, body["floor_passed"]), encoding="utf-8")
    return json_path, md_path


def _multiseed_body(report: MultiSeedDetectionReport) -> dict[str, object]:
    return {
        "n_signals": report.n_signals,
        "n_seeds": report.n_seeds,
        "n_healthy": report.n_healthy,
        "n_decaying": report.n_decaying,
        "n_detected": report.n_detected,
        "n_false_alarms": report.n_false_alarms,
        "detection_rate": report.detection_rate,
        "false_alarm_rate": report.false_alarm_rate,
        "median_time_to_detect": report.median_time_to_detect,
        "p90_time_to_detect": report.p90_time_to_detect,
        "max_time_to_detect": report.max_time_to_detect,
        "by_kind": [
            {
                "kind": item.kind,
                "n": item.n,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "p90_time_to_detect": item.p90_time_to_detect,
                "max_time_to_detect": item.max_time_to_detect,
            }
            for item in report.by_kind
        ],
    }


def _markdown(
    gate: GateSuiteReport,
    continuity: ContinuitySuiteReport,
    mutation: MutationFloorResult,
    floor_passed: object,
) -> str:
    lines = [
        "# Phase 5 empirical proof",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        "- agent_id: `empirical_proof_agent`",
        f"- overall floor_passed: `{floor_passed}`",
        f"- gate_suite_passed: `{gate.passed}`",
        f"- independent continuity floor_passed: `{continuity.floor_passed}`",
        f"- short_horizon_passed (TTD<=15): `{continuity.short_passed}`",
        f"- medium_horizon_passed (TTD<=45): `{continuity.medium_passed}`",
        f"- mutation_kill_rate: `{mutation.kill_rate}` passed: `{mutation.passed}`",
        "",
        "## Phase 1 gate (independent synthetics)",
        "",
        "| case | seed | expected | passed | n_oos | PBO | DSR | WFE | purge/embargo | reasons |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in gate.cases:
        pbo = "n/a" if item.pbo is None else f"{item.pbo:.4f}"
        dsr = "n/a" if item.dsr is None else f"{item.dsr:.4f}"
        wfe = "n/a" if item.wfe is None else f"{item.wfe:.4f}"
        reasons = ",".join(item.reject_reasons) if item.reject_reasons else ""
        lines.append(
            f"| {item.name} | {item.seed} | {item.expected_pass} | {item.passed} | "
            f"{item.n_oos_windows} | {pbo} | {dsr} | {wfe} | "
            f"{item.purge_applied}/{item.embargo_applied} | {reasons} |"
        )
    lines.extend(["", "## Short horizon (fast/material breaks, TTD <= 15)", ""])
    lines.extend(_kind_table(continuity.floor, "short / material / FAR kinds"))
    lines.extend(
        [
            "",
            "## Medium horizon (slow 30/45/60-day decay, TTD <= 45, detection >= 0.85)",
            "",
            continuity.slow_notes,
            "",
        ]
    )
    lines.extend(_kind_table(continuity.slow, "slow kinds"))
    lines.extend(
        [
            "",
            "## Mutation kill rate (latest nightly report)",
            "",
            f"- path: `{mutation.path}`",
            f"- observed: `{mutation.observed}`",
            f"- required: `{mutation.required}`",
            f"- passed: `{mutation.passed}`",
            "",
        ]
    )
    return "\n".join(lines)


def _kind_table(report: MultiSeedDetectionReport, title: str) -> list[str]:
    lines = [
        f"### {title}",
        "",
        f"- seeds: `{report.n_seeds}` signals: `{report.n_signals}`",
        f"- detection_rate: `{report.detection_rate:.4f}`",
        f"- false_alarm_rate: `{report.false_alarm_rate:.4f}`",
        f"- max_time_to_detect: `{report.max_time_to_detect}`",
        "",
        "| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in report.by_kind:
        mid = "n/a" if item.median_time_to_detect is None else f"{item.median_time_to_detect:.1f}"
        p90 = "n/a" if item.p90_time_to_detect is None else f"{item.p90_time_to_detect:.1f}"
        mx = "n/a" if item.max_time_to_detect is None else f"{item.max_time_to_detect:.1f}"
        lines.append(
            f"| {item.kind} | {item.n} | {item.detection_rate:.4f} | {item.false_alarm_rate:.4f} | {mid} | {p90} | {mx} |"
        )
    lines.append("")
    return lines
