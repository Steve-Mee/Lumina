"""``python -m lumina_research.proof verify|research|weekly``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from lumina_research.cycles.runner import run_research_cycles
from lumina_research.monitoring.cli import run_scan as run_guardian_scan
from lumina_research.proof.independent import INDEPENDENT_INSTRUMENTS, INDEPENDENT_SEEDS
from lumina_research.proof.runner import DEFAULT_EVOLUTION_LOG, DEFAULT_REPORTS, run_empirical_verification


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lumina-research-proof",
        description="Phase 5 empirical proof: independent verification, real-data cycles, weekly metrics.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify", help="P1 independent gate + continuity floors + mutation report")
    verify.add_argument("--work-dir", type=Path, default=Path("state/phase5-proof"))
    verify.add_argument("--report-dir", type=Path, default=DEFAULT_REPORTS)
    verify.add_argument("--evolution-log-dir", type=Path, default=DEFAULT_EVOLUTION_LOG)
    verify.add_argument("--mutation-report", type=Path, default=None)
    verify.add_argument("--n-per-kind", type=int, default=6)
    verify.add_argument("--n-days", type=int, default=70)
    verify.add_argument("--decay-start", type=int, default=20)
    research = sub.add_parser("research", help="P2 real-data research cycles through the Validation Gate")
    research.add_argument("--work-dir", type=Path, default=Path("state/phase5-research"))
    research.add_argument("--report-dir", type=Path, default=DEFAULT_REPORTS)
    research.add_argument("--evolution-log-dir", type=Path, default=DEFAULT_EVOLUTION_LOG)
    research.add_argument("--data-dir", type=Path, default=None)
    weekly = sub.add_parser("weekly", help="Guardian weekly scan plus weekly metrics report")
    weekly.add_argument("--state-dir", type=Path, required=True)
    weekly.add_argument("--report-dir", type=Path, required=True)
    weekly.add_argument("--evolution-log-dir", type=Path, default=None)
    weekly.add_argument("--mutation-report", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    command = str(args.command)
    if command == "verify":
        result = run_empirical_verification(
            work_dir=args.work_dir,
            report_dir=args.report_dir,
            evolution_log_dir=args.evolution_log_dir,
            mutation_report=args.mutation_report,
            n_per_kind=int(args.n_per_kind),
            n_days=int(args.n_days),
            decay_start=int(args.decay_start),
            seeds=INDEPENDENT_SEEDS,
            instruments=INDEPENDENT_INSTRUMENTS,
        )
        if result.passed:
            return 0
        sys.stderr.write("empirical verification floors failed; detector may be tuned, floors may not\n")
        return 2
    if command == "research":
        cycle = run_research_cycles(
            work_dir=args.work_dir,
            report_dir=args.report_dir,
            evolution_log_dir=args.evolution_log_dir,
            data_dir=args.data_dir,
        )
        if cycle.data.usable:
            if cycle.kill_rate_flag.startswith("flag_"):
                sys.stderr.write(f"P2 kill-rate diagnostic: {cycle.kill_rate_flag}\n")
            return 0
        sys.stderr.write("P2 stopped: no usable real market data\n")
        return 3
    if command == "weekly":
        weekly_argv = [
            "weekly",
            "--state-dir",
            str(args.state_dir),
            "--report-dir",
            str(args.report_dir),
        ]
        if args.evolution_log_dir is not None:
            weekly_argv.extend(["--evolution-log-dir", str(args.evolution_log_dir)])
        if args.mutation_report is not None:
            weekly_argv.extend(["--mutation-report", str(args.mutation_report)])
        return run_guardian_scan(weekly_argv)
    raise AssertionError(f"unknown command {command}")
