"""Scheduler entrypoint: ``python -m lumina_research.monitoring daily|weekly``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, cast

from lumina_research.agents.objects import as_object_dict
from lumina_research.monitoring.config import ContinuityConfigError, load_default_config
from lumina_research.monitoring.loop import ContinuityIntegrityError, ContinuityRuntime
from lumina_research.monitoring.types import ContinuityRefused


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lumina-research-monitoring",
        description="Research Charter guardian scan (daily/weekly) plus optional replenishment check.",
    )
    parser.add_argument("cadence", choices=("daily", "weekly"), help="Guardian cadence")
    parser.add_argument("--state-dir", type=Path, required=True, help="Directory with audit/experiments/decisions")
    parser.add_argument("--report-dir", type=Path, required=True, help="Machine-readable report output directory")
    parser.add_argument("--evolution-log-dir", type=Path, default=None, help="Optional project-brain evolution log")
    parser.add_argument("--config", type=Path, default=None, help="Optional continuity limits.toml")
    parser.add_argument("--replenish", action="store_true", help="Request hypotheses if below floor (still gated)")
    parser.add_argument("--seed", type=int, default=20261028)
    return parser


def load_decisions(state_dir: Path) -> tuple[dict[str, object], ...]:
    path = state_dir / "decisions.json"
    if not path.exists():
        return ()
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ContinuityRefused("decisions.json must be a list")
    rows: list[dict[str, object]] = []
    for item in cast(list[object], loaded):
        mapping = as_object_dict(item)
        if mapping is None:
            raise ContinuityRefused("decision rows must be objects")
        rows.append(mapping)
    return tuple(rows)


def run_scan(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    state_dir: Path = args.state_dir
    report_dir: Path = args.report_dir
    state_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    try:
        config = load_default_config(args.config) if args.config is not None else load_default_config()
        runtime = ContinuityRuntime(
            audit_path=state_dir / "audit.jsonl",
            experiment_log_path=state_dir / "experiments.jsonl",
            config=config,
            evolution_log_dir=args.evolution_log_dir,
        )
        report = runtime.guardian_scan(str(args.cadence), decisions=load_decisions(state_dir), report_dir=report_dir)
        if bool(args.replenish):
            runtime.request_replenishment(seed=int(args.seed))
    except (ContinuityRefused, ContinuityConfigError, ContinuityIntegrityError) as exc:
        sys.stderr.write(f"continuity refused: {exc}\n")
        return 1
    if report.passed:
        return 0
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    return run_scan(argv)


if __name__ == "__main__":
    raise SystemExit(main())
