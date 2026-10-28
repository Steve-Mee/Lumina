"""Kill-rate report. Always includes the OOS distribution per candidate, never one backtest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from lumina_core.agent_orchestration.schemas_research import PromotionCandidate, ValidationResult


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    hypothesis_id: str
    config_id: str
    planted: bool
    passed_gate: bool
    promoted: bool
    reject_reasons: tuple[str, ...]
    oos_values: tuple[float | None, ...]
    oos_median: float | None
    oos_worst: float | None
    oos_pct_positive: float | None
    dsr: float | None
    pbo: float | None
    wfe: float | None
    n_oos_windows: int
    decision_kind: str | None


@dataclass(frozen=True, slots=True)
class KillRateReport:
    seed: int
    n_hypotheses: int
    n_killed: int
    n_survived: int
    n_promoted: int
    kill_rate: float
    planted_ids: tuple[str, ...]
    planted_survived: tuple[str, ...]
    reject_reason_counts: Mapping[str, int]
    candidates: tuple[CandidateSnapshot, ...]


def build_kill_rate_report(
    *,
    seed: int,
    planted_ids: Sequence[str],
    results: Sequence[ValidationResult],
    promotions: Sequence[PromotionCandidate],
    planted_flags: Mapping[str, bool],
) -> KillRateReport:
    promoted_ids = {item.hypothesis_id for item in promotions}
    snapshots: list[CandidateSnapshot] = []
    reason_counts: dict[str, int] = {}
    for result in results:
        promoted = result.hypothesis_id in promoted_ids
        kind = None
        for item in promotions:
            if item.hypothesis_id == result.hypothesis_id:
                kind = item.decision_kind
                break
        for reason in result.reject_reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if not result.passed and not result.reject_reasons:
            reason_counts["unspecified_reject"] = reason_counts.get("unspecified_reject", 0) + 1
        snapshots.append(
            CandidateSnapshot(
                hypothesis_id=result.hypothesis_id,
                config_id=result.config_id,
                planted=bool(planted_flags.get(result.hypothesis_id, False)),
                passed_gate=result.passed,
                promoted=promoted,
                reject_reasons=result.reject_reasons,
                oos_values=result.oos_distribution.values,
                oos_median=result.oos_distribution.median,
                oos_worst=result.oos_distribution.worst,
                oos_pct_positive=result.oos_distribution.pct_positive,
                dsr=result.dsr.probability,
                pbo=result.pbo.pbo,
                wfe=result.wfe.wfe,
                n_oos_windows=result.n_oos_windows,
                decision_kind=kind,
            )
        )
    n_hypotheses = len(results)
    n_promoted = len(promoted_ids)
    n_killed = n_hypotheses - n_promoted
    kill_rate = (n_killed / n_hypotheses) if n_hypotheses else 0.0
    planted_tuple = tuple(planted_ids)
    survived = tuple(hid for hid in planted_tuple if hid in promoted_ids)
    return KillRateReport(
        seed=seed,
        n_hypotheses=n_hypotheses,
        n_killed=n_killed,
        n_survived=n_hypotheses - n_killed,
        n_promoted=n_promoted,
        kill_rate=kill_rate,
        planted_ids=planted_tuple,
        planted_survived=survived,
        reject_reason_counts=dict(reason_counts),
        candidates=tuple(snapshots),
    )


def write_kill_rate_reports(report: KillRateReport, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "phase2_kill_rate.json"
    md_path = directory / "phase2_kill_rate.md"
    payload = _as_json(report)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_as_markdown(report), encoding="utf-8")
    return md_path, json_path


def _as_json(report: KillRateReport) -> dict[str, object]:
    return {
        "seed": report.seed,
        "n_hypotheses": report.n_hypotheses,
        "n_killed": report.n_killed,
        "n_survived": report.n_survived,
        "n_promoted": report.n_promoted,
        "kill_rate": report.kill_rate,
        "planted_ids": list(report.planted_ids),
        "planted_survived": list(report.planted_survived),
        "reject_reason_counts": dict(report.reject_reason_counts),
        "candidates": [
            {
                "hypothesis_id": item.hypothesis_id,
                "config_id": item.config_id,
                "planted": item.planted,
                "passed_gate": item.passed_gate,
                "promoted": item.promoted,
                "reject_reasons": list(item.reject_reasons),
                "oos_distribution": {
                    "values": list(item.oos_values),
                    "median": item.oos_median,
                    "worst": item.oos_worst,
                    "pct_positive": item.oos_pct_positive,
                },
                "dsr": item.dsr,
                "pbo": item.pbo,
                "wfe": item.wfe,
                "n_oos_windows": item.n_oos_windows,
                "decision_kind": item.decision_kind,
            }
            for item in report.candidates
        ],
    }


def _as_markdown(report: KillRateReport) -> str:
    lines = [
        "# Phase 2 research loop — kill-rate report",
        "",
        "Distributions only. No single-backtest claim.",
        "",
        f"- seed: `{report.seed}`",
        f"- hypotheses: **{report.n_hypotheses}**",
        f"- killed: **{report.n_killed}**",
        f"- promoted (survivors): **{report.n_promoted}**",
        f"- kill rate: **{report.kill_rate:.4f}**",
        f"- planted ids: `{', '.join(report.planted_ids) or 'none'}`",
        f"- planted survived: `{', '.join(report.planted_survived) or 'none'}`",
        "",
        "## Why ideas die (per gate check)",
        "",
        "| check | count |",
        "|---|---|",
    ]
    if report.reject_reason_counts:
        for name, count in sorted(report.reject_reason_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{name}` | {count} |")
    else:
        lines.append("| _(none)_ | 0 |")
    lines.extend(
        [
            "",
            "## Per-candidate OOS distribution",
            "",
            "| id | planted | gate | promoted | DSR | PBO | WFE | OOS median | OOS worst | pct+ | n_oos | reasons |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in report.candidates:
        reasons = ",".join(item.reject_reasons) if item.reject_reasons else ""
        lines.append(
            "| `{id}` | {planted} | {gate} | {promoted} | {dsr} | {pbo} | {wfe} | {median} | {worst} | {pct} | {n} | `{reasons}` |".format(
                id=item.hypothesis_id,
                planted="yes" if item.planted else "no",
                gate="PASS" if item.passed_gate else "FAIL",
                promoted="yes" if item.promoted else "no",
                dsr=_fmt(item.dsr),
                pbo=_fmt(item.pbo),
                wfe=_fmt(item.wfe),
                median=_fmt(item.oos_median),
                worst=_fmt(item.oos_worst),
                pct=_fmt(item.oos_pct_positive),
                n=item.n_oos_windows,
                reasons=reasons,
            )
        )
    lines.append("")
    lines.append("Each candidate's full OOS path values are in `phase2_kill_rate.json`.")
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
