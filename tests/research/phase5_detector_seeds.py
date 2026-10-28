"""Pre-registered never-seen seeds for the high-vol DD detector fix verify.

Committed before the campaign is run. Disjoint from Phase 4 tuning, PR #63
independent, HOLDOUT_SEEDS, and the prior AUDIT_SEEDS set.
"""

from __future__ import annotations

import json
from pathlib import Path

from lumina_research.monitoring.campaign import DEFAULT_CAMPAIGN_SEEDS
from lumina_research.monitoring.types import ContinuityRefused
from lumina_research.proof.continuity_suite import ContinuitySuiteReport, run_independent_continuity
from lumina_research.proof.independent import (
    HOLDOUT_INSTRUMENTS,
    HOLDOUT_SEEDS,
    INDEPENDENT_SEEDS,
    assert_holdout_seeds,
)
from tests.research.phase5_audit_campaign import AUDIT_SEEDS, report_payload

# Chosen 2026-10-28, before running the detector-fix verify. Ten unique primes.
DETECTOR_FIX_SEEDS: tuple[int, ...] = (
    10007,
    10009,
    10037,
    10039,
    10061,
    10067,
    10069,
    10079,
    10091,
    10093,
)
DETECTOR_FIX_INSTRUMENTS = HOLDOUT_INSTRUMENTS


def assert_detector_fix_seeds(seeds: tuple[int, ...] = DETECTOR_FIX_SEEDS) -> None:
    assert_holdout_seeds(seeds)
    overlap_holdout = set(seeds) & set(HOLDOUT_SEEDS)
    if overlap_holdout:
        raise ContinuityRefused(f"detector-fix seeds overlap HOLDOUT_SEEDS: {sorted(overlap_holdout)}")
    if set(seeds) & set(DEFAULT_CAMPAIGN_SEEDS):
        raise ContinuityRefused("detector-fix seeds overlap Phase 4 tuning")
    if set(seeds) & set(INDEPENDENT_SEEDS):
        raise ContinuityRefused("detector-fix seeds overlap PR #63 independent set")
    if set(seeds) & set(AUDIT_SEEDS):
        raise ContinuityRefused("detector-fix seeds overlap AUDIT_SEEDS")
    if len(set(seeds)) != len(seeds):
        raise ContinuityRefused("detector-fix seeds must be unique")
    if len(seeds) != len(DETECTOR_FIX_INSTRUMENTS):
        raise ContinuityRefused("detector-fix seeds must align with instruments")


def run_detector_fix_continuity(work_dir: Path, *, n_per_kind: int = 6, n_days: int = 70) -> ContinuitySuiteReport:
    assert_detector_fix_seeds(DETECTOR_FIX_SEEDS)
    return run_independent_continuity(
        audit_dir=work_dir / "floor",
        experiment_log_dir=work_dir / "exp",
        n_per_kind=n_per_kind,
        n_days=n_days,
        decay_start=20,
        seeds=DETECTOR_FIX_SEEDS,
        instruments=DETECTOR_FIX_INSTRUMENTS,
    )


def write_detector_fix_report(suite: ContinuitySuiteReport, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = report_payload(suite)
    payload["seeds"] = list(DETECTOR_FIX_SEEDS)
    path = directory / "phase5_detector_fix_seeds.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
