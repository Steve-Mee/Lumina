"""One-cycle Validation Gate run for the 10:00 GO: RV-01, RV-02, LH-01, LH-03.

Dropped LH-02/LH-04 stay in n_hypotheses=6 and are not trialled. RV-02's 59-trade
low-power risk is accepted. LH-03 5-minute ATR(14) is a parameter clarification.
Holdout stays sealed. No SIM/promotion. Risk Core untouched.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from lumina_research.cycles.catalog import HypothesisSpec, catalog
from lumina_research.cycles.data import DataStatus, LoadedTape
from lumina_research.cycles.final_cycle import (
    DATA_ANSWERS_SHA256,
    FINALE_PREREG_SHA256,
    KILL_DSR_MIN,
    KILL_OOS_POSITIVE_MIN,
    KILL_OOS_WINDOWS,
    LH03_ANSWERS_NAME,
    LH03_ANSWERS_SHA256,
    LH03_ATR_NOTE,
    RV02_LOW_POWER_NOTE,
    RV02_POWER_N_TRADES,
    check_data_availability,
    kill_rule,
    lh03_atr_lock,
    load_macro_events,
    load_pre_holdout_bars,
    load_vix,
    runnable_config_ids,
    rv02_low_power,
)
from lumina_research.cycles.final_cycle_sim import (
    FINAL_CYCLE_RUN_IDS,
    LH03_STOP_SPIKE_MULT,
    LH03_TARGET_SPIKE_MULT,
    LH03_TIME_STOP_BARS,
    FinalCycleContext,
    bind_context,
    clear_context,
)
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, P2_HOLDOUT_START_UTC, assert_no_holdout_timestamps
from lumina_research.cycles.null_lock import assert_research_allowed
from lumina_research.cycles.p2_cycle import clear_materialize_cache
from lumina_research.cycles.positive_control import required_midpoint_controls
from lumina_research.cycles.prepare import prepare_tape
from lumina_research.cycles.report import CycleReport, CycleRow, death_reason
from lumina_research.cycles.runner import ResearchCycleResult, run_research_cycles
from lumina_research.cycles.seal import ES_NQ_SEAL_NAME, SEAL_NAME, file_sha256
from lumina_research.cycles.search_space import NEW_BOOK_MAX_CYCLES
from lumina_research.cycles.trial_ledger import (
    DEFAULT_LEDGER_PATH,
    LINE_STATE_CYCLE_COMPLETE,
    LINE_STATE_STOPPED,
    LedgerBlocksRun,
    assert_ledger_allows_run,
    line_state_after_cycle,
    load_trial_ledger,
)
from lumina_research.proof.runner import DEFAULT_REPORTS
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN, FLOOR_PBO_HARD_REJECT

_REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
FINAL_CYCLES_STEM = "phase5_p2_final_cycle"
FINAL_RESULTS_NAME = "phase5_p2_final_cycle_results.md"
FINAL_SEAL_NAME = "phase5_p2_final_cycle_holdout_seal.json"
END_REPORT_NAME = "phase5_p2_final_cycle_end_report_2026-10-30.md"
END_JSON_NAME = "phase5_p2_final_cycle_end.json"
LOCKED_RUN_IDS: tuple[str, ...] = runnable_config_ids()
_GRID: tuple[tuple[str, str, str, str, int, float, float | None, float | None, str, int, bool], ...] = (
    ("p2s-rv-01", "mean_reversion", "es_nq_ratio_mr", "fade", 20, 2.5, None, None, "rth", 360, True),
    ("p2s-rv-02", "overnight_gap", "es_nq_rel_gap", "fade", 1, 0.4, None, None, "rth", 90, False),
    ("p2s-lh-01", "range_compression", "nr7_breakout", "breakout", 7, 0.0, 1.5, 1.0, "rth", 2000, False),
    (
        "p2s-lh-03",
        "close_reversal",
        "macro_event_fade",
        "fade",
        14,
        1.2,
        LH03_TARGET_SPIKE_MULT,
        LH03_STOP_SPIKE_MULT,
        "globex",
        LH03_TIME_STOP_BARS,
        False,
    ),
)


def final_cycle_specs() -> tuple[HypothesisSpec, ...]:
    by_template = {item.template_id: item for item in catalog()}
    out: list[HypothesisSpec] = []
    for config_id, template_id, family, mode, lookback, threshold, target, stop, session, time_stop, disable in _GRID:
        source = by_template[template_id]
        out.append(
            HypothesisSpec(
                config_id=config_id,
                template_id=template_id,
                family=family,
                instrument="ES",
                lookback=lookback,
                threshold=threshold,
                mode=mode,
                target_ticks=1,
                stop_ticks=1,
                rationale=source.rationale,
                session_filter=session,
                time_stop_bars=time_stop,
                session_end_flatten=True,
                has_fit_step=False,
                target_atr=target,
                stop_atr=stop,
                atr_n_sessions=14,
                disable_brackets=disable,
            )
        )
    ids = tuple(item.config_id for item in out)
    if ids != LOCKED_RUN_IDS:
        raise RuntimeError("final-cycle grid must be RV-01, RV-02, LH-01, LH-03")
    if any(item.instrument != "ES" for item in out):
        raise RuntimeError("final-cycle primary instrument is ES")
    if set(ids) != set(FINAL_CYCLE_RUN_IDS):
        raise RuntimeError("final-cycle run ids drifted from the sim lock")
    return tuple(out)


def apply_team_kill(report: CycleReport) -> CycleReport:
    """Stricter than STATIC_POSITIVE_SHARE_MIN 0.60: need DSR>=0.95, >=7/8 OOS+, net>0."""
    rows: list[CycleRow] = []
    for row in report.rows:
        extra = _team_kill_reasons(row)
        if row.passed and extra:
            reasons = row.reject_reasons + extra
            rows.append(
                replace(
                    row,
                    passed=False,
                    reject_reasons=reasons,
                    death_reason=death_reason(tested=row.tested, passed=False, reasons=reasons, stopped=False),
                )
            )
            continue
        rows.append(row)
    n_tested = sum(1 for item in rows if item.tested)
    n_killed = sum(1 for item in rows if item.tested and not item.passed)
    n_survived = sum(1 for item in rows if item.tested and item.passed)
    kill_rate = None if n_tested == 0 else n_killed / float(n_tested)
    return replace(
        report,
        rows=tuple(rows),
        n_tested=n_tested,
        n_killed=n_killed,
        n_survivors=n_survived,
        kill_rate=kill_rate,
    )


def run_final_cycle(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    repo_root: Path | None = None,
    require_known_csv: bool = True,
) -> ResearchCycleResult:
    """Four locked ids on pinned pre-holdout tapes. Fresh DSR N. No promotion."""
    root = repo_root if repo_root is not None else _REPO
    _require_lh03_answers(root)
    assert_research_allowed(report_dir)
    assert_ledger_allows_run(cycle="final-cycle")
    avail = check_data_availability()
    if not (avail.es_pre_holdout and avail.nq_pre_holdout and avail.vix and avail.macro_calendar):
        raise ValueError("final-cycle needs pinned ES, NQ, VIX, and macro files")
    if avail.es_path is None or avail.nq_path is None or avail.vix_path is None or avail.macro_path is None:
        raise ValueError("final-cycle data paths are missing after the pin check")
    cycle_work = work_dir / "p2-next-search-space"
    cycle_work.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    es_path = Path(avail.es_path)
    nq_path = Path(avail.nq_path)
    es_bars = load_pre_holdout_bars(es_path)
    nq_bars = load_pre_holdout_bars(nq_path)
    assert_no_holdout_timestamps(es_bars, pin_ns=P2_HOLDOUT_START_NS)
    assert_no_holdout_timestamps(nq_bars, pin_ns=P2_HOLDOUT_START_NS)
    prepared_es = prepare_tape("ES", es_bars)
    prepared_nq = prepare_tape("NQ", nq_bars)
    vix = load_vix(Path(avail.vix_path))
    events = load_macro_events(Path(avail.macro_path))
    nq_index = {item.ts_ns: item for item in prepared_nq.bars}
    bind_context(
        FinalCycleContext(
            es=prepared_es,
            nq=prepared_nq,
            vix=vix,
            events=events,
            nq_bars=nq_index,
        )
    )
    es_tape = LoadedTape(instrument="ES", bar_size="1m", path=es_path, bars=es_bars)
    nq_tape = LoadedTape(instrument="NQ", bar_size="1m", path=nq_path, bars=nq_bars)
    seal_sha = _write_pre_holdout_seal(
        report_dir=report_dir,
        es_sha=file_sha256(es_path) if require_known_csv else file_sha256(es_path),
        nq_sha=file_sha256(nq_path),
        n_es=len(es_bars),
        n_nq=len(nq_bars),
        first_ts=_iso_utc(es_bars[0].ts_ns),
        last_ts=_iso_utc(es_bars[-1].ts_ns),
        es_name=es_path.name,
        nq_name=nq_path.name,
    )
    status = DataStatus(
        usable=True,
        tapes=(es_tape, nq_tape),
        searched=(str(es_path), str(nq_path), str(avail.vix_path), str(avail.macro_path)),
        missing=("MES", "MNQ"),
        required={
            "instruments": "ES primary; NQ pair leg; no MES/MNQ",
            "holdout": "pin 2026-01-28T23:00:00Z sealed; pre-holdout CSVs only",
            "configs": "exactly RV-01, RV-02, LH-01, LH-03; LH-02/LH-04 dropped inside n=6",
            "promotion": "none",
            "sim_real": "none",
        },
    )
    specs = final_cycle_specs()
    clear_materialize_cache()
    try:
        result = run_research_cycles(
            work_dir=cycle_work,
            report_dir=report_dir,
            evolution_log_dir=None,
            repo_root=root,
            specs=specs,
            cycles_stem=FINAL_CYCLES_STEM,
            results_name=FINAL_RESULTS_NAME,
            allowed_instruments=frozenset({"ES"}),
            control_per_instrument=False,
            write_sidecars=False,
            seal_filename=FINAL_SEAL_NAME,
            require_known_files=False,
            control_geometry_mode="atr",
            control_block_seeds=(),
            prepared_tapes={prepared_es.instrument: prepared_es},
            status_override=status,
            seal_sha_override=seal_sha,
            required_control_geometries=required_midpoint_controls(),
        )
    finally:
        clear_context()
    killed = apply_team_kill(result.report)
    flag = result.kill_rate_flag
    if killed.n_tested > 0 and killed.n_survivors == 0:
        flag = "all_kill"
    result = ResearchCycleResult(
        report=killed,
        json_path=result.json_path,
        md_path=result.md_path,
        data=result.data,
        kill_rate=killed.kill_rate,
        kill_rate_flag=flag,
    )
    n_trials = _count_trial_events(cycle_work / "audit.jsonl")
    _write_end_report(
        result=result,
        report_dir=report_dir,
        repo_root=root,
        n_es=len(es_bars),
        n_nq=len(nq_bars),
        first_ts=_iso_utc(es_bars[0].ts_ns),
        last_ts=_iso_utc(es_bars[-1].ts_ns),
        seal_sha=seal_sha,
        n_trials=n_trials,
    )
    record_final_cycle_ledger(
        result=result,
        n_trials=n_trials,
        ledger_path=DEFAULT_LEDGER_PATH,
    )
    return result


def record_final_cycle_ledger(
    *,
    result: ResearchCycleResult,
    n_trials: int,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> None:
    before = load_trial_ledger(ledger_path)
    if before.n_cycles_completed != 0:
        raise LedgerBlocksRun("final-cycle ledger record requires n_cycles_completed=0 before the run")
    state = line_state_after_cycle(n_survivors=result.report.n_survivors, n_cycles_completed_before=0)
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    active = payload["active_book"]
    if not isinstance(active, dict):
        raise LedgerBlocksRun("trial ledger active_book is not an object")
    active["open"] = False
    active["status"] = state
    active["n_cycles_completed"] = NEW_BOOK_MAX_CYCLES
    active["research_line_stopped"] = state == LINE_STATE_STOPPED
    active["n_by_market"] = {"ES": int(n_trials), "MES": 0, "MNQ": 0, "NQ": 0}
    active["n_total"] = int(n_trials)
    active["dsr_pbo_n"] = int(n_trials)
    active["rv02_low_power"] = dict(rv02_low_power())
    active["lh03_atr"] = dict(lh03_atr_lock())
    active["cycle"] = {
        "id": "final-cycle",
        "report": END_JSON_NAME,
        "n_survivors": result.report.n_survivors,
        "n_tested": result.report.n_tested,
        "n_trials": int(n_trials),
        "line_state": state,
    }
    active["note"] = (
        "10:00 GO cycle complete. n_hypotheses=6 with LH-02/LH-04 dropped. "
        f"{RV02_LOW_POWER_NOTE} {LH03_ATR_NOTE} "
        f"line_state={state}."
    )
    ledger_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    load_trial_ledger(ledger_path)


def _team_kill_reasons(row: CycleRow) -> tuple[str, ...]:
    reasons: list[str] = []
    if row.dsr is None or float(row.dsr) < KILL_DSR_MIN:
        reasons.append("team_kill_dsr")
    n_pos = _n_positive_oos(row)
    windows = row.n_oos_windows
    if n_pos is None or windows is None or n_pos < KILL_OOS_POSITIVE_MIN or int(windows) < KILL_OOS_WINDOWS:
        reasons.append("team_kill_oos")
    if row.net_pnl is None or float(row.net_pnl) <= 0.0:
        reasons.append("team_kill_net")
    return tuple(reasons)


def _n_positive_oos(row: CycleRow) -> int | None:
    windows = row.n_oos_windows
    pct = row.pct_positive_oos
    if windows is None or pct is None:
        return None
    return int(round(float(pct) * int(windows)))


def _count_trial_events(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            continue
        if row.get("event") == "trial":
            count += 1
    return count


def _require_lh03_answers(repo_root: Path) -> None:
    path = repo_root / "docs" / "research" / LH03_ANSWERS_NAME
    if not path.is_file():
        raise ValueError("LH-03 10:00 answers file is missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != LH03_ANSWERS_SHA256:
        raise ValueError("LH-03 10:00 answers sha256 is not the frozen 0c549ee1 lock")


def _iso_utc(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_pre_holdout_seal(
    *,
    report_dir: Path,
    es_sha: str,
    nq_sha: str,
    n_es: int,
    n_nq: int,
    first_ts: str,
    last_ts: str,
    es_name: str,
    nq_name: str,
) -> str:
    if FINAL_SEAL_NAME in {SEAL_NAME, ES_NQ_SEAL_NAME}:
        raise RuntimeError("final-cycle must not overwrite live holdout seals")
    body: dict[str, object] = {
        "holdout_start_utc": P2_HOLDOUT_START_UTC.isoformat(),
        "holdout_start_ns": P2_HOLDOUT_START_NS,
        "holdout_opened": False,
        "tape_kind": "pre_holdout_es_nq",
        "holdout_months": 9,
        "note": (
            "Pre-holdout ES+NQ tapes: last bar is before the pin. Holdout bars "
            "are absent and stay sealed. This sidecar is not the live MES/MNQ seal."
        ),
        "sealed_at": utc_now_iso(),
        "instruments": {
            "ES": {
                "bar_size": "1m",
                "file_sha256": es_sha,
                "first_utc": first_ts,
                "last_utc": last_ts,
                "n_bars": n_es,
                "n_train": n_es,
                "n_holdout": 0,
                "path": es_name,
            },
            "NQ": {
                "bar_size": "1m",
                "file_sha256": nq_sha,
                "n_bars": n_nq,
                "n_train": n_nq,
                "n_holdout": 0,
                "path": nq_name,
            },
        },
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    body["seal_sha256"] = digest
    (report_dir / FINAL_SEAL_NAME).write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest


def _oos_positive(row: CycleRow) -> tuple[int | None, str]:
    n_pos = _n_positive_oos(row)
    windows = row.n_oos_windows
    if n_pos is None or windows is None:
        return None, "n/a"
    return n_pos, f"{n_pos}/{windows}"


def _per_trade(total: float | None, n_trades: int | None) -> float | None:
    if total is None or n_trades is None or n_trades <= 0:
        return None
    return float(total) / float(n_trades)


def _row_payload(row: CycleRow) -> dict[str, object]:
    n_pos, exact_oos = _oos_positive(row)
    charter_fail = tuple(item for item in row.reject_reasons if not item.startswith("team_kill_"))
    return {
        "config_id": row.config_id,
        "template_id": row.template_id,
        "family": row.family,
        "instrument": row.instrument,
        "tested": row.tested,
        "passed_gate": bool(row.tested and not charter_fail),
        "passed_team_kill": row.passed,
        "reject_reasons": list(row.reject_reasons),
        "death_reason": row.death_reason,
        "n_trades": row.n_trades,
        "gross_pnl": row.gross_pnl,
        "net_pnl": row.net_pnl,
        "gross_per_trade": _per_trade(row.gross_pnl, row.n_trades),
        "net_per_trade": _per_trade(row.net_pnl, row.n_trades),
        "n_oos_windows": row.n_oos_windows,
        "n_positive_oos": n_pos,
        "exact_oos": exact_oos,
        "pct_positive_oos": row.pct_positive_oos,
        "dsr": row.dsr,
        "pbo": row.pbo,
        "n_trials": row.n_trials,
        "regime_vol_high": row.regime_vol_high,
        "regime_vol_low": row.regime_vol_low,
        "regime_trend_up": row.regime_trend_up,
        "regime_trend_down": row.regime_trend_down,
        "verdict": "survivor" if row.passed else row.death_reason,
    }


def _write_end_report(
    *,
    result: ResearchCycleResult,
    report_dir: Path,
    repo_root: Path,
    n_es: int,
    n_nq: int,
    first_ts: str,
    last_ts: str,
    seal_sha: str,
    n_trials: int,
) -> None:
    report = result.report
    line_state = line_state_after_cycle(n_survivors=report.n_survivors, n_cycles_completed_before=0)
    payload: dict[str, object] = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "dsr_floor": FLOOR_DSR_PROBABILITY_MIN,
        "pbo_hard_reject": FLOOR_PBO_HARD_REJECT,
        "kill": dict(kill_rule()),
        "finale_prereg_sha256": FINALE_PREREG_SHA256,
        "data_answers_sha256": DATA_ANSWERS_SHA256,
        "lh03_answers": LH03_ANSWERS_NAME,
        "lh03_answers_sha256": LH03_ANSWERS_SHA256,
        "lh03_atr": dict(lh03_atr_lock()),
        "rv02_low_power": dict(rv02_low_power()),
        "holdout_pin": "2026-01-28T23:00:00Z",
        "holdout_opened": False,
        "promotion": False,
        "sim_real": False,
        "n_hypotheses_stated": 6,
        "dropped_config_ids": ["p2s-lh-02", "p2s-lh-04"],
        "run_config_ids": list(LOCKED_RUN_IDS),
        "n_es_bars": n_es,
        "n_nq_bars": n_nq,
        "es_first_ts": first_ts,
        "es_last_ts": last_ts,
        "holdout_seal_sha256": seal_sha,
        "n_tested": report.n_tested,
        "n_killed": report.n_killed,
        "n_survivors": report.n_survivors,
        "kill_rate": report.kill_rate,
        "stopped": report.stopped,
        "stop_reason": report.stop_reason,
        "control_note": report.control_note,
        "planted_detected": report.planted_detected,
        "null_detected": report.null_detected,
        "n_trials": n_trials,
        "line_state": line_state,
        "research_line_stopped": line_state == LINE_STATE_STOPPED,
        "overall_verdict": (
            LINE_STATE_STOPPED if report.n_survivors == 0 else LINE_STATE_CYCLE_COMPLETE
        ),
        "configs": [_row_payload(row) for row in report.rows],
        "dropped": [
            {
                "config_id": "p2s-lh-02",
                "status": "dropped",
                "reason": "power n_trades=5",
                "tested": False,
            },
            {
                "config_id": "p2s-lh-04",
                "status": "dropped",
                "reason": "no free 1-minute SPX cash data",
                "tested": False,
            },
        ],
    }
    (report_dir / END_JSON_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# P2 final-cycle strategy-run — end report (2026-10-30 10:00 GO)",
        "",
        "Binding input (research team, **NOT** Steve):",
        f"`docs/research/{LH03_ANSWERS_NAME}` sha256 `{LH03_ANSWERS_SHA256}` (prefix `0c549ee1`).",
        "",
        "Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin",
        "`2026-01-28T23:00:00Z` unopened. Risk Core untouched.**",
        "",
        f"- {LH03_ATR_NOTE}",
        f"- {RV02_LOW_POWER_NOTE} Power count remains **{RV02_POWER_N_TRADES}**.",
        "- Runnable ids: `p2s-rv-01`, `p2s-rv-02`, `p2s-lh-01`, `p2s-lh-03`.",
        "- Dropped inside n=6: `p2s-lh-02`, `p2s-lh-04` (not trialled).",
        f"- Kill: DSR≥{KILL_DSR_MIN} AND ≥{KILL_OOS_POSITIVE_MIN}/{KILL_OOS_WINDOWS} OOS+ AND net>0.",
        f"- CostModel `{COST_MODEL_VERSION}`. Null `linear_magnitude`. Midpoint fade 1.0/1.2 and breakout 1.8/0.9.",
        f"- n_trials (this book) `{n_trials}`. line_state `{line_state}`.",
        f"- control: planted={report.planted_detected} null={report.null_detected} note=`{report.control_note}`",
        "",
        "| config | trades | gross/trade | net/trade | +OOS | DSR | PBO | verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        n_pos, exact = _oos_positive(row)
        _ = n_pos
        gross_pt = _per_trade(row.gross_pnl, row.n_trades)
        net_pt = _per_trade(row.net_pnl, row.n_trades)
        lines.append(
            f"| `{row.config_id}` | {row.n_trades} | {_fmt(gross_pt)} | {_fmt(net_pt)} | "
            f"{exact} | {_fmt(row.dsr)} | {_fmt(row.pbo)} | {row.death_reason if not row.passed else 'survivor'} |"
        )
    lines.extend(
        [
            "",
            "Dropped (counted in n_hypotheses=6, not trialled): `p2s-lh-02` (5 trades), `p2s-lh-04` (no 1m SPX).",
            "",
            f"Survivors: **{report.n_survivors}**. "
            + (
                "`research_line_stopped=true`."
                if report.n_survivors == 0
                else "`cycle_complete`; still no SIM/promotion."
            ),
            "",
        ]
    )
    (report_dir / END_REPORT_NAME).write_text("\n".join(lines), encoding="utf-8")


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"
