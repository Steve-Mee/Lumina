"""Phase 3 evolution report. Distributions only; never a single in-sample backtest."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from lumina_core.agent_orchestration.schemas_research import (
    GovernanceDecision,
    MutationProposed,
    PromotionCandidate,
    ValidationResult,
)
from lumina_research.agents.report import CandidateSnapshot, build_kill_rate_report


@dataclass(frozen=True, slots=True)
class EvolutionReport:
    seed: int
    n_mutations: int
    n_admitted: int
    n_governance_rejected: int
    n_human_recorded: int
    n_hypotheses: int
    n_killed: int
    n_promoted: int
    kill_rate: float
    n_noise_mutations: int
    n_noise_promoted: int
    n_trials_start: int
    n_trials_end: int
    floors_intact: bool
    risk_core_intact: bool
    reject_reason_counts: Mapping[str, int]
    candidates: tuple[CandidateSnapshot, ...]
    mutation_ids: tuple[str, ...]
    admitted_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SeedEvolution:
    seed: int
    instrument: str
    report: EvolutionReport


@dataclass(frozen=True, slots=True)
class MultiSeedEvolutionReport:
    seeds: tuple[SeedEvolution, ...]
    n_mutations: int
    n_hypotheses: int
    n_promoted: int
    n_noise_mutations: int
    n_noise_promoted: int
    kill_rate: float
    floors_intact: bool
    risk_core_intact: bool

    @classmethod
    def from_seeds(cls, seeds: tuple[SeedEvolution, ...]) -> MultiSeedEvolutionReport:
        n_mutations = sum(row.report.n_mutations for row in seeds)
        n_hypotheses = sum(row.report.n_hypotheses for row in seeds)
        n_promoted = sum(row.report.n_promoted for row in seeds)
        n_noise = sum(row.report.n_noise_mutations for row in seeds)
        n_noise_promoted = sum(row.report.n_noise_promoted for row in seeds)
        killed = sum(row.report.n_killed for row in seeds)
        return cls(
            seeds=seeds,
            n_mutations=n_mutations,
            n_hypotheses=n_hypotheses,
            n_promoted=n_promoted,
            n_noise_mutations=n_noise,
            n_noise_promoted=n_noise_promoted,
            kill_rate=(killed / n_hypotheses) if n_hypotheses else 0.0,
            floors_intact=all(row.report.floors_intact for row in seeds),
            risk_core_intact=all(row.report.risk_core_intact for row in seeds),
        )


def build_evolution_report(
    *,
    seed: int,
    mutations: Sequence[MutationProposed],
    decisions: Sequence[GovernanceDecision],
    results: Sequence[ValidationResult],
    promotions: Sequence[PromotionCandidate],
    planted_flags: Mapping[str, bool],
    n_trials_start: int,
    n_trials_end: int,
    floors_intact: bool,
    risk_core_intact: bool,
) -> EvolutionReport:
    admitted_ids = tuple(item.mutation_id for item in decisions if item.admitted)
    killed_gov = tuple(item.mutation_id for item in decisions if not item.admitted and not item.recorded_for_human)
    recorded = tuple(item.mutation_id for item in decisions if item.recorded_for_human)
    planted = {f"hyp-{item.config_id}": item.genome.planted for item in mutations}
    planted.update(dict(planted_flags))
    kill = build_kill_rate_report(
        seed=seed,
        planted_ids=tuple(hid for hid, flag in planted.items() if flag),
        results=results,
        promotions=promotions,
        planted_flags=planted,
    )
    noise_ids = {f"hyp-{item.config_id}" for item in mutations if item.kind == "noise" or not item.genome.planted}
    promoted_ids = {item.hypothesis_id for item in promotions}
    n_noise = sum(1 for item in mutations if item.kind == "noise" or not item.genome.planted)
    n_noise_promoted = len(noise_ids & promoted_ids)
    reasons: dict[str, int] = dict(kill.reject_reason_counts)
    for decision in decisions:
        if decision.admitted:
            continue
        label = decision.reasons[0] if decision.reasons else "governance_reject"
        reasons[label] = reasons.get(label, 0) + 1
    return EvolutionReport(
        seed=seed,
        n_mutations=len(mutations),
        n_admitted=len(admitted_ids),
        n_governance_rejected=len(killed_gov),
        n_human_recorded=len(recorded),
        n_hypotheses=kill.n_hypotheses,
        n_killed=kill.n_killed,
        n_promoted=kill.n_promoted,
        kill_rate=kill.kill_rate,
        n_noise_mutations=n_noise,
        n_noise_promoted=n_noise_promoted,
        n_trials_start=n_trials_start,
        n_trials_end=n_trials_end,
        floors_intact=floors_intact,
        risk_core_intact=risk_core_intact,
        reject_reason_counts=reasons,
        candidates=kill.candidates,
        mutation_ids=tuple(item.mutation_id for item in mutations),
        admitted_ids=admitted_ids,
    )


def write_evolution_reports(report: EvolutionReport, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "phase3_evolution.json"
    md_path = directory / "phase3_evolution.md"
    json_path.write_text(json.dumps(_as_json(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_as_markdown(report), encoding="utf-8")
    return md_path, json_path


def write_multiseed_evolution_reports(report: MultiSeedEvolutionReport, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "phase3_evolution_multiseed.json"
    md_path = directory / "phase3_evolution_multiseed.md"
    json_path.write_text(json.dumps(_as_multiseed_json(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_as_multiseed_markdown(report), encoding="utf-8")
    return md_path, json_path


def _as_json(report: EvolutionReport) -> dict[str, object]:
    return {
        "seed": report.seed,
        "n_mutations": report.n_mutations,
        "n_admitted": report.n_admitted,
        "n_governance_rejected": report.n_governance_rejected,
        "n_human_recorded": report.n_human_recorded,
        "n_hypotheses": report.n_hypotheses,
        "n_killed": report.n_killed,
        "n_promoted": report.n_promoted,
        "kill_rate": report.kill_rate,
        "n_noise_mutations": report.n_noise_mutations,
        "n_noise_promoted": report.n_noise_promoted,
        "n_trials_start": report.n_trials_start,
        "n_trials_end": report.n_trials_end,
        "floors_intact": report.floors_intact,
        "risk_core_intact": report.risk_core_intact,
        "reject_reason_counts": dict(report.reject_reason_counts),
        "mutation_ids": list(report.mutation_ids),
        "admitted_ids": list(report.admitted_ids),
        "candidates": [
            {
                "hypothesis_id": item.hypothesis_id,
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
            }
            for item in report.candidates
        ],
    }


def _as_markdown(report: EvolutionReport) -> str:
    lines = [
        "# Phase 3 self-evolution — report",
        "",
        "Parameter/window mutations only. Fitness is the Phase 1 composite OOS function.",
        "",
        f"- seed: `{report.seed}`",
        f"- mutations: **{report.n_mutations}**",
        f"- admitted to Validation Gate: **{report.n_admitted}**",
        f"- hypotheses: **{report.n_hypotheses}**",
        f"- promoted: **{report.n_promoted}**",
        f"- kill rate: **{report.kill_rate:.4f}**",
        f"- noise promoted: **{report.n_noise_promoted}/{report.n_noise_mutations}**",
        f"- trials: {report.n_trials_start} → {report.n_trials_end}",
        f"- floors intact: **{report.floors_intact}**",
        f"- Risk Core intact: **{report.risk_core_intact}**",
        "",
        "## Why ideas die",
        "",
        "| check | count |",
        "|---|---|",
    ]
    if report.reject_reason_counts:
        for name, count in sorted(report.reject_reason_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{name}` | {count} |")
    else:
        lines.append("| _(none)_ | 0 |")
    lines.append("")
    return "\n".join(lines)


def _as_multiseed_json(report: MultiSeedEvolutionReport) -> dict[str, object]:
    return {
        "n_mutations": report.n_mutations,
        "n_hypotheses": report.n_hypotheses,
        "n_promoted": report.n_promoted,
        "n_noise_mutations": report.n_noise_mutations,
        "n_noise_promoted": report.n_noise_promoted,
        "kill_rate": report.kill_rate,
        "floors_intact": report.floors_intact,
        "risk_core_intact": report.risk_core_intact,
        "seeds": [
            {
                "seed": row.seed,
                "instrument": row.instrument,
                **_as_json(row.report),
            }
            for row in report.seeds
        ],
    }


def _as_multiseed_markdown(report: MultiSeedEvolutionReport) -> str:
    lines = [
        "# Phase 3 self-evolution — multi-seed report",
        "",
        "Independent seeds. Gate floors and Risk Core were not retuned.",
        "",
        f"- seeds: **{len(report.seeds)}**",
        f"- mutations: **{report.n_mutations}**",
        f"- hypotheses: **{report.n_hypotheses}**",
        f"- promoted: **{report.n_promoted}**",
        f"- overall kill rate: **{report.kill_rate:.4f}**",
        f"- noise promoted: **{report.n_noise_promoted}/{report.n_noise_mutations}**",
        f"- floors intact: **{report.floors_intact}**",
        f"- Risk Core intact: **{report.risk_core_intact}**",
        "",
        "| seed | instrument | n | kill rate | noise promoted |",
        "|---|---|---|---|---|",
    ]
    for row in report.seeds:
        lines.append(
            f"| `{row.seed}` | `{row.instrument}` | {row.report.n_hypotheses} | "
            f"{row.report.kill_rate:.4f} | {row.report.n_noise_promoted}/{row.report.n_noise_mutations} |"
        )
    lines.append("")
    return "\n".join(lines)
