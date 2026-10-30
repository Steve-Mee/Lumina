"""Null-only FPR validation. No templates, no NQ, no holdout, no strategy-run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lumina_research.cycles.daily import unique_sessions
from lumina_research.cycles.data import LoadedTape, ResearchBar, read_csv_bars
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, P2_HOLDOUT_START_UTC, assert_no_holdout_timestamps
from lumina_research.cycles.null_lock import NULL_ONLY_JSON
from lumina_research.cycles.null_model import (
    NULL_BUILDER_V1,
    NULL_BUILDER_V2,
    NULL_CALIBRATED_POSITIVE_SHARE,
    classify_null_a2,
    default_null_seeds,
)
from lumina_research.cycles.p2_cycle import market_series
from lumina_research.cycles.positive_control import run_controls
from lumina_research.cycles.prepare import PreparedTape, prepare_tape
from lumina_research.cycles.wf_sizes import walk_forward_sizes
from lumina_research.proof.runner import DEFAULT_REPORTS
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.walk_forward import WalkForwardError

_REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
MD_NAME = "phase5_p2_null_only_validation.md"
ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-NULLGATE-20261029T1817.md"
STRENGTHENING = (
    "v2 linear_magnitude: OLS linear detrend of session OC vs time index "
    "inside each WF partition, session-shuffle residual signs, count-balance "
    "|n_pos-n_neg|<=1, greedy magnitude-balance on |OC|. ISO-week block of "
    "planted signs stays report-only extra (8 seeds) and is skipped here."
)


@dataclass(frozen=True, slots=True)
class BuilderScore:
    builder: str
    n_a2: int
    n_edge: int
    n_seeds: int
    exact_a2: str
    exact_edge: str
    a2_share: float
    edge_share: float
    strict_pass: bool
    n_trials: int


@dataclass(frozen=True, slots=True)
class NullOnlyCycle:
    es_before: BuilderScore | None
    es_after: BuilderScore | None
    synthetic_before: BuilderScore
    synthetic_after: BuilderScore
    strict_gate_pass: bool
    json_path: Path
    md_path: Path
    n_days_es: int
    holdout_asserted: bool
    es_first_ts: str
    es_last_ts: str
    n_bars_es: int


def synthetic_drift_tape(*, n_sessions: int = 40, instrument: str = "MES") -> PreparedTape:
    """All-up RTH tape: the v1 leak probe. Not a market result."""
    rows: list[ResearchBar] = []
    day = datetime(2025, 3, 3, 14, 31, tzinfo=UTC)
    session_index = 0
    while session_index < n_sessions:
        if day.weekday() < 5:
            price = 5000.0
            step = 2.0 + 0.25 * float(session_index % 5)
            for index in range(24):
                ts = day + timedelta(minutes=index)
                nxt = price + step
                ns = int(ts.timestamp() * 1_000_000_000)
                rows.append(
                    ResearchBar(
                        ts_ns=ns,
                        open=price,
                        high=nxt + 0.25,
                        low=price - 0.25,
                        close=nxt,
                        volume=8_000.0,
                    )
                )
                price = nxt
            session_index += 1
        day += timedelta(days=1)
    return prepare_tape(instrument, tuple(rows))


def load_pre_holdout_es(path: Path) -> LoadedTape:
    bars = read_csv_bars(path)
    if not bars:
        raise ValueError(f"empty ES tape {path}")
    assert_no_holdout_timestamps(bars, pin_ns=P2_HOLDOUT_START_NS)
    last = bars[-1]
    if int(last.ts_ns) >= P2_HOLDOUT_START_NS:
        raise ValueError("ES tape last bar is on or after the holdout pin")
    return LoadedTape(instrument="ES", bar_size="1m", path=path, bars=bars, holdout_start_ns=None)


def prepare_pre_holdout(tape: LoadedTape) -> PreparedTape:
    assert_no_holdout_timestamps(tape.bars, pin_ns=P2_HOLDOUT_START_NS)
    return prepare_tape(tape.instrument, tape.bars)


def score_builder(
    *,
    prepared: PreparedTape,
    registry: TrialRegistry,
    audit_path: Path,
    builder: str,
    is_size: int,
    oos_size: int,
    n_days: int,
) -> BuilderScore:
    report = run_controls(
        prepared={prepared.instrument: prepared},
        registry=registry,
        audit_path=audit_path,
        is_size=is_size,
        oos_size=oos_size,
        market_returns=market_series(prepared),
        n_days=n_days,
        block_seeds=(),
        fail_closed=False,
        null_builder=builder,
    )
    audit = report.null_audit
    if audit is None:
        raise RuntimeError("null-only run produced no audit")
    edge = classify_null_a2(audit.n_edge, audit.n_seeds)
    return BuilderScore(
        builder=builder,
        n_a2=audit.n_a2,
        n_edge=audit.n_edge,
        n_seeds=audit.n_seeds,
        exact_a2=audit.exact_a2 or f"{audit.n_a2}/{audit.n_seeds}",
        exact_edge=audit.exact_edge or f"{audit.n_edge}/{audit.n_seeds}",
        a2_share=float(audit.n_a2) / float(audit.n_seeds),
        edge_share=float(audit.n_edge) / float(audit.n_seeds),
        strict_pass=edge.reliable,
        n_trials=audit.n_trials_this_root,
    )


def run_null_only(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    es_csv: Path | None = None,
    synthetic: PreparedTape | None = None,
    repo_root: Path | None = None,
) -> NullOnlyCycle:
    """Score v1 vs v2 on synthetic and optional ES. No templates, no NQ, no holdout."""
    root = repo_root if repo_root is not None else _REPO
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    if synthetic is None:
        raise ValueError("synthetic tape is required")
    registry = TrialRegistry(work_dir / "null_only.jsonl")
    syn_days = len(unique_sessions(synthetic.session_dates))
    syn_is, syn_oos, _formed = walk_forward_sizes(syn_days)
    synthetic_before = score_builder(
        prepared=synthetic,
        registry=registry,
        audit_path=registry.audit_path,
        builder=NULL_BUILDER_V1,
        is_size=syn_is,
        oos_size=syn_oos,
        n_days=syn_days,
    )
    synthetic_after = score_builder(
        prepared=synthetic,
        registry=registry,
        audit_path=registry.audit_path,
        builder=NULL_BUILDER_V2,
        is_size=syn_is,
        oos_size=syn_oos,
        n_days=syn_days,
    )
    es_before: BuilderScore | None = None
    es_after: BuilderScore | None = None
    n_days_es = 0
    n_bars_es = 0
    es_first_ts = ""
    es_last_ts = ""
    holdout_asserted = False
    if es_csv is not None:
        tape = load_pre_holdout_es(es_csv)
        holdout_asserted = True
        n_bars_es = len(tape.bars)
        es_first_ts = _iso_utc(tape.bars[0].ts_ns)
        es_last_ts = _iso_utc(tape.bars[-1].ts_ns)
        prepared = prepare_pre_holdout(tape)
        n_days_es = len(unique_sessions(prepared.session_dates))
        try:
            es_is, es_oos, _es_formed = walk_forward_sizes(n_days_es)
        except WalkForwardError as exc:
            raise ValueError(f"ES tape cannot form walk-forward windows: {exc}") from exc
        es_before = score_builder(
            prepared=prepared,
            registry=registry,
            audit_path=registry.audit_path,
            builder=NULL_BUILDER_V1,
            is_size=es_is,
            oos_size=es_oos,
            n_days=n_days_es,
        )
        es_after = score_builder(
            prepared=prepared,
            registry=registry,
            audit_path=registry.audit_path,
            builder=NULL_BUILDER_V2,
            is_size=es_is,
            oos_size=es_oos,
            n_days=n_days_es,
        )
    strict_pass = synthetic_after.strict_pass and es_after is not None and es_after.strict_pass
    cycle = NullOnlyCycle(
        es_before=es_before,
        es_after=es_after,
        synthetic_before=synthetic_before,
        synthetic_after=synthetic_after,
        strict_gate_pass=strict_pass,
        json_path=report_dir / NULL_ONLY_JSON,
        md_path=report_dir / MD_NAME,
        n_days_es=n_days_es,
        holdout_asserted=holdout_asserted,
        es_first_ts=es_first_ts,
        es_last_ts=es_last_ts,
        n_bars_es=n_bars_es,
    )
    _write_reports(cycle, repo_root=root)
    return cycle


def _iso_utc(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _score_payload(score: BuilderScore | None) -> dict[str, object] | None:
    if score is None:
        return None
    return {
        "builder": score.builder,
        "n_a2": score.n_a2,
        "n_edge": score.n_edge,
        "n_seeds": score.n_seeds,
        "exact_a2": score.exact_a2,
        "exact_edge": score.exact_edge,
        "a2_share": score.a2_share,
        "edge_share": score.edge_share,
        "strict_pass": score.strict_pass,
        "n_trials": score.n_trials,
    }


def _write_reports(cycle: NullOnlyCycle, *, repo_root: Path) -> None:
    answers = repo_root / "docs" / "research" / ANSWERS_NAME
    answers_sha = hashlib.sha256(answers.read_bytes()).hexdigest() if answers.is_file() else ""
    payload = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "answers": ANSWERS_NAME,
        "answers_present": answers.is_file(),
        "answers_sha256": answers_sha,
        "holdout_pin": P2_HOLDOUT_START_UTC.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "holdout_asserted": cycle.holdout_asserted,
        "holdout_opened": False,
        "nq_closed": True,
        "templates_run": False,
        "research_run": False,
        "n_seeds": len(default_null_seeds()),
        "calibrated_positive_share": NULL_CALIBRATED_POSITIVE_SHARE,
        "fail_at": 4,
        "n_days_es": cycle.n_days_es,
        "n_bars_es": cycle.n_bars_es,
        "es_first_ts": cycle.es_first_ts,
        "es_last_ts": cycle.es_last_ts,
        "es_before": _score_payload(cycle.es_before),
        "es_after": _score_payload(cycle.es_after),
        "synthetic_before": _score_payload(cycle.synthetic_before),
        "synthetic_after": _score_payload(cycle.synthetic_after),
        "strict_gate_pass": cycle.strict_gate_pass,
        "builder_after": NULL_BUILDER_V2,
        "builder_before": NULL_BUILDER_V1,
        "strengthening": STRENGTHENING,
    }
    cycle.json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# P2 null-only validation (2026-10-29 18:17)",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- answers: `{ANSWERS_NAME}`",
        f"- answers_sha256: `{answers_sha}`",
        f"- CostModel: `{COST_MODEL_VERSION}`",
        "- holdout pin `2026-01-28T23:00:00Z`: asserted absent, unopened",
        "- NQ: closed; templates: not run; strategy-run: locked until strict FPR passes",
        f"- seeds: `{len(default_null_seeds())}`",
        "- gate: A2 and +OOS ≥ 7/8; fail at ≥4/32; A2 count is diagnostic",
        f"- builder_before: `{NULL_BUILDER_V1}`",
        f"- builder_after: `{NULL_BUILDER_V2}`",
        f"- strengthening: {STRENGTHENING}",
        f"- ES bars: `{cycle.n_bars_es}` sessions `{cycle.n_days_es}` first `{cycle.es_first_ts}` last `{cycle.es_last_ts}`",
        f"- strict_gate_pass: `{cycle.strict_gate_pass}`",
        "",
        "## Exact FPR",
        "",
        "| tape | builder | exact A2 (old) | A2 share | exact 7/8 (strict) | strict share | ≤3/32 |",
        "|---|---|---|---|---|---|---|",
    ]
    rows = [
        ("synthetic", cycle.synthetic_before),
        ("synthetic", cycle.synthetic_after),
        ("ES", cycle.es_before),
        ("ES", cycle.es_after),
    ]
    for tape, score in rows:
        if score is None:
            lines.append(f"| {tape} | n/a | n/a | n/a | n/a | n/a | n/a |")
            continue
        lines.append(
            "| {tape} | {builder} | {a2} | {ash:.3f} | {edge} | {esh:.3f} | {ok} |".format(
                tape=tape,
                builder=score.builder,
                a2=score.exact_a2,
                ash=score.a2_share,
                edge=score.exact_edge,
                esh=score.edge_share,
                ok="yes" if score.strict_pass else "no",
            )
        )
    cycle.md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
