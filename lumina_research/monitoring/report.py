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
        handle.write(
            f"- `{payload['timestamp']}` agent=`{agent_id}` event=`{event}` signal=`{signal_id}`\n"
        )


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
        "paths": [
            {
                "signal_id": item.signal_id,
                "decaying": item.decaying,
                "detected": item.detected,
                "false_alarm": item.false_alarm,
                "time_to_detect": item.time_to_detect,
                "final_stage": item.final_stage,
            }
            for item in report.paths
        ],
    }
    (directory / "phase4_detection.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ttd = "n/a" if report.median_time_to_detect is None else f"{report.median_time_to_detect:.1f}"
    md = [
        "# Phase 4 decay detection",
        "",
        f"- seed: `{report.seed}`",
        f"- healthy: `{report.n_healthy}` decaying: `{report.n_decaying}`",
        f"- detection_rate: `{report.detection_rate:.4f}`",
        f"- false_alarm_rate: `{report.false_alarm_rate:.4f}`",
        f"- median_time_to_detect: `{ttd}`",
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
    median = None if not ttds else float(sorted(ttds)[len(ttds) // 2])
    mean = None if not ttds else float(sum(ttds) / len(ttds))
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
    )
