"""Independent PR #63 audit campaign: never-seen seeds, not used by unit tests as data."""

from __future__ import annotations

import json
from pathlib import Path

from lumina_research.monitoring.campaign import DEFAULT_CAMPAIGN_SEEDS
from lumina_research.monitoring.report import _regime_metrics
from lumina_research.monitoring.types import ContinuityRefused
from lumina_research.proof.continuity_suite import ContinuitySuiteReport, run_independent_continuity
from lumina_research.proof.independent import (
    HOLDOUT_INSTRUMENTS,
    HOLDOUT_SEEDS,
    INDEPENDENT_SEEDS,
    assert_holdout_seeds,
)

# Chosen for this audit only. Disjoint from Phase 4 tuning, PR #63 independent, and HOLDOUT_SEEDS.
AUDIT_SEEDS: tuple[int, ...] = (
    90210,
    48151623,
    73939133,
    104729,
    611953,
    1299709,
    15485863,
    32452843,
    49979687,
    67867967,
)
AUDIT_INSTRUMENTS = HOLDOUT_INSTRUMENTS


def assert_audit_seeds(seeds: tuple[int, ...] = AUDIT_SEEDS) -> None:
    assert_holdout_seeds(seeds)
    overlap = set(seeds) & set(HOLDOUT_SEEDS)
    if overlap:
        raise ContinuityRefused(f"audit seeds overlap official HOLDOUT_SEEDS: {sorted(overlap)}")
    if set(seeds) & set(DEFAULT_CAMPAIGN_SEEDS):
        raise ContinuityRefused("audit seeds overlap Phase 4 tuning")
    if set(seeds) & set(INDEPENDENT_SEEDS):
        raise ContinuityRefused("audit seeds overlap PR #63 independent set")
    if len(seeds) != len(AUDIT_INSTRUMENTS):
        raise ContinuityRefused("audit seeds must align with instruments")


def run_audit_continuity(work_dir: Path, *, n_per_kind: int = 6, n_days: int = 70) -> ContinuitySuiteReport:
    assert_audit_seeds(AUDIT_SEEDS)
    return run_independent_continuity(
        audit_dir=work_dir / "floor",
        experiment_log_dir=work_dir / "exp",
        n_per_kind=n_per_kind,
        n_days=n_days,
        decay_start=20,
        seeds=AUDIT_SEEDS,
        instruments=AUDIT_INSTRUMENTS,
    )


def report_payload(suite: ContinuitySuiteReport) -> dict[str, object]:
    rows = []
    for item in suite.floor.by_kind:
        rows.append(
            {
                "slice": item.kind,
                "n": item.n,
                "far": item.false_alarm_rate,
                "detection": item.detection_rate,
                "ttd_max": item.max_time_to_detect,
                "ttd_median": item.median_time_to_detect,
            }
        )
    for item in suite.slow.by_kind:
        rows.append(
            {
                "slice": item.kind,
                "n": item.n,
                "far": item.false_alarm_rate,
                "detection": item.detection_rate,
                "ttd_max": item.max_time_to_detect,
                "ttd_median": item.median_time_to_detect,
            }
        )
    for item in _regime_metrics(suite.floor.paths):
        rows.append(
            {
                "slice": f"regime={item.kind}",
                "n": item.n,
                "far": item.false_alarm_rate,
                "detection": item.detection_rate,
                "ttd_max": item.max_time_to_detect,
                "ttd_median": item.median_time_to_detect,
            }
        )
    return {
        "seeds": list(AUDIT_SEEDS),
        "floor_passed": suite.floor_passed,
        "short_passed": suite.short_passed,
        "medium_passed": suite.medium_passed,
        "primary_high_vol_far": suite.primary_high_vol_far,
        "primary_normal_far": suite.primary_normal_far,
        "stress_high_vol_mixture_far": suite.stress_high_vol_mixture_far,
        "rows": rows,
    }


def write_audit_report(suite: ContinuitySuiteReport, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = report_payload(suite)
    path = directory / "phase5_audit_fresh_seeds.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
