"""Multi-seed live-vs-OOS detection campaign. Synthetic paper/shadow paths only."""

from __future__ import annotations

import random
from collections.abc import Callable
from pathlib import Path

from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.report import (
    DetectionPath,
    MultiSeedDetectionReport,
    SeedDetectionRow,
    build_detection_report,
    build_multiseed_report,
    write_multiseed_detection_reports,
)
from lumina_research.monitoring.synthetic import (
    DEFAULT_OOS,
    decaying_path,
    gradual_decay_path,
    healthy_path,
    high_vol_healthy_path,
    oos_stats,
    regime_shift_path,
    seal_promotion_pair,
)
from lumina_research.monitoring.types import ContinuityRefused, Instrument

PathFn = Callable[[random.Random, float, float, int, int], tuple[float, ...]]

DEFAULT_CAMPAIGN_SEEDS: tuple[int, ...] = (20261028, 7, 13, 21, 42, 99, 123, 256, 1024, 4096)
DEFAULT_CAMPAIGN_INSTRUMENTS: tuple[Instrument, ...] = (
    "MES",
    "MNQ",
    "ES",
    "NQ",
    "MES",
    "MNQ",
    "ES",
    "NQ",
    "MES",
    "MNQ",
)
DEFAULT_KINDS: tuple[str, ...] = (
    "healthy",
    "abrupt_decay",
    "gradual_decay",
    "high_vol_healthy",
    "regime_shift",
)
_INSTRUMENTS: dict[str, Instrument] = {"ES": "ES", "NQ": "NQ", "MES": "MES", "MNQ": "MNQ"}


def _healthy(rng: random.Random, mean: float, stdev: float, n: int, _start: int) -> tuple[float, ...]:
    return healthy_path(rng, oos_mean=mean, oos_stdev=stdev, n=n)


def _abrupt(rng: random.Random, mean: float, stdev: float, n: int, start: int) -> tuple[float, ...]:
    return decaying_path(rng, oos_mean=mean, oos_stdev=stdev, n=n, decay_start=start)


def _gradual(rng: random.Random, mean: float, stdev: float, n: int, start: int) -> tuple[float, ...]:
    return gradual_decay_path(rng, oos_mean=mean, oos_stdev=stdev, n=n, decay_start=start)


def _high_vol(rng: random.Random, mean: float, stdev: float, n: int, _start: int) -> tuple[float, ...]:
    return high_vol_healthy_path(rng, oos_mean=mean, oos_stdev=stdev, n=n)


def _regime(rng: random.Random, mean: float, stdev: float, n: int, start: int) -> tuple[float, ...]:
    return regime_shift_path(rng, oos_mean=mean, oos_stdev=stdev, n=n, decay_start=start)


_KIND_FNS: dict[str, tuple[bool, PathFn]] = {
    "healthy": (False, _healthy),
    "abrupt_decay": (True, _abrupt),
    "gradual_decay": (True, _gradual),
    "high_vol_healthy": (False, _high_vol),
    "regime_shift": (True, _regime),
}


def run_phase4_multiseed_detection(
    *,
    audit_dir: Path,
    experiment_log_dir: Path,
    n_per_kind: int = 6,
    n_days: int = 70,
    decay_start: int = 20,
    seeds: tuple[int, ...] = DEFAULT_CAMPAIGN_SEEDS,
    instruments: tuple[Instrument, ...] = DEFAULT_CAMPAIGN_INSTRUMENTS,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    report_dir: Path | None = None,
) -> MultiSeedDetectionReport:
    if len(seeds) != len(instruments):
        raise ContinuityRefused("campaign seeds and instruments must align")
    oos = DEFAULT_OOS
    mean, stdev = oos_stats(oos)
    seed_rows: list[SeedDetectionRow] = []
    all_paths: list[DetectionPath] = []
    trial = 1
    for seed, instrument in zip(seeds, instruments, strict=True):
        mapped = _INSTRUMENTS.get(instrument)
        if mapped is None:
            raise ContinuityRefused(f"unknown instrument {instrument!r}")
        runtime = ContinuityRuntime(
            audit_path=audit_dir / f"audit-{seed}.jsonl",
            experiment_log_path=experiment_log_dir / f"exp-{seed}.jsonl",
        )
        rng = random.Random(seed)
        paths: list[DetectionPath] = []
        for kind in kinds:
            decaying, builder = _KIND_FNS[kind]
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
                series = builder(rng, mean, stdev, n_days, decay_start)
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
    report = build_multiseed_report(rows=seed_rows, paths=all_paths)
    if report_dir is not None:
        write_multiseed_detection_reports(report, report_dir)
    return report
