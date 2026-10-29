"""Write Phase 5 empirical reports under experiments/reports/."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_research.monitoring.acceptance import (
    DETECTION_RATE_MIN,
    FAR_HEALTHY_MAX,
    FAR_HIGH_VOL_MAX,
    TTD_MAX_TRADING_DAYS,
    TTD_MEDIUM_MAX_TRADING_DAYS,
)
from lumina_research.monitoring.mutation_report import MutationFloorResult
from lumina_research.monitoring.report import KindMetrics, MultiSeedDetectionReport
from lumina_research.proof.continuity_suite import ContinuitySuiteReport
from lumina_research.proof.gate_suite import GateSuiteReport
from lumina_research.proof.independent import PRIMARY_HIGH_VOL_KIND, STRESS_HIGH_VOL_KIND, healthy_kind
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
        "holdout_seeds": [row.seed for row in continuity.floor.seeds],
        "primary_normal_far": continuity.primary_normal_far,
        "primary_high_vol_far": continuity.primary_high_vol_far,
        "stress_high_vol_mixture_far": continuity.stress_high_vol_mixture_far,
        "by_regime": _regime_body(continuity.floor),
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
        "by_regime": [
            {
                "regime": item.kind,
                "n": item.n,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "p90_time_to_detect": item.p90_time_to_detect,
                "max_time_to_detect": item.max_time_to_detect,
            }
            for item in report.by_regime
        ],
    }


def _regime_body(report: MultiSeedDetectionReport) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in report.by_regime:
        rows.append(
            {
                "regime": item.kind,
                "n": item.n,
                "n_detected": item.n_detected,
                "n_false_alarms": item.n_false_alarms,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "max_time_to_detect": item.max_time_to_detect,
            }
        )
    return rows


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
        f"- holdout_seeds: `{', '.join(str(row.seed) for row in continuity.floor.seeds)}`",
        f"- primary_normal_far (`healthy_laplace`, floor <= {FAR_HEALTHY_MAX:.2f}): `{continuity.primary_normal_far}`",
        f"- primary_high_vol_far (`{PRIMARY_HIGH_VOL_KIND}`, floor <= {FAR_HIGH_VOL_MAX:.2f}): `{continuity.primary_high_vol_far}`",
        f"- stress `{STRESS_HIGH_VOL_KIND}` FAR (not a floor): `{continuity.stress_high_vol_mixture_far}`",
        "",
        "## Per-regime FAR / detection / TTD",
        "",
    ]
    lines.extend(_regime_table(continuity))
    lines.extend(
        [
            "",
            "## Phase 1 gate (independent synthetics)",
            "",
            "| case | seed | expected | passed | n_oos | PBO | DSR | WFE | purge/embargo | reasons |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
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


def _regime_table(continuity: ContinuitySuiteReport) -> list[str]:
    lines = [
        "| slice | n | FAR | FAR floor | detection | TTD max | TTD floor | pass |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in continuity.floor.by_kind:
        band = healthy_kind(item.kind)
        if band == "healthy":
            lines.append(_slice_row(item, far_floor=FAR_HEALTHY_MAX, ttd_floor=None, detection_floor=None))
        elif band == "high_vol":
            lines.append(_slice_row(item, far_floor=FAR_HIGH_VOL_MAX, ttd_floor=None, detection_floor=None))
        elif band == "stress":
            lines.append(_slice_row(item, far_floor=None, ttd_floor=None, detection_floor=None, stress=True))
        elif item.kind in {"abrupt_student", "gradual_smooth", "regime_laplace", "material_break"}:
            lines.append(
                _slice_row(
                    item,
                    far_floor=None,
                    ttd_floor=TTD_MAX_TRADING_DAYS,
                    detection_floor=DETECTION_RATE_MIN,
                )
            )
    for item in continuity.floor.by_regime:
        far_floor = FAR_HIGH_VOL_MAX if item.kind == "high_vol" else FAR_HEALTHY_MAX
        lines.append(
            _slice_row(
                item,
                far_floor=far_floor,
                ttd_floor=TTD_MAX_TRADING_DAYS if item.n_detected else None,
                detection_floor=DETECTION_RATE_MIN if item.n_detected else None,
                label=f"regime={item.kind}",
            )
        )
    for item in continuity.slow.by_kind:
        lines.append(
            _slice_row(
                item,
                far_floor=None,
                ttd_floor=TTD_MEDIUM_MAX_TRADING_DAYS,
                detection_floor=DETECTION_RATE_MIN,
            )
        )
    lines.append("")
    return lines


def _slice_row(
    item: KindMetrics,
    *,
    far_floor: float | None,
    ttd_floor: int | None,
    detection_floor: float | None,
    stress: bool = False,
    label: str | None = None,
) -> str:
    name = label if label is not None else item.kind
    far = f"{item.false_alarm_rate:.4f}"
    far_cap = "stress" if stress else ("n/a" if far_floor is None else f"{far_floor:.2f}")
    det = f"{item.detection_rate:.4f}"
    ttd = "n/a" if item.max_time_to_detect is None else f"{item.max_time_to_detect:.1f}"
    ttd_cap = "n/a" if ttd_floor is None else str(ttd_floor)
    passed = True
    if far_floor is not None and item.false_alarm_rate > far_floor:
        passed = False
    if detection_floor is not None and item.detection_rate < detection_floor:
        passed = False
    if ttd_floor is not None and (item.max_time_to_detect is None or item.max_time_to_detect > ttd_floor):
        passed = False
    if stress:
        passed_label = "reported"
    else:
        passed_label = "PASS" if passed else "FAIL"
    return f"| {name} | {item.n} | {far} | {far_cap} | {det} | {ttd} | {ttd_cap} | {passed_label} |"
