"""Independent Phase 4 FAR/detection campaign, plus honest slow-decay reporting."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from lumina_research.monitoring.acceptance import (
    CAMPAIGN_MIN_SEEDS,
    CAMPAIGN_MIN_SIGNALS,
    DETECTION_RATE_MIN,
    FAR_HEALTHY_MAX,
    FAR_HIGH_VOL_MAX,
    FAR_HIGH_VOL_TARGET,
    TTD_MAX_TRADING_DAYS,
    TTD_MEDIUM_MAX_TRADING_DAYS,
)
from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.report import (
    DetectionPath,
    KindMetrics,
    MultiSeedDetectionReport,
    SeedDetectionRow,
    build_detection_report,
    build_multiseed_report,
)
from lumina_research.monitoring.synthetic import oos_stats, seal_promotion_pair
from lumina_research.monitoring.types import ContinuityRefused
from lumina_research.proof.independent import (
    FLOOR_KINDS,
    INDEPENDENT_INSTRUMENTS,
    INDEPENDENT_OOS,
    INDEPENDENT_SEEDS,
    SHORT_DECAY_KINDS,
    SLOW_KINDS,
    assert_independent_seeds,
    decaying_kind,
    healthy_kind,
    map_instrument,
    path_for,
)


@dataclass(frozen=True, slots=True)
class ContinuitySuiteReport:
    floor: MultiSeedDetectionReport
    slow: MultiSeedDetectionReport
    floor_passed: bool
    short_passed: bool
    medium_passed: bool
    slow_notes: str


def run_independent_continuity(
    *,
    audit_dir: Path,
    experiment_log_dir: Path,
    n_per_kind: int = 6,
    n_days: int = 70,
    decay_start: int = 20,
    seeds: tuple[int, ...] = INDEPENDENT_SEEDS,
    instruments: tuple[str, ...] = INDEPENDENT_INSTRUMENTS,
    floor_kinds: tuple[str, ...] = FLOOR_KINDS,
    slow_kinds: tuple[str, ...] = SLOW_KINDS,
) -> ContinuitySuiteReport:
    assert_independent_seeds(seeds)
    if len(seeds) != len(instruments):
        raise ContinuityRefused("campaign seeds and instruments must align")
    floor = _campaign(
        audit_dir=audit_dir / "floor",
        experiment_log_dir=experiment_log_dir / "floor",
        n_per_kind=n_per_kind,
        n_days=n_days,
        decay_start=decay_start,
        seeds=seeds,
        instruments=instruments,
        kinds=floor_kinds,
    )
    slow_days = max(n_days, decay_start + 61)
    slow = _campaign(
        audit_dir=audit_dir / "slow",
        experiment_log_dir=experiment_log_dir / "slow",
        n_per_kind=n_per_kind,
        n_days=slow_days,
        decay_start=decay_start,
        seeds=seeds,
        instruments=instruments,
        kinds=slow_kinds,
    )
    short_passed = _floor_holds(floor, n_signals_floor=len(seeds) * len(floor_kinds) * n_per_kind)
    medium_passed = _medium_holds(slow, n_signals_floor=len(seeds) * len(slow_kinds) * n_per_kind)
    floor_passed = short_passed and medium_passed
    note = (
        "Two horizons, reported separately. Short/material breaks: detection >= 0.85 within "
        f"{TTD_MAX_TRADING_DAYS} trading days. Slow 30/45/60-day ramps: detection >= 0.85 within "
        f"{TTD_MEDIUM_MAX_TRADING_DAYS} trading days (target 40). High-vol FAR hard cap "
        f"{FAR_HIGH_VOL_MAX:.2f}, target {FAR_HIGH_VOL_TARGET:.2f}; 0.12 is not a pass."
    )
    return ContinuitySuiteReport(
        floor=floor,
        slow=slow,
        floor_passed=floor_passed,
        short_passed=short_passed,
        medium_passed=medium_passed,
        slow_notes=note,
    )


def _campaign(
    *,
    audit_dir: Path,
    experiment_log_dir: Path,
    n_per_kind: int,
    n_days: int,
    decay_start: int,
    seeds: tuple[int, ...],
    instruments: tuple[str, ...],
    kinds: tuple[str, ...],
) -> MultiSeedDetectionReport:
    oos = INDEPENDENT_OOS
    mean, stdev = oos_stats(oos)
    seed_rows: list[SeedDetectionRow] = []
    all_paths: list[DetectionPath] = []
    trial = 1
    for seed, instrument in zip(seeds, instruments, strict=True):
        mapped = map_instrument(instrument)
        runtime = ContinuityRuntime(
            audit_path=audit_dir / f"audit-{seed}.jsonl",
            experiment_log_path=experiment_log_dir / f"exp-{seed}.jsonl",
        )
        rng = random.Random(seed)
        paths: list[DetectionPath] = []
        for kind in kinds:
            decaying = decaying_kind(kind)
            for index in range(n_per_kind):
                hyp = f"hyp-{seed}-{kind}-{index}"
                candidate, validation = seal_promotion_pair(
                    runtime.authority,
                    hypothesis_id=hyp,
                    config_id=hyp,
                    trial_id=trial,
                    instrument=mapped,
                    quantity=2.0,
                    notional=10_000.0,
                    oos=oos,
                )
                trial += 1
                runtime.admit(candidate, validation)
                series = path_for(
                    kind, rng, oos_mean=mean, oos_stdev=stdev, n=n_days, decay_start=decay_start
                )
                detect_day: int | None = None
                for day, metric in enumerate(series):
                    updated = runtime.observe(hyp, metric)
                    if detect_day is None and updated.stage != "active":
                        detect_day = max(0, day - decay_start) if decaying else day
                signal = runtime.registry.require(hyp)
                flagged = signal.stage != "active"
                paths.append(
                    DetectionPath(
                        signal_id=hyp,
                        decaying=decaying,
                        detected=flagged if decaying else False,
                        false_alarm=flagged if not decaying else False,
                        time_to_detect=detect_day if flagged else None,
                        final_stage=signal.stage,
                        kind=kind,
                    )
                )
        seed_report = build_detection_report(seed=seed, paths=paths)
        seed_rows.append(
            SeedDetectionRow(
                seed=seed,
                instrument=mapped,
                n_signals=len(paths),
                detection_rate=seed_report.detection_rate,
                false_alarm_rate=seed_report.false_alarm_rate,
                median_time_to_detect=seed_report.median_time_to_detect,
                mean_time_to_detect=seed_report.mean_time_to_detect,
            )
        )
        all_paths.extend(paths)
    return build_multiseed_report(rows=seed_rows, paths=all_paths)


def _size_ok(report: MultiSeedDetectionReport, *, n_signals_floor: int) -> bool:
    if report.n_seeds < CAMPAIGN_MIN_SEEDS and n_signals_floor >= CAMPAIGN_MIN_SIGNALS:
        return False
    if n_signals_floor >= CAMPAIGN_MIN_SIGNALS and report.n_signals < CAMPAIGN_MIN_SIGNALS:
        return False
    return True


def _short_holds(report: MultiSeedDetectionReport, *, n_signals_floor: int) -> bool:
    if not _size_ok(report, n_signals_floor=n_signals_floor):
        return False
    for kind_row in report.by_kind:
        band = healthy_kind(kind_row.kind)
        if band == "healthy" and kind_row.false_alarm_rate > FAR_HEALTHY_MAX:
            return False
        if band == "high_vol" and kind_row.false_alarm_rate > FAR_HIGH_VOL_MAX:
            return False
        if kind_row.kind in SHORT_DECAY_KINDS:
            if kind_row.detection_rate < DETECTION_RATE_MIN:
                return False
            if kind_row.max_time_to_detect is None or kind_row.max_time_to_detect > TTD_MAX_TRADING_DAYS:
                return False
    return True


def _medium_holds(report: MultiSeedDetectionReport, *, n_signals_floor: int) -> bool:
    if not _size_ok(report, n_signals_floor=n_signals_floor):
        return False
    slow = frozenset(SLOW_KINDS)
    for kind_row in report.by_kind:
        if kind_row.kind not in slow:
            continue
        if kind_row.detection_rate < DETECTION_RATE_MIN:
            return False
        if kind_row.max_time_to_detect is None or kind_row.max_time_to_detect > TTD_MEDIUM_MAX_TRADING_DAYS:
            return False
    return True


def _floor_holds(report: MultiSeedDetectionReport, *, n_signals_floor: int) -> bool:
    """Back-compat alias: short-horizon Phase 4 floors on the independent floor kinds."""
    return _short_holds(report, n_signals_floor=n_signals_floor)


def kind_rows(report: MultiSeedDetectionReport) -> tuple[KindMetrics, ...]:
    return report.by_kind
