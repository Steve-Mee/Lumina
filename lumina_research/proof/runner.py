"""Run the Phase 5 P1 verification suite and persist reports + evolution log."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lumina_research.monitoring.mutation_report import (
    MutationFloorResult,
    evaluate_mutation_floor,
    resolve_mutation_report,
)
from lumina_research.proof.continuity_suite import ContinuitySuiteReport, run_independent_continuity
from lumina_research.proof.gate_suite import GateSuiteReport, run_gate_suite
from lumina_research.proof.independent import FLOOR_KINDS, INDEPENDENT_INSTRUMENTS, INDEPENDENT_SEEDS, SLOW_KINDS
from lumina_research.proof.log import log_proof_event
from lumina_research.proof.report import write_empirical_reports

DEFAULT_EVOLUTION_LOG = Path("project-dna/lumina/evolution/log")
DEFAULT_REPORTS = Path("experiments/reports")


@dataclass(frozen=True, slots=True)
class EmpiricalVerification:
    gate: GateSuiteReport
    continuity: ContinuitySuiteReport
    mutation: MutationFloorResult
    passed: bool
    json_path: Path
    md_path: Path


def run_empirical_verification(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    experiment_log_path: Path | None = None,
    evolution_log_dir: Path | None = DEFAULT_EVOLUTION_LOG,
    mutation_report: Path | None = None,
    n_per_kind: int = 6,
    n_days: int = 70,
    decay_start: int = 20,
    seeds: tuple[int, ...] = INDEPENDENT_SEEDS,
    instruments: tuple[str, ...] = INDEPENDENT_INSTRUMENTS,
) -> EmpiricalVerification:
    """Phase 1 gate + independent Phase 4 floors + mutation report. Never retunes floors."""
    audit_dir = work_dir / "audit"
    exp_dir = work_dir / "experiments"
    audit_dir.mkdir(parents=True, exist_ok=True)
    exp_dir.mkdir(parents=True, exist_ok=True)
    log_path = experiment_log_path if experiment_log_path is not None else work_dir / "experiments.jsonl"
    gate = run_gate_suite(audit_dir=audit_dir / "gate")
    continuity = run_independent_continuity(
        audit_dir=audit_dir / "continuity",
        experiment_log_dir=exp_dir,
        n_per_kind=n_per_kind,
        n_days=n_days,
        decay_start=decay_start,
        seeds=seeds,
        instruments=instruments,
        floor_kinds=FLOOR_KINDS,
        slow_kinds=SLOW_KINDS,
    )
    mutation = evaluate_mutation_floor(resolve_mutation_report(mutation_report))
    passed = gate.passed and continuity.floor_passed and mutation.passed
    json_path, md_path = write_empirical_reports(
        directory=report_dir, gate=gate, continuity=continuity, mutation=mutation
    )
    log_proof_event(
        path=log_path,
        event="empirical_verification",
        metrics={
            "passed": passed,
            "gate_passed": gate.passed,
            "continuity_floor_passed": continuity.floor_passed,
            "short_horizon_passed": continuity.short_passed,
            "medium_horizon_passed": continuity.medium_passed,
            "mutation_passed": mutation.passed,
            "mutation_kill_rate": mutation.kill_rate,
            "n_floor_signals": continuity.floor.n_signals,
            "n_slow_signals": continuity.slow.n_signals,
            "report_json": str(json_path),
        },
        evolution_log_dir=evolution_log_dir,
        reject_reason=None if passed else "empirical_floor_failed",
        failed_checks=() if passed else _failures(gate, continuity, mutation),
    )
    return EmpiricalVerification(
        gate=gate,
        continuity=continuity,
        mutation=mutation,
        passed=passed,
        json_path=json_path,
        md_path=md_path,
    )


def _failures(
    gate: GateSuiteReport,
    continuity: ContinuitySuiteReport,
    mutation: MutationFloorResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not gate.passed:
        reasons.append("gate_suite")
    if not continuity.floor_passed:
        reasons.append("independent_continuity")
    if not continuity.short_passed:
        reasons.append("short_horizon")
    if not continuity.medium_passed:
        reasons.append("medium_horizon")
    if not mutation.passed:
        reasons.append("mutation_kill_rate")
    return tuple(reasons)
