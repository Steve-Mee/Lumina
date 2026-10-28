"""Weekly research-loop metrics. Capital-preservation violations must be 0."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from lumina_core.agent_orchestration.schemas_research import GuardianFinding
from lumina_research.agents.objects import as_object_dict
from lumina_research.diagnostics import diagnose_kill_rate
from lumina_research.monitoring.acceptance import MEANINGFUL_RAMP_DAYS, MUTATION_KILL_RATE_MIN
from lumina_research.monitoring.mutation_report import MutationFloorResult
from lumina_research.monitoring.report import DetectionReport, GuardianReport, KindMetrics, MultiSeedDetectionReport
from lumina_research.monitoring.types import LiveSignal
from lumina_research.validation.audit import utc_now_iso


@dataclass(frozen=True, slots=True)
class RealizedExpected:
    signal_id: str
    expected_oos: float
    realized: float | None
    delta: float | None
    stage: str


@dataclass(frozen=True, slots=True)
class WeeklyMetrics:
    generated_at: str
    n_hypotheses: int
    n_killed: int
    n_survivors: int
    kill_rate: float | None
    kill_rate_flag: str
    realized_vs_expected: tuple[RealizedExpected, ...]
    false_alarm_rate: float | None
    false_alarm_rate_high_vol: float | None
    detection_rate: float | None
    short_detection_rate: float | None
    medium_detection_rate: float | None
    short_median_ttd: float | None
    medium_median_ttd: float | None
    median_detection_latency: float | None
    p90_detection_latency: float | None
    max_detection_latency: float | None
    adaptation_speed: float | None
    observed_decay_ramp_days: int
    slow_decay: tuple[KindMetrics, ...]
    capital_preservation_violations: int
    mutation_kill_rate: float | None
    mutation_kill_floor_passed: bool
    guardian_passed: bool
    passed: bool


def build_weekly_metrics(
    *,
    hypotheses: Sequence[Mapping[str, object]] = (),
    signals: Sequence[LiveSignal] = (),
    live_means: Mapping[str, float | None] | None = None,
    guardian: GuardianReport | None = None,
    findings: Sequence[GuardianFinding] = (),
    detection: DetectionReport | MultiSeedDetectionReport | None = None,
    slow_decay: Sequence[KindMetrics] = (),
    mutation: MutationFloorResult | None = None,
) -> WeeklyMetrics:
    """Aggregate the research loop. Missing live means are reported as None, not invented."""
    rows = tuple(hypotheses)
    hyp_rows = tuple(item for item in rows if str(item.get("event", "hypothesis")) == "hypothesis")
    val_rows = tuple(item for item in rows if str(item.get("event")) == "validation")
    if hyp_rows or val_rows:
        n_hyp = len(hyp_rows)
        n_killed = sum(1 for item in val_rows if _killed(item))
    else:
        n_hyp = len(rows)
        n_killed = sum(1 for item in rows if _killed(item))
    n_survived = max(0, n_hyp - n_killed)
    kill_rate = None if n_hyp == 0 else n_killed / float(n_hyp)
    kill_flag = diagnose_kill_rate(kill_rate=kill_rate, n_hypotheses=n_hyp, n_survivors=n_survived)
    means: dict[str, float | None] = dict(live_means) if live_means is not None else {}
    realized: list[RealizedExpected] = []
    for signal in signals:
        live = means.get(signal.signal_id)
        delta = None if live is None else float(live) - float(signal.oos_mean)
        realized.append(
            RealizedExpected(
                signal_id=signal.signal_id,
                expected_oos=float(signal.oos_mean),
                realized=None if live is None else float(live),
                delta=delta,
                stage=signal.stage,
            )
        )
    far, detection_rate, median_ttd, p90_ttd, max_ttd = _detection_fields(detection)
    far_high, short_det, medium_det, short_ttd, medium_ttd = _horizon_fields(detection, slow_decay)
    adaptation = None if median_ttd is None else float(MEANINGFUL_RAMP_DAYS) / max(float(median_ttd), 1e-9)
    capital = sum(
        1
        for item in findings
        if item.check_id == "risk_core_untouched" and item.passed is False
    )
    mut_rate = None if mutation is None else mutation.kill_rate
    mut_ok = True if mutation is None else mutation.passed
    guardian_ok = True if guardian is None else guardian.passed
    passed = capital == 0 and mut_ok and guardian_ok and (mut_rate is None or mut_rate >= MUTATION_KILL_RATE_MIN)
    return WeeklyMetrics(
        generated_at=utc_now_iso(),
        n_hypotheses=n_hyp,
        n_killed=n_killed,
        n_survivors=n_survived,
        kill_rate=kill_rate,
        kill_rate_flag=kill_flag,
        realized_vs_expected=tuple(realized),
        false_alarm_rate=far,
        false_alarm_rate_high_vol=far_high,
        detection_rate=detection_rate,
        short_detection_rate=short_det,
        medium_detection_rate=medium_det,
        short_median_ttd=short_ttd,
        medium_median_ttd=medium_ttd,
        median_detection_latency=median_ttd,
        p90_detection_latency=p90_ttd,
        max_detection_latency=max_ttd,
        adaptation_speed=adaptation,
        observed_decay_ramp_days=MEANINGFUL_RAMP_DAYS,
        slow_decay=tuple(slow_decay),
        capital_preservation_violations=capital,
        mutation_kill_rate=mut_rate,
        mutation_kill_floor_passed=mut_ok,
        guardian_passed=guardian_ok,
        passed=passed,
    )


def write_weekly_metrics(report: WeeklyMetrics, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "generated_at": report.generated_at,
        "n_hypotheses": report.n_hypotheses,
        "n_killed": report.n_killed,
        "n_survivors": report.n_survivors,
        "kill_rate": report.kill_rate,
        "kill_rate_flag": report.kill_rate_flag,
        "realized_vs_expected": [
            {
                "signal_id": item.signal_id,
                "expected_oos": item.expected_oos,
                "realized": item.realized,
                "delta": item.delta,
                "stage": item.stage,
            }
            for item in report.realized_vs_expected
        ],
        "false_alarm_rate": report.false_alarm_rate,
        "false_alarm_rate_high_vol": report.false_alarm_rate_high_vol,
        "detection_rate": report.detection_rate,
        "short_detection_rate": report.short_detection_rate,
        "medium_detection_rate": report.medium_detection_rate,
        "short_median_ttd": report.short_median_ttd,
        "medium_median_ttd": report.medium_median_ttd,
        "median_detection_latency": report.median_detection_latency,
        "p90_detection_latency": report.p90_detection_latency,
        "max_detection_latency": report.max_detection_latency,
        "adaptation_speed": report.adaptation_speed,
        "observed_decay_ramp_days": report.observed_decay_ramp_days,
        "slow_decay": [
            {
                "kind": item.kind,
                "n": item.n,
                "detection_rate": item.detection_rate,
                "false_alarm_rate": item.false_alarm_rate,
                "median_time_to_detect": item.median_time_to_detect,
                "p90_time_to_detect": item.p90_time_to_detect,
                "max_time_to_detect": item.max_time_to_detect,
            }
            for item in report.slow_decay
        ],
        "capital_preservation_violations": report.capital_preservation_violations,
        "mutation_kill_rate": report.mutation_kill_rate,
        "mutation_kill_floor_passed": report.mutation_kill_floor_passed,
        "guardian_passed": report.guardian_passed,
        "passed": report.passed,
    }
    json_path = directory / "weekly-metrics.json"
    json_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    kill = "n/a" if report.kill_rate is None else f"{report.kill_rate:.4f}"
    far = "n/a" if report.false_alarm_rate is None else f"{report.false_alarm_rate:.4f}"
    det = "n/a" if report.detection_rate is None else f"{report.detection_rate:.4f}"
    ttd = "n/a" if report.median_detection_latency is None else f"{report.median_detection_latency:.1f}"
    adapt = "n/a" if report.adaptation_speed is None else f"{report.adaptation_speed:.3f}"
    mut = "n/a" if report.mutation_kill_rate is None else f"{report.mutation_kill_rate:.4f}"
    md = [
        "# Weekly research metrics",
        "",
        f"- generated_at: `{report.generated_at}`",
        f"- hypotheses: `{report.n_hypotheses}` killed: `{report.n_killed}` survivors: `{report.n_survivors}`",
        f"- kill_rate: `{kill}` flag: `{report.kill_rate_flag}`",
        f"- false_alarm_rate: `{far}` high_vol: `{report.false_alarm_rate_high_vol}`",
        f"- detection_rate: `{det}` short: `{report.short_detection_rate}` medium: `{report.medium_detection_rate}`",
        f"- median_detection_latency: `{ttd}`",
        f"- adaptation_speed (ramp/TTD): `{adapt}` vs observed decay ramp `{report.observed_decay_ramp_days}` days",
        f"- capital_preservation_violations: `{report.capital_preservation_violations}` (must be 0)",
        f"- mutation_kill_rate: `{mut}` floor_passed: `{report.mutation_kill_floor_passed}`",
        f"- guardian_passed: `{report.guardian_passed}`",
        f"- passed: `{report.passed}`",
        "",
    ]
    (directory / "weekly-metrics.md").write_text("\n".join(md), encoding="utf-8")
    return json_path


def load_hypothesis_rows(path: Path) -> tuple[dict[str, object], ...]:
    """Parse an experiment JSONL. Rows without a hypothesis event are skipped."""
    if not path.is_file():
        return ()
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            loaded: object = json.loads(line)
        except json.JSONDecodeError:
            continue
        mapping = as_object_dict(loaded)
        if mapping is None:
            continue
        event = str(mapping.get("event", ""))
        metrics_raw = mapping.get("metrics")
        metrics = as_object_dict(metrics_raw) if metrics_raw is not None else None
        inner = as_object_dict(metrics.get("metrics")) if metrics is not None else None
        if event in {"hypothesis", "validation"}:
            row: dict[str, object] = dict(mapping)
            if inner is not None:
                row["inner_metrics"] = inner
            rows.append(row)
    return tuple(rows)


def _killed(item: Mapping[str, object]) -> bool:
    if item.get("passed") is False:
        return True
    if item.get("killed") is True:
        return True
    metrics = as_object_dict(item.get("metrics"))
    if metrics is not None:
        if metrics.get("passed") is False:
            return True
        inner = as_object_dict(metrics.get("metrics"))
        if inner is not None and inner.get("passed") is False:
            return True
        reasons = metrics.get("reject_reason")
        failed = metrics.get("failed_checks")
        empty_reason = reasons is None or reasons == "" or reasons == []
        if not empty_reason or (isinstance(failed, list) and failed):
            event = str(item.get("event", ""))
            if event == "validation":
                return True
    return False


def _detection_fields(
    detection: DetectionReport | MultiSeedDetectionReport | None,
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    if detection is None:
        return None, None, None, None, None
    max_ttd: float | None
    if isinstance(detection, MultiSeedDetectionReport):
        max_ttd = detection.max_time_to_detect
        p90 = detection.p90_time_to_detect
    else:
        ttds = tuple(item.time_to_detect for item in detection.paths if item.time_to_detect is not None)
        max_ttd = None if not ttds else float(max(ttds))
        p90 = detection.p90_time_to_detect
    return (
        detection.false_alarm_rate,
        detection.detection_rate,
        detection.median_time_to_detect,
        p90,
        max_ttd,
    )


def _horizon_fields(
    detection: DetectionReport | MultiSeedDetectionReport | None,
    slow_decay: Sequence[KindMetrics],
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    far_high: float | None = None
    short_det: float | None = None
    medium_det: float | None = None
    short_ttd: float | None = None
    medium_ttd: float | None = None
    if isinstance(detection, MultiSeedDetectionReport):
        high = tuple(item for item in detection.by_kind if "high_vol" in item.kind)
        if high:
            alarms = sum(item.n_false_alarms for item in high)
            denom = sum(item.n for item in high)
            far_high = None if denom == 0 else alarms / float(denom)
        decaying = tuple(
            item
            for item in detection.by_kind
            if item.kind not in {"healthy_laplace", "high_vol_mixture"} and "slow" not in item.kind
        )
        if decaying:
            detected = sum(item.n_detected for item in decaying)
            n_dec = sum(item.n for item in decaying)
            short_det = None if n_dec == 0 else detected / float(n_dec)
            ttds = tuple(item.median_time_to_detect for item in decaying if item.median_time_to_detect is not None)
            short_ttd = None if not ttds else float(sorted(ttds)[len(ttds) // 2])
    if slow_decay:
        detected_s = sum(item.n_detected for item in slow_decay)
        n_slow = sum(item.n for item in slow_decay)
        medium_det = None if n_slow == 0 else detected_s / float(n_slow)
        ttds_s = tuple(item.median_time_to_detect for item in slow_decay if item.median_time_to_detect is not None)
        medium_ttd = None if not ttds_s else float(sorted(ttds_s)[len(ttds_s) // 2])
    return far_high, short_det, medium_det, short_ttd, medium_ttd
