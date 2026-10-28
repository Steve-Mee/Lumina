"""Continuity reports, experiment JSONL, and optional project-brain evolution log."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from lumina_research.agents.experiment_log import log_experiment
from lumina_research.validation.audit import utc_now_iso


@dataclass(frozen=True, slots=True)
class DetectionPath:
    signal_id: str
    decaying: bool
    detected: bool
    false_alarm: bool
    time_to_detect: int | None
    final_stage: str
    kind: str = ""
    vol_regime: str = "normal"
    n_normal_windows: int = 0
    n_high_vol_windows: int = 0


@dataclass(frozen=True, slots=True)
class DetectionReport:
    seed: int
    n_healthy: int
    n_decaying: int
    n_detected: int
    n_false_alarms: int
    detection_rate: float
    false_alarm_rate: float
    median_time_to_detect: float | None
    mean_time_to_detect: float | None
    paths: tuple[DetectionPath, ...]
    p10_time_to_detect: float | None = None
    p90_time_to_detect: float | None = None


@dataclass(frozen=True, slots=True)
class KindMetrics:
    kind: str
    n: int
    n_detected: int
    n_false_alarms: int
    detection_rate: float
    false_alarm_rate: float
    median_time_to_detect: float | None
    p90_time_to_detect: float | None
    max_time_to_detect: float | None


@dataclass(frozen=True, slots=True)
class SeedDetectionRow:
    seed: int
    instrument: str
    n_signals: int
    detection_rate: float
    false_alarm_rate: float
    median_time_to_detect: float | None
    mean_time_to_detect: float | None


@dataclass(frozen=True, slots=True)
class MultiSeedDetectionReport:
    seeds: tuple[SeedDetectionRow, ...]
    n_signals: int
    n_seeds: int
    n_healthy: int
    n_decaying: int
    n_detected: int
    n_false_alarms: int
    detection_rate: float
    false_alarm_rate: float
    median_time_to_detect: float | None
    mean_time_to_detect: float | None
    p10_time_to_detect: float | None
    p90_time_to_detect: float | None
    max_time_to_detect: float | None
    time_to_detect: tuple[int, ...]
    by_kind: tuple[KindMetrics, ...]
    paths: tuple[DetectionPath, ...]
    by_regime: tuple[KindMetrics, ...] = ()


@dataclass(frozen=True, slots=True)
class GuardianReport:
    cadence: str
    n_signals: int
    n_checks: int
    n_ok: int
    n_warn: int
    n_violations: int
    suspend_proposals: tuple[str, ...]
    finding_ids: tuple[str, ...]
    passed: bool


def log_decision(
    *,
    path: Path,
    agent_id: str,
    event: str,
    signal_id: str,
    metrics: Mapping[str, object],
    evolution_log_dir: Path | None = None,
    reject_reason: str | None = None,
    failed_checks: tuple[str, ...] = (),
) -> None:
    log_experiment(
        path=path,
        agent_id=agent_id,
        event=event,
        hypothesis_id=signal_id,
        rationale=None,
        metrics=dict(metrics),
        reject_reason=reject_reason,
        failed_checks=failed_checks,
    )
    if evolution_log_dir is None:
        return
    evolution_log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": utc_now_iso(),
        "agent_id": agent_id,
        "event": event,
        "signal_id": signal_id,
        "metrics": dict(metrics),
        "reject_reason": reject_reason,
        "failed_checks": list(failed_checks),
    }
    line = json.dumps(payload, sort_keys=True, default=str) + "\n"
    target = evolution_log_dir / "phase4-continuity.jsonl"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
    weekly = evolution_log_dir / "phase4-continuity.md"
    if not weekly.exists():
        weekly.write_text("# Phase 4 continuity decisions\n\n", encoding="utf-8")
    with weekly.open("a", encoding="utf-8") as handle:
        handle.write(f"- `{payload['timestamp']}` agent=`{agent_id}` event=`{event}` signal=`{signal_id}`\n")


def write_detection_reports(report: DetectionReport, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "seed": report.seed,
        "n_healthy": report.n_healthy,
        "n_decaying": report.n_decaying,
        "n_detected": report.n_detected,
        "n_false_alarms": report.n_false_alarms,
        "detection_rate": report.detection_rate,
        "false_alarm_rate": report.false_alarm_rate,
        "median_time_to_detect": report.median_time_to_detect,
        "mean_time_to_detect": report.mean_time_to_detect,
        "p10_time_to_detect": report.p10_time_to_detect,
        "p90_time_to_detect": report.p90_time_to_detect,
        "paths": [
            {
                "signal_id": item.signal_id,
                "decaying": item.decaying,
                "detected": item.detected,
                "false_alarm": item.false_alarm,
                "time_to_detect": item.time_to_detect,
                "final_stage": item.final_stage,
                "kind": item.kind,
                "vol_regime": item.vol_regime,
                "n_normal_windows": item.n_normal_windows,
                "n_high_vol_windows": item.n_high_vol_windows,
            }
            for item in report.paths
        ],
    }
    (directory / "phase4_detection.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ttd = "n/a" if report.median_time_to_detect is None else f"{report.median_time_to_detect:.1f}"
    md = [
        "# Phase 4 decay detection",
        "",
        f"- seed: `{report.seed}`",
        f"- healthy: `{report.n_healthy}` decaying: `{report.n_decaying}`",
        f"- detection_rate: `{report.detection_rate:.4f}`",
        f"- false_alarm_rate: `{report.false_alarm_rate:.4f}`",
        f"- median_time_to_detect: `{ttd}`",
        f"- p10_time_to_detect: `{report.p10_time_to_detect}`",
        f"- p90_time_to_detect: `{report.p90_time_to_detect}`",
        "",
    ]
    (directory / "phase4_detection.md").write_text("\n".join(md), encoding="utf-8")


def write_guardian_report(report: GuardianReport, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"guardian-{report.cadence}.json"
    body = {
        "cadence": report.cadence,
        "n_signals": report.n_signals,
        "n_checks": report.n_checks,
        "n_ok": report.n_ok,
        "n_warn": report.n_warn,
        "n_violations": report.n_violations,
        "suspend_proposals": list(report.suspend_proposals),
        "finding_ids": list(report.finding_ids),
        "passed": report.passed,
    }
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_detection_report(*, seed: int, paths: Sequence[DetectionPath]) -> DetectionReport:
    rows = tuple(paths)
    healthy = tuple(item for item in rows if not item.decaying)
    decaying = tuple(item for item in rows if item.decaying)
    detected = tuple(item for item in decaying if item.detected)
    false_alarms = tuple(item for item in healthy if item.false_alarm)
    ttds = tuple(item.time_to_detect for item in detected if item.time_to_detect is not None)
    ordered = tuple(sorted(ttds))
    median = None if not ordered else float(ordered[len(ordered) // 2])
    mean = None if not ordered else float(sum(ordered) / len(ordered))
    p10 = None if not ordered else float(ordered[max(0, int(0.10 * (len(ordered) - 1)))])
    p90 = None if not ordered else float(ordered[min(len(ordered) - 1, int(0.90 * (len(ordered) - 1)))])
    return DetectionReport(
        seed=seed,
        n_healthy=len(healthy),
        n_decaying=len(decaying),
        n_detected=len(detected),
        n_false_alarms=len(false_alarms),
        detection_rate=(len(detected) / len(decaying)) if decaying else 0.0,
        false_alarm_rate=(len(false_alarms) / len(healthy)) if healthy else 0.0,
        median_time_to_detect=median,
        mean_time_to_detect=mean,
        paths=rows,
        p10_time_to_detect=p10,
        p90_time_to_detect=p90,
    )


def _kind_metrics(paths: Sequence[DetectionPath]) -> tuple[KindMetrics, ...]:
    names = tuple(dict.fromkeys(item.kind or ("decaying" if item.decaying else "healthy") for item in paths))
    rows: list[KindMetrics] = []
    for name in names:
        group = tuple(item for item in paths if (item.kind or ("decaying" if item.decaying else "healthy")) == name)
        decaying = tuple(item for item in group if item.decaying)
        healthy = tuple(item for item in group if not item.decaying)
        detected = tuple(item for item in decaying if item.detected)
        false_alarms = tuple(item for item in healthy if item.false_alarm)
        ttds = tuple(sorted(item.time_to_detect for item in detected if item.time_to_detect is not None))
        p90 = None if not ttds else float(ttds[min(len(ttds) - 1, int(0.90 * (len(ttds) - 1)))])
        rows.append(
            KindMetrics(
                kind=name,
                n=len(group),
                n_detected=len(detected),
                n_false_alarms=len(false_alarms),
                detection_rate=(len(detected) / len(decaying)) if decaying else 0.0,
                false_alarm_rate=(len(false_alarms) / len(healthy)) if healthy else 0.0,
                median_time_to_detect=None if not ttds else float(ttds[len(ttds) // 2]),
                p90_time_to_detect=p90,
                max_time_to_detect=None if not ttds else float(ttds[-1]),
            )
        )
    return tuple(rows)


def _path_regime(item: DetectionPath) -> str:
    """Majority ready-window label. Alarm-time vol_regime stays on the path for logs."""
    if item.n_high_vol_windows > item.n_normal_windows:
        return "high_vol"
    return "normal"


def _regime_metrics(paths: Sequence[DetectionPath]) -> tuple[KindMetrics, ...]:
    grouped: list[DetectionPath] = []
    for item in paths:
        if item.kind == "high_vol_mixture":
            continue
        grouped.append(
            DetectionPath(
                signal_id=item.signal_id,
                decaying=item.decaying,
                detected=item.detected,
                false_alarm=item.false_alarm,
                time_to_detect=item.time_to_detect,
                final_stage=item.final_stage,
                kind=_path_regime(item),
                vol_regime=item.vol_regime,
                n_normal_windows=item.n_normal_windows,
                n_high_vol_windows=item.n_high_vol_windows,
            )
        )
    rows = {item.kind: item for item in _kind_metrics(grouped)}
    ordered = tuple(rows[name] for name in ("normal", "high_vol") if name in rows)
    extra = tuple(item for item in rows.values() if item.kind not in {"normal", "high_vol"})
    return ordered + extra


def build_multiseed_report(
    *, rows: Sequence[SeedDetectionRow], paths: Sequence[DetectionPath]
) -> MultiSeedDetectionReport:
    pooled = build_detection_report(seed=0, paths=paths)
    ttds = tuple(item.time_to_detect for item in paths if item.decaying and item.time_to_detect is not None)
    return MultiSeedDetectionReport(
        seeds=tuple(rows),
        n_signals=len(tuple(paths)),
        n_seeds=len(tuple(rows)),
        n_healthy=pooled.n_healthy,
        n_decaying=pooled.n_decaying,
        n_detected=pooled.n_detected,
        n_false_alarms=pooled.n_false_alarms,
        detection_rate=pooled.detection_rate,
        false_alarm_rate=pooled.false_alarm_rate,
        median_time_to_detect=pooled.median_time_to_detect,
        mean_time_to_detect=pooled.mean_time_to_detect,
        p10_time_to_detect=pooled.p10_time_to_detect,
        p90_time_to_detect=pooled.p90_time_to_detect,
        max_time_to_detect=None if not ttds else float(max(ttds)),
        time_to_detect=ttds,
        by_kind=_kind_metrics(paths),
        paths=tuple(paths),
        by_regime=_regime_metrics(paths),
    )


def write_multiseed_detection_reports(report: MultiSeedDetectionReport, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "n_signals": report.n_signals,
        "n_seeds": report.n_seeds,
        "n_healthy": report.n_healthy,
        "n_decaying": report.n_decaying,
        "n_detected": report.n_detected,
        "n_false_alarms": report.n_false_alarms,
        "detection_rate": report.detection_rate,
        "false_alarm_rate": report.false_alarm_rate,
        "median_time_to_detect": report.median_time_to_detect,
        "mean_time_to_detect": report.mean_time_to_detect,
        "p10_time_to_detect": report.p10_time_to_detect,
        "p90_time_to_detect": report.p90_time_to_detect,
        "max_time_to_detect": report.max_time_to_detect,
        "time_to_detect": list(report.time_to_detect),
        "by_kind": [
            {
                "kind": item.kind,
                "n": item.n,
                "n_detected": item.n_detected,
                "n_false_alarms": item.n_false_alarms,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "p90_time_to_detect": item.p90_time_to_detect,
                "max_time_to_detect": item.max_time_to_detect,
            }
            for item in report.by_kind
        ],
        "by_regime": [
            {
                "kind": item.kind,
                "n": item.n,
                "n_detected": item.n_detected,
                "n_false_alarms": item.n_false_alarms,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "p90_time_to_detect": item.p90_time_to_detect,
                "max_time_to_detect": item.max_time_to_detect,
            }
            for item in report.by_regime
        ],
        "seeds": [
            {
                "seed": item.seed,
                "instrument": item.instrument,
                "n_signals": item.n_signals,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "mean_time_to_detect": item.mean_time_to_detect,
            }
            for item in report.seeds
        ],
    }
    (directory / "phase4_detection_multiseed.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ttd = "n/a" if report.median_time_to_detect is None else f"{report.median_time_to_detect:.1f}"
    md = [
        "# Phase 4 multi-seed decay detection",
        "",
        f"- seeds: `{report.n_seeds}` signals: `{report.n_signals}`",
        f"- detection_rate: `{report.detection_rate:.4f}`",
        f"- false_alarm_rate: `{report.false_alarm_rate:.4f}`",
        f"- median_time_to_detect: `{ttd}`",
        f"- p10_time_to_detect: `{report.p10_time_to_detect}`",
        f"- p90_time_to_detect: `{report.p90_time_to_detect}`",
        f"- max_time_to_detect: `{report.max_time_to_detect}`",
        "",
        "| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |",
        "|---|---|---|---|---|---|---|",
    ]
    for kind_row in report.by_kind:
        mid = "n/a" if kind_row.median_time_to_detect is None else f"{kind_row.median_time_to_detect:.1f}"
        p90 = "n/a" if kind_row.p90_time_to_detect is None else f"{kind_row.p90_time_to_detect:.1f}"
        mx = "n/a" if kind_row.max_time_to_detect is None else f"{kind_row.max_time_to_detect:.1f}"
        md.append(
            f"| {kind_row.kind} | {kind_row.n} | {kind_row.detection_rate:.4f} | {kind_row.false_alarm_rate:.4f} | {mid} | {p90} | {mx} |"
        )
    if report.by_regime:
        md.extend(
            [
                "",
                "| regime | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for kind_row in report.by_regime:
            mid = "n/a" if kind_row.median_time_to_detect is None else f"{kind_row.median_time_to_detect:.1f}"
            p90 = "n/a" if kind_row.p90_time_to_detect is None else f"{kind_row.p90_time_to_detect:.1f}"
            mx = "n/a" if kind_row.max_time_to_detect is None else f"{kind_row.max_time_to_detect:.1f}"
            md.append(
                f"| {kind_row.kind} | {kind_row.n} | {kind_row.detection_rate:.4f} | {kind_row.false_alarm_rate:.4f} | {mid} | {p90} | {mx} |"
            )
    md.extend(
        ["", "| seed | instrument | n | detection_rate | false_alarm_rate | median TTD |", "|---|---|---|---|---|---|"]
    )
    for seed_row in report.seeds:
        mid = "n/a" if seed_row.median_time_to_detect is None else f"{seed_row.median_time_to_detect:.1f}"
        md.append(
            f"| {seed_row.seed} | {seed_row.instrument} | {seed_row.n_signals} | {seed_row.detection_rate:.4f} | {seed_row.false_alarm_rate:.4f} | {mid} |"
        )
    md.append("")
    (directory / "phase4_detection_multiseed.md").write_text("\n".join(md), encoding="utf-8")
