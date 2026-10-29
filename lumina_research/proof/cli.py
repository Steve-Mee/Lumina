"""``python -m lumina_research.proof verify|research|weekly``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from lumina_research.cycles.atr_cycle import run_atr_es_cycle
from lumina_research.cycles.four_instrument import run_four_instrument_cycle
from lumina_research.cycles.midpoint_d13 import (
    POWER_CLEAN,
    run_midpoint_d13,
    run_midpoint_power,
    run_midpoint_power_floor,
)
from lumina_research.cycles.null_audit import run_null_audit
from lumina_research.cycles.null_lock import NullLeaks, assert_research_allowed
from lumina_research.cycles.null_only import run_null_only, synthetic_drift_tape
from lumina_research.cycles.runner import run_research_cycles
from lumina_research.monitoring.cli import run_scan as run_guardian_scan
from lumina_research.proof.independent import HOLDOUT_INSTRUMENTS, HOLDOUT_SEEDS, assert_holdout_seeds
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
    research.add_argument(
        "--cycle",
        choices=(
            "first",
            "four-instrument",
            "null-audit",
            "atr-es",
            "null-only",
            "midpoint-d13",
            "midpoint-power",
            "midpoint-power-floor",
        ),
        default="first",
        help=(
            "first: MES/MNQ 12. four-instrument: cost-fix+ES/NQ. null-audit: D13 multi-seed. "
            "atr-es: ES ATR grid. null-only: FPR validation, no templates. "
            "midpoint-d13: planted+null under fade/breakout midpoints, no templates. "
            "midpoint-power: 100/50/25% planted magnitude, no templates. "
            "midpoint-power-floor: 12.5%/6.25% planted magnitude, no templates."
        ),
    )
    research.add_argument(
        "--es-csv",
        type=Path,
        default=None,
        help=(
            "null-only / midpoint-d13 / midpoint-power / midpoint-power-floor: "
            "local pre-holdout ES CSV. Not committed."
        ),
    )
    research.add_argument(
        "--reuse-mes-mnq",
        action="store_true",
        help="four-instrument: keep existing cost-fix MES/MNQ reports; run ES/NQ only.",
    )
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
        assert_holdout_seeds(HOLDOUT_SEEDS)
        result = run_empirical_verification(
            work_dir=args.work_dir,
            report_dir=args.report_dir,
            evolution_log_dir=args.evolution_log_dir,
            mutation_report=args.mutation_report,
            n_per_kind=int(args.n_per_kind),
            n_days=int(args.n_days),
            decay_start=int(args.decay_start),
            seeds=HOLDOUT_SEEDS,
            instruments=HOLDOUT_INSTRUMENTS,
        )
        if result.passed:
            return 0
        sys.stderr.write("empirical verification floors failed; detector may be tuned, floors may not\n")
        return 2
    if command == "research":
        if str(args.cycle) == "null-only":
            null_cycle = run_null_only(
                work_dir=args.work_dir,
                report_dir=args.report_dir,
                es_csv=args.es_csv,
                synthetic=synthetic_drift_tape(),
            )
            if not null_cycle.strict_gate_pass:
                sys.stderr.write("null-only: strict 7/8 FPR is above 3/32; research-run stays locked\n")
                return 2
            return 0
        if str(args.cycle) == "midpoint-d13":
            try:
                midpoint = run_midpoint_d13(
                    work_dir=args.work_dir,
                    report_dir=args.report_dir,
                    es_csv=args.es_csv,
                )
            except ValueError as exc:
                sys.stderr.write(f"midpoint-d13: {exc}\n")
                return 2
            if midpoint.overall_verdict != POWER_CLEAN:
                sys.stderr.write(f"midpoint-d13: {midpoint.overall_verdict}; no strategy-run\n")
                return 2
            return 0
        if str(args.cycle) == "midpoint-power":
            try:
                power = run_midpoint_power(
                    work_dir=args.work_dir,
                    report_dir=args.report_dir,
                    es_csv=args.es_csv,
                )
            except ValueError as exc:
                sys.stderr.write(f"midpoint-power: {exc}\n")
                return 2
            if not power.full_magnitude_clean:
                sys.stderr.write("midpoint-power: 100% magnitude is not clean; no strategy-run\n")
                return 2
            return 0
        if str(args.cycle) == "midpoint-power-floor":
            try:
                floor = run_midpoint_power_floor(
                    work_dir=args.work_dir,
                    report_dir=args.report_dir,
                    es_csv=args.es_csv,
                )
            except ValueError as exc:
                sys.stderr.write(f"midpoint-power-floor: {exc}\n")
                return 2
            if floor.null_leaked:
                sys.stderr.write("midpoint-power-floor: null leaked; no strategy-run\n")
                return 2
            return 0
        if str(args.cycle) in {"first", "four-instrument", "atr-es"}:
            try:
                assert_research_allowed(Path(args.report_dir))
            except NullLeaks as exc:
                sys.stderr.write(f"{exc}\n")
                return 2
        if str(args.cycle) == "null-audit":
            audit = run_null_audit(
                work_dir=args.work_dir,
                report_dir=args.report_dir,
                data_dir=args.data_dir,
            )
            if not audit.method_ready:
                sys.stderr.write("null-audit fail-closed: MES/MNQ/ES planted miss or null unreliable\n")
                return 2
            return 0
        if str(args.cycle) == "atr-es":
            atr = run_atr_es_cycle(
                work_dir=args.work_dir,
                report_dir=args.report_dir,
                data_dir=args.data_dir,
            )
            if atr.report.stop_reason == "positive_control_failed":
                sys.stderr.write(f"ATR ES control failed: {atr.report.control_note}\n")
                return 2
            if atr.data.usable:
                return 0
            sys.stderr.write("P2 stopped: no usable real market data\n")
            return 3
        if str(args.cycle) == "four-instrument":
            four = run_four_instrument_cycle(
                work_dir=args.work_dir,
                report_dir=args.report_dir,
                data_dir=args.data_dir,
                reuse_mes_mnq=bool(args.reuse_mes_mnq),
            )
            if four.es_nq.report.stop_reason == "positive_control_failed":
                sys.stderr.write(f"ES/NQ control failed: {four.es_nq.report.control_note}\n")
                return 2
            if four.mes_mnq.data.usable:
                if four.mes_mnq.kill_rate_flag.startswith("flag_"):
                    sys.stderr.write(f"P2 kill-rate diagnostic: {four.mes_mnq.kill_rate_flag}\n")
                if four.es_nq.report.stopped:
                    sys.stderr.write(f"ES/NQ fail-closed: {four.es_nq.report.stop_reason}\n")
                return 0
            sys.stderr.write("P2 stopped: no usable real market data\n")
            return 3
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
