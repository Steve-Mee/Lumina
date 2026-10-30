"""ES midpoint D13: planted edge under fade 1.0/1.2 and breakout 1.8/0.9.

Control cycle only. No templates, no NQ, no holdout, no strategy-run.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lumina_research.cycles.daily import unique_sessions
from lumina_research.cycles.holdout import P2_HOLDOUT_START_UTC, assert_no_holdout_timestamps
from lumina_research.cycles.null_model import (
    NULL_BUILDER,
    NULL_CALIBRATED_POSITIVE_SHARE,
    default_null_seeds,
    fail_closed_hit_count,
)
from lumina_research.cycles.null_only import load_pre_holdout_es, prepare_pre_holdout
from lumina_research.cycles.p2_cycle import market_series
from lumina_research.cycles.positive_control import (
    PLANTED_POWER_FLOOR_MAGNITUDES,
    PLANTED_POWER_MAGNITUDES,
    ControlReport,
    build_control_dailies,
    required_midpoint_controls,
    run_controls,
)
from lumina_research.cycles.wf_sizes import walk_forward_sizes
from lumina_research.proof.runner import DEFAULT_REPORTS
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.static_rules import STATIC_POSITIVE_SHARE_MIN
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.walk_forward import WalkForwardError

_REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
JSON_NAME = "phase5_p2_midpoint_d13.json"
MD_NAME = "phase5_p2_midpoint_d13.md"
POWER_JSON_NAME = "phase5_p2_midpoint_power.json"
POWER_MD_NAME = "phase5_p2_midpoint_power.md"
POWER_FLOOR_JSON_NAME = "phase5_p2_midpoint_power_floor.json"
POWER_FLOOR_MD_NAME = "phase5_p2_midpoint_power_floor.md"
PREREG_NAME = "phase5_p2_midpoint_d13_preregister_2026-10-29.md"
POWER_PREREG_NAME = "phase5_p2_midpoint_power_preregister_2026-10-29.md"
POWER_FLOOR_PREREG_NAME = "phase5_p2_midpoint_power_floor_preregister_2026-10-29.md"
ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-NULLVAL-20261029T1924.md"
POWER_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-MIDPOINT-20261029T2129.md"
POWER_FLOOR_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md"
POWER_CLEAN = "clean"
POWER_PROBLEM = "power_problem"
POWER_NULL_LEAK = "null_leak"


@dataclass(frozen=True, slots=True)
class GeometryScore:
    name: str
    target_atr: float
    stop_atr: float
    planted_detected: bool
    planted_median_oos: float
    planted_pct_positive: float
    planted_dsr: float
    planted_passed_gate: bool
    effect_clears_threshold: bool
    planted_beats_null: bool
    n_a2: int
    n_edge: int
    n_seeds: int
    exact_a2: str
    exact_edge: str
    null_median_of_medians: float
    null_reliable: bool
    power_verdict: str
    n_trials: int
    n_days: int
    accepted: bool
    planted_magnitude: float = 1.0
    planted_reject_reasons: tuple[str, ...] = ()
    planted_pbo: float = 0.0
    planted_pbo_n_configs: int = 0
    planted_n_oos_windows: int = 0
    planted_n_positive_oos: int = 0


@dataclass(frozen=True, slots=True)
class MidpointD13Cycle:
    geometries: tuple[GeometryScore, ...]
    overall_verdict: str
    all_clean: bool
    json_path: Path
    md_path: Path
    n_days_es: int
    n_bars_es: int
    es_first_ts: str
    es_last_ts: str
    holdout_asserted: bool
    prereg_sha256: str


@dataclass(frozen=True, slots=True)
class MagnitudeBand:
    magnitude: float
    geometries: tuple[GeometryScore, ...]
    overall_verdict: str
    all_clean: bool


@dataclass(frozen=True, slots=True)
class MidpointPowerCycle:
    bands: tuple[MagnitudeBand, ...]
    json_path: Path
    md_path: Path
    n_days_es: int
    n_bars_es: int
    es_first_ts: str
    es_last_ts: str
    holdout_asserted: bool
    prereg_sha256: str
    full_magnitude_clean: bool
    null_leaked: bool = False
    csv_sha256: str = ""


def power_verdict(*, planted_detected: bool, n_edge: int, n_seeds: int) -> str:
    """19:24: silent null + missed plant is a power problem, not a looser gate."""
    fail_at = fail_closed_hit_count(n_seeds)
    if n_edge >= fail_at:
        return POWER_NULL_LEAK
    if planted_detected:
        return POWER_CLEAN
    return POWER_PROBLEM


def magnitude_label(magnitude: float) -> str:
    """Stable work-dir suffix; 0.125 stays 0p125, not 0p12."""
    text = f"{magnitude:.4f}".rstrip("0").rstrip(".")
    return text.replace(".", "p")


def overall_verdict(scores: tuple[GeometryScore, ...]) -> str:
    if not scores:
        return POWER_PROBLEM
    if any(item.power_verdict == POWER_NULL_LEAK for item in scores):
        return POWER_NULL_LEAK
    if any(item.power_verdict == POWER_PROBLEM for item in scores):
        return POWER_PROBLEM
    return POWER_CLEAN


def run_midpoint_d13(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    es_csv: Path | None = None,
    repo_root: Path | None = None,
) -> MidpointD13Cycle:
    """Planted + v2 null under fade 1.0/1.2 and breakout 1.8/0.9. ES only."""
    root = repo_root if repo_root is not None else _REPO
    if es_csv is None:
        raise ValueError("midpoint-d13 requires a local pre-holdout ES CSV")
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    tape = load_pre_holdout_es(es_csv)
    assert_no_holdout_timestamps(tape.bars)
    prepared = prepare_pre_holdout(tape)
    n_days = len(unique_sessions(prepared.session_dates))
    try:
        is_size, oos_size, _formed = walk_forward_sizes(n_days)
    except WalkForwardError as exc:
        raise ValueError(f"ES tape cannot form walk-forward windows: {exc}") from exc
    market = market_series(prepared)
    scores: list[GeometryScore] = []
    for name, target, stop in required_midpoint_controls():
        registry = TrialRegistry(work_dir / f"midpoint_{name}.jsonl")
        report = run_controls(
            prepared={prepared.instrument: prepared},
            registry=registry,
            audit_path=registry.audit_path,
            is_size=is_size,
            oos_size=oos_size,
            market_returns=market,
            n_days=n_days,
            block_seeds=(),
            fail_closed=False,
            geometry_mode="atr",
            target_atr=target,
            stop_atr=stop,
            null_builder=NULL_BUILDER,
        )
        scores.append(
            _score_geometry(
                name=name,
                target=float(target),
                stop=float(stop),
                report=report,
                magnitude=1.0,
            )
        )
    packed = tuple(scores)
    prereg = root / "experiments" / "reports" / PREREG_NAME
    prereg_sha = hashlib.sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else ""
    cycle = MidpointD13Cycle(
        geometries=packed,
        overall_verdict=overall_verdict(packed),
        all_clean=all(item.power_verdict == POWER_CLEAN for item in packed) and len(packed) == 2,
        json_path=report_dir / JSON_NAME,
        md_path=report_dir / MD_NAME,
        n_days_es=n_days,
        n_bars_es=len(tape.bars),
        es_first_ts=_iso_utc(tape.bars[0].ts_ns),
        es_last_ts=_iso_utc(tape.bars[-1].ts_ns),
        holdout_asserted=True,
        prereg_sha256=prereg_sha,
    )
    _write_reports(cycle, repo_root=root)
    return cycle


def run_midpoint_power(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    es_csv: Path | None = None,
    repo_root: Path | None = None,
    magnitudes: tuple[float, ...] = PLANTED_POWER_MAGNITUDES,
) -> MidpointPowerCycle:
    """100%/50%/25% planted magnitude under locked midpoints. Control only."""
    return _run_power_bands(
        work_dir=work_dir,
        report_dir=report_dir,
        es_csv=es_csv,
        repo_root=repo_root,
        magnitudes=magnitudes,
        locked=PLANTED_POWER_MAGNITUDES,
        json_name=POWER_JSON_NAME,
        md_name=POWER_MD_NAME,
        prereg_name=POWER_PREREG_NAME,
        answers_name=POWER_ANSWERS_NAME,
        title="P2 midpoint power (2026-10-29 21:29)",
        magnitude_blurb=(
            "magnitudes: `1.00`, `0.50`, `0.25` of known size "
            "(linear scale of costed session net)"
        ),
        cycle_name="midpoint-power",
        lock_error="midpoint-power magnitudes are locked to 1.0, 0.5, 0.25",
    )


def run_midpoint_power_floor(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    es_csv: Path | None = None,
    repo_root: Path | None = None,
    magnitudes: tuple[float, ...] = PLANTED_POWER_FLOOR_MAGNITUDES,
) -> MidpointPowerCycle:
    """12.5%/6.25% planted magnitude under locked midpoints. Control only."""
    return _run_power_bands(
        work_dir=work_dir,
        report_dir=report_dir,
        es_csv=es_csv,
        repo_root=repo_root,
        magnitudes=magnitudes,
        locked=PLANTED_POWER_FLOOR_MAGNITUDES,
        json_name=POWER_FLOOR_JSON_NAME,
        md_name=POWER_FLOOR_MD_NAME,
        prereg_name=POWER_FLOOR_PREREG_NAME,
        answers_name=POWER_FLOOR_ANSWERS_NAME,
        title="P2 midpoint power floor (2026-10-29 22:08)",
        magnitude_blurb=(
            "magnitudes: `0.125`, `0.0625` of known size "
            "(linear scale of costed session net; detection floor)"
        ),
        cycle_name="midpoint-power-floor",
        lock_error="midpoint-power-floor magnitudes are locked to 0.125, 0.0625",
    )


def _run_power_bands(
    *,
    work_dir: Path,
    report_dir: Path,
    es_csv: Path | None,
    repo_root: Path | None,
    magnitudes: tuple[float, ...],
    locked: tuple[float, ...],
    json_name: str,
    md_name: str,
    prereg_name: str,
    answers_name: str,
    title: str,
    magnitude_blurb: str,
    cycle_name: str,
    lock_error: str,
) -> MidpointPowerCycle:
    root = repo_root if repo_root is not None else _REPO
    if es_csv is None:
        raise ValueError(f"{cycle_name} requires a local pre-holdout ES CSV")
    if magnitudes != locked:
        raise ValueError(lock_error)
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_sha = hashlib.sha256(es_csv.read_bytes()).hexdigest()
    tape = load_pre_holdout_es(es_csv)
    assert_no_holdout_timestamps(tape.bars)
    prepared = prepare_pre_holdout(tape)
    n_days = len(unique_sessions(prepared.session_dates))
    try:
        is_size, oos_size, _formed = walk_forward_sizes(n_days)
    except WalkForwardError as exc:
        raise ValueError(f"ES tape cannot form walk-forward windows: {exc}") from exc
    market = market_series(prepared)
    packed = {prepared.instrument: prepared}
    per_mag: dict[float, list[GeometryScore]] = {float(item): [] for item in magnitudes}
    for name, target, stop in required_midpoint_controls():
        dailies = build_control_dailies(
            prepared=packed,
            is_size=is_size,
            oos_size=oos_size,
            block_seeds=(),
            geometry_mode="atr",
            target_atr=target,
            stop_atr=stop,
            null_builder=NULL_BUILDER,
        )
        for magnitude in magnitudes:
            mag_label = magnitude_label(float(magnitude))
            stem = f"{cycle_name.replace('-', '_')}_{name}_{mag_label}.jsonl"
            registry = TrialRegistry(work_dir / stem)
            report = run_controls(
                prepared=packed,
                registry=registry,
                audit_path=registry.audit_path,
                is_size=is_size,
                oos_size=oos_size,
                market_returns=market,
                n_days=n_days,
                block_seeds=(),
                fail_closed=False,
                geometry_mode="atr",
                target_atr=target,
                stop_atr=stop,
                null_builder=NULL_BUILDER,
                planted_magnitude=float(magnitude),
                control_dailies=dailies,
            )
            per_mag[float(magnitude)].append(
                _score_geometry(
                    name=name,
                    target=float(target),
                    stop=float(stop),
                    report=report,
                    magnitude=float(magnitude),
                )
            )
    bands = tuple(
        MagnitudeBand(
            magnitude=float(magnitude),
            geometries=tuple(per_mag[float(magnitude)]),
            overall_verdict=overall_verdict(tuple(per_mag[float(magnitude)])),
            all_clean=all(item.power_verdict == POWER_CLEAN for item in per_mag[float(magnitude)])
            and len(per_mag[float(magnitude)]) == 2,
        )
        for magnitude in magnitudes
    )
    prereg = root / "experiments" / "reports" / prereg_name
    prereg_sha = hashlib.sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else ""
    full = next((item for item in bands if item.magnitude == 1.0), None)
    cycle = MidpointPowerCycle(
        bands=bands,
        json_path=report_dir / json_name,
        md_path=report_dir / md_name,
        n_days_es=n_days,
        n_bars_es=len(tape.bars),
        es_first_ts=_iso_utc(tape.bars[0].ts_ns),
        es_last_ts=_iso_utc(tape.bars[-1].ts_ns),
        holdout_asserted=True,
        prereg_sha256=prereg_sha,
        full_magnitude_clean=bool(full is not None and full.all_clean),
        null_leaked=any(band.overall_verdict == POWER_NULL_LEAK for band in bands),
        csv_sha256=csv_sha,
    )
    _write_power_reports(
        cycle,
        repo_root=root,
        answers_name=answers_name,
        prereg_name=prereg_name,
        title=title,
        magnitude_blurb=magnitude_blurb,
        locked_magnitudes=locked,
    )
    return cycle


def _score_geometry(
    *,
    name: str,
    target: float,
    stop: float,
    report: ControlReport,
    magnitude: float,
) -> GeometryScore:
    audit = report.null_audit
    if audit is None:
        raise RuntimeError(f"midpoint control {name} produced no null audit")
    median = float(report.positive.median_oos)
    effect_ok = math.isfinite(median) and median > 0.0
    verdict = power_verdict(
        planted_detected=bool(report.positive.detected),
        n_edge=audit.n_edge,
        n_seeds=audit.n_seeds,
    )
    return GeometryScore(
        name=name,
        target_atr=float(target),
        stop_atr=float(stop),
        planted_detected=bool(report.positive.detected),
        planted_median_oos=median,
        planted_pct_positive=float(report.positive.pct_positive),
        planted_dsr=float(report.positive.dsr),
        planted_passed_gate=bool(report.positive.passed_gate),
        effect_clears_threshold=effect_ok,
        planted_beats_null=bool(audit.planted_beats_null),
        n_a2=audit.n_a2,
        n_edge=audit.n_edge,
        n_seeds=audit.n_seeds,
        exact_a2=audit.exact_a2 or f"{audit.n_a2}/{audit.n_seeds}",
        exact_edge=audit.exact_edge or f"{audit.n_edge}/{audit.n_seeds}",
        null_median_of_medians=float(audit.median_of_medians),
        null_reliable=bool(audit.reliable),
        power_verdict=verdict,
        n_trials=audit.n_trials_this_root,
        n_days=int(report.positive.n_days),
        accepted=bool(report.accepted),
        planted_magnitude=float(magnitude),
        planted_reject_reasons=tuple(report.positive.reject_reasons),
        planted_pbo=float(report.positive.pbo),
        planted_pbo_n_configs=int(report.positive.pbo_n_configs),
        planted_n_oos_windows=int(report.positive.n_oos_windows),
        planted_n_positive_oos=int(report.positive.n_positive_oos),
    )


def _iso_utc(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _geometry_payload(score: GeometryScore) -> dict[str, object]:
    return {
        "name": score.name,
        "target_atr": score.target_atr,
        "stop_atr": score.stop_atr,
        "planted_detected": score.planted_detected,
        "planted_median_oos": score.planted_median_oos,
        "planted_pct_positive": score.planted_pct_positive,
        "planted_dsr": score.planted_dsr,
        "planted_passed_gate": score.planted_passed_gate,
        "effect_clears_threshold": score.effect_clears_threshold,
        "planted_beats_null": score.planted_beats_null,
        "n_a2": score.n_a2,
        "n_edge": score.n_edge,
        "n_seeds": score.n_seeds,
        "exact_a2": score.exact_a2,
        "exact_edge": score.exact_edge,
        "null_median_of_medians": score.null_median_of_medians,
        "null_reliable": score.null_reliable,
        "power_verdict": score.power_verdict,
        "n_trials": score.n_trials,
        "n_days": score.n_days,
        "accepted": score.accepted,
        "planted_magnitude": score.planted_magnitude,
        "planted_reject_reasons": list(score.planted_reject_reasons),
        "planted_pbo": score.planted_pbo,
        "planted_pbo_n_configs": score.planted_pbo_n_configs,
        "planted_n_oos_windows": score.planted_n_oos_windows,
        "planted_n_positive_oos": score.planted_n_positive_oos,
        "exact_oos": (
            f"{score.planted_n_positive_oos}/{score.planted_n_oos_windows}"
            if score.planted_n_oos_windows
            else ""
        ),
    }


def _write_reports(cycle: MidpointD13Cycle, *, repo_root: Path) -> None:
    answers = repo_root / "docs" / "research" / ANSWERS_NAME
    answers_sha = hashlib.sha256(answers.read_bytes()).hexdigest() if answers.is_file() else ""
    payload = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "answers": ANSWERS_NAME,
        "answers_present": answers.is_file(),
        "answers_sha256": answers_sha,
        "prereg": PREREG_NAME,
        "prereg_sha256": cycle.prereg_sha256,
        "holdout_pin": P2_HOLDOUT_START_UTC.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "holdout_asserted": cycle.holdout_asserted,
        "holdout_opened": False,
        "nq_closed": True,
        "templates_run": False,
        "research_run": False,
        "n_seeds": len(default_null_seeds()),
        "builder": NULL_BUILDER,
        "calibrated_positive_share": NULL_CALIBRATED_POSITIVE_SHARE,
        "a2_positive_share_min": STATIC_POSITIVE_SHARE_MIN,
        "fail_at": fail_closed_hit_count(len(default_null_seeds())),
        "n_days_es": cycle.n_days_es,
        "n_bars_es": cycle.n_bars_es,
        "es_first_ts": cycle.es_first_ts,
        "es_last_ts": cycle.es_last_ts,
        "geometries": [_geometry_payload(item) for item in cycle.geometries],
        "overall_verdict": cycle.overall_verdict,
        "all_clean": cycle.all_clean,
    }
    cycle.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P2 midpoint D13 (2026-10-29 19:24)",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- answers: `{ANSWERS_NAME}` sha256 `{answers_sha}`",
        f"- pre-register: `{PREREG_NAME}` sha256 `{cycle.prereg_sha256}`",
        f"- CostModel: `{COST_MODEL_VERSION}`",
        "- holdout pin `2026-01-28T23:00:00Z`: asserted absent, unopened",
        "- NQ: closed; templates: not run; strategy-run: not run",
        f"- builder: `{NULL_BUILDER}`; seeds: `{len(default_null_seeds())}`",
        f"- planted drempel: median OOS > 0, +OOS ≥ `{STATIC_POSITIVE_SHARE_MIN:.2f}`, no decay, beats null",
        f"- null fail-at: `{fail_closed_hit_count(len(default_null_seeds()))}/32` on 7/8 `n_edge`",
        f"- ES bars: `{cycle.n_bars_es}` sessions `{cycle.n_days_es}` first `{cycle.es_first_ts}` last `{cycle.es_last_ts}`",
        f"- overall_verdict: `{cycle.overall_verdict}`",
        "",
        "## Per geometry",
        "",
        "| family | tgt/stop | planted detected | median OOS | +OOS | DSR | effect > 0 | beats null | exact A2 | exact 7/8 | verdict |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in cycle.geometries:
        lines.append(
            "| {name} | {tgt:g}/{stp:g} | {det} | {med:.6g} | {pct:.3f} | {dsr:.3f} | {eff} | {beat} | {a2} | {edge} | {verdict} |".format(
                name=item.name,
                tgt=item.target_atr,
                stp=item.stop_atr,
                det="yes" if item.planted_detected else "no",
                med=item.planted_median_oos,
                pct=item.planted_pct_positive,
                dsr=item.planted_dsr,
                eff="yes" if item.effect_clears_threshold else "no",
                beat="yes" if item.planted_beats_null else "no",
                a2=item.exact_a2,
                edge=item.exact_edge,
                verdict=item.power_verdict,
            )
        )
    cycle.md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_power_reports(
    cycle: MidpointPowerCycle,
    *,
    repo_root: Path,
    answers_name: str,
    prereg_name: str,
    title: str,
    magnitude_blurb: str,
    locked_magnitudes: tuple[float, ...],
) -> None:
    answers = repo_root / "docs" / "research" / answers_name
    answers_sha = hashlib.sha256(answers.read_bytes()).hexdigest() if answers.is_file() else ""
    payload = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "answers": answers_name,
        "answers_present": answers.is_file(),
        "answers_sha256": answers_sha,
        "prereg": prereg_name,
        "prereg_sha256": cycle.prereg_sha256,
        "csv_sha256": cycle.csv_sha256,
        "holdout_pin": P2_HOLDOUT_START_UTC.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "holdout_asserted": cycle.holdout_asserted,
        "holdout_opened": False,
        "nq_closed": True,
        "templates_run": False,
        "research_run": False,
        "n_seeds": len(default_null_seeds()),
        "builder": NULL_BUILDER,
        "calibrated_positive_share": NULL_CALIBRATED_POSITIVE_SHARE,
        "a2_positive_share_min": STATIC_POSITIVE_SHARE_MIN,
        "fail_at": fail_closed_hit_count(len(default_null_seeds())),
        "magnitudes": list(locked_magnitudes),
        "n_days_es": cycle.n_days_es,
        "n_bars_es": cycle.n_bars_es,
        "es_first_ts": cycle.es_first_ts,
        "es_last_ts": cycle.es_last_ts,
        "full_magnitude_clean": cycle.full_magnitude_clean,
        "null_leaked": cycle.null_leaked,
        "bands": [
            {
                "planted_magnitude": band.magnitude,
                "overall_verdict": band.overall_verdict,
                "all_clean": band.all_clean,
                "geometries": [_geometry_payload(item) for item in band.geometries],
            }
            for band in cycle.bands
        ],
    }
    cycle.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        f"# {title}",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- answers: `{answers_name}` sha256 `{answers_sha}`",
        f"- pre-register: `{prereg_name}` sha256 `{cycle.prereg_sha256}`",
        f"- csv sha256: `{cycle.csv_sha256}`",
        f"- CostModel: `{COST_MODEL_VERSION}`",
        "- holdout pin `2026-01-28T23:00:00Z`: asserted absent, unopened",
        "- NQ: closed; templates: not run; strategy-run: not run",
        f"- builder: `{NULL_BUILDER}`; seeds: `{len(default_null_seeds())}`",
        f"- {magnitude_blurb}",
        f"- planted drempel: median OOS > 0, +OOS ≥ `{STATIC_POSITIVE_SHARE_MIN:.2f}`, no decay, beats null",
        f"- null fail-at: `{fail_closed_hit_count(len(default_null_seeds()))}/32` on 7/8 `n_edge`",
        f"- ES bars: `{cycle.n_bars_es}` sessions `{cycle.n_days_es}` first `{cycle.es_first_ts}` last `{cycle.es_last_ts}`",
        f"- full_magnitude_clean: `{cycle.full_magnitude_clean}`",
        f"- null_leaked: `{cycle.null_leaked}`",
        "",
    ]
    for band in cycle.bands:
        lines.extend(
            [
                f"## Magnitude {band.magnitude:g}",
                "",
                f"- overall_verdict: `{band.overall_verdict}`",
                "",
                "| family | tgt/stop | detected | passed_gate | median OOS | +OOS | DSR | PBO n | exact A2 | exact 7/8 | reject_reasons | verdict |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for item in band.geometries:
            reasons = ",".join(item.planted_reject_reasons) if item.planted_reject_reasons else ""
            if item.planted_n_oos_windows:
                oos = f"{item.planted_n_positive_oos}/{item.planted_n_oos_windows}"
            else:
                oos = f"{item.planted_pct_positive:.3f}"
            lines.append(
                "| {name} | {tgt:g}/{stp:g} | {det} | {gate} | {med:.6g} | {oos} | {dsr:.3f} | {ncfg} | {a2} | {edge} | {reasons} | {verdict} |".format(
                    name=item.name,
                    tgt=item.target_atr,
                    stp=item.stop_atr,
                    det="yes" if item.planted_detected else "no",
                    gate="yes" if item.planted_passed_gate else "no",
                    med=item.planted_median_oos,
                    oos=oos,
                    dsr=item.planted_dsr,
                    ncfg=item.planted_pbo_n_configs,
                    a2=item.exact_a2,
                    edge=item.exact_edge,
                    reasons=reasons or "—",
                    verdict=item.power_verdict,
                )
            )
        lines.append("")
    cycle.md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
