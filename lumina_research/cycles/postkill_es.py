"""Post-kill ES follow-up: two 2.4 ATR breakouts + one TOD lookback-45.

Research-team 06:38. ES only. No NQ, no promotion, no SIM, holdout sealed.
Preregister must be committed before any run. Optional plants are not run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from lumina_research.cycles.catalog import HypothesisSpec, catalog
from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.holdout import (
    P2_HOLDOUT_START_NS,
    P2_HOLDOUT_START_UTC,
    assert_no_holdout_timestamps,
)
from lumina_research.cycles.limited_es import PRE_HOLDOUT_CSV_SHA256
from lumina_research.cycles.nq_lock import assert_nq_templates_closed
from lumina_research.cycles.null_lock import assert_research_allowed
from lumina_research.cycles.null_only import load_pre_holdout_es, prepare_pre_holdout
from lumina_research.cycles.p2_cycle import clear_materialize_cache
from lumina_research.cycles.positive_control import (
    BREAKOUT_MIDPOINT_ATR,
    FADE_MIDPOINT_ATR,
    required_midpoint_controls,
)
from lumina_research.cycles.report import CycleReport, CycleRow
from lumina_research.cycles.runner import ResearchCycleResult, run_research_cycles
from lumina_research.cycles.seal import ES_NQ_SEAL_NAME, SEAL_NAME, file_sha256
from lumina_research.proof.runner import DEFAULT_REPORTS
from lumina_research.validation.audit import utc_now_iso, write_event
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN, FLOOR_PBO_HARD_REJECT

_REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
POSTKILL_CYCLES_STEM = "phase5_p2_postkill"
POSTKILL_RESULTS_NAME = "phase5_p2_postkill_results.md"
POSTKILL_SEAL_NAME = "phase5_p2_postkill_holdout_seal.json"
END_REPORT_NAME = "phase5_p2_postkill_end_report_2026-10-30.md"
END_JSON_NAME = "phase5_p2_postkill_end.json"
PREREG_NAME = "phase5_p2_postkill_preregister_2026-10-30.md"
ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-POSTKILL-20261030T0638.md"
ANSWERS_SHA256 = "311ea60a1e8b3f832884669791d9e324c578822f3793db781cb54b9e79590c3b"
LIMITED_PIT_JSON = "phase5_p2_limited_es.json"
LIMITED_TIME_STOP = 2000
PRIOR_LIMITED_N_TRIALS = 78
BREAKOUT_STRETCH_ATR = 2.4
BREAKOUT_STOP_ATR = 0.9
TOD_LOOKBACK = 45
LOCKED_IDS: tuple[str, ...] = ("p2p-rc-es", "p2p-vx-es", "p2p-tod-es")
BREAKOUT_SIBLINGS: tuple[str, ...] = ("p2l-rc-es", "p2l-vx-es")
TAPE_SEARCHED: tuple[str, ...] = (
    "/tmp/lumina-es/ES_pre_holdout.csv",
    "$LUMINA_RESEARCH_DATA_DIR/ES/1m/*.csv",
    "data/research/ES/1m/*.csv",
)
_GRID: tuple[tuple[str, str, str, str, int, float, float, float], ...] = (
    ("p2p-rc-es", "range_compression", "range_compression", "breakout", 60, 0.25, 2.4, 0.9),
    ("p2p-vx-es", "volatility_expansion", "volatility_expansion", "breakout", 60, 0.75, 2.4, 0.9),
    ("p2p-tod-es", "time_of_day_inventory", "time_of_day", "fade", 45, 0.0, 1.0, 1.2),
)


def postkill_es_specs() -> tuple[HypothesisSpec, ...]:
    by_template = {item.template_id: item for item in catalog()}
    fade_t, fade_s = FADE_MIDPOINT_ATR
    _bo_t, bo_s = BREAKOUT_MIDPOINT_ATR
    out: list[HypothesisSpec] = []
    for config_id, template_id, family, mode, lookback, threshold, target, stop in _GRID:
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
                session_filter="rth",
                time_stop_bars=LIMITED_TIME_STOP,
                session_end_flatten=True,
                has_fit_step=False,
                target_atr=target,
                stop_atr=stop,
                atr_n_sessions=14,
                disable_brackets=False,
            )
        )
    ids = tuple(item.config_id for item in out)
    if ids != LOCKED_IDS:
        raise RuntimeError("postkill ES grid must be the three pre-registered p2p-* ids")
    if any(item.instrument != "ES" for item in out):
        raise RuntimeError("postkill ES grid is ES only")
    assert_nq_templates_closed(item.instrument for item in out)
    breakout = [item for item in out if item.config_id in {"p2p-rc-es", "p2p-vx-es"}]
    tod = next(item for item in out if item.config_id == "p2p-tod-es")
    if any(item.target_atr != BREAKOUT_STRETCH_ATR or item.stop_atr != bo_s for item in breakout):
        raise RuntimeError("postkill breakouts must keep target 2.4 / stop 0.9")
    if bo_s != BREAKOUT_STOP_ATR:
        raise RuntimeError("breakout stop midpoint drifted from 0.9")
    if tod.lookback != TOD_LOOKBACK:
        raise RuntimeError("postkill TOD must keep lookback 45")
    if tod.target_atr != fade_t or tod.stop_atr != fade_s:
        raise RuntimeError("postkill TOD must keep fade 1.0/1.2")
    return tuple(out)


def _pit_json(report_dir: Path, repo_root: Path | None = None) -> Path:
    direct = report_dir / LIMITED_PIT_JSON
    if direct.is_file():
        return direct
    root = repo_root if repo_root is not None else _REPO
    return root / "experiments" / "reports" / LIMITED_PIT_JSON


def breakout_diagnostics_from_limited_pit(
    report_dir: Path = DEFAULT_REPORTS,
    *,
    repo_root: Path | None = None,
) -> tuple[dict[str, object], ...]:
    """MFE/MAE, exit mix, and per-trade costs from the killed limited-es PIT.

    Reading committed columns is not a TrialRegistry increment.
    """
    payload = json.loads(_pit_json(report_dir, repo_root).read_text(encoding="utf-8"))
    by_id = {str(row["config_id"]): row for row in payload["hypotheses"]}
    rows: list[dict[str, object]] = []
    for config_id in BREAKOUT_SIBLINGS:
        src = by_id[config_id]
        n_trades = int(src["n_trades"])
        rows.append(_diag_row(src, n_trades))
    return tuple(rows)


def tod_diagnostics_from_limited_pit(
    report_dir: Path = DEFAULT_REPORTS,
    *,
    repo_root: Path | None = None,
) -> dict[str, object]:
    payload = json.loads(_pit_json(report_dir, repo_root).read_text(encoding="utf-8"))
    by_id = {str(row["config_id"]): row for row in payload["hypotheses"]}
    src = by_id["p2l-tod-es"]
    return _diag_row(src, int(src["n_trades"]))


def seed_prior_dsr_n(audit_path: Path, *, n: int = PRIOR_LIMITED_N_TRIALS) -> None:
    """Continue DSR N from the limited-es high-water. New records still increment."""
    if n < 1:
        raise ValueError("prior DSR N must be positive")
    for index in range(1, n + 1):
        write_event(
            path=audit_path,
            agent_id="prior_limited_es",
            event="trial",
            metrics={
                "config_id": "prior_limited_es_cycle",
                "n_trials": index,
                "trial_id": index,
                "note": "seed DSR N from limited-es high-water 78",
            },
        )


def run_postkill_es_cycle(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    es_csv: Path | None = None,
    repo_root: Path | None = None,
    require_known_csv: bool = True,
) -> ResearchCycleResult:
    """Three p2p-* configs on the attached pre-holdout ES tape. No promotion."""
    root = repo_root if repo_root is not None else _REPO
    if es_csv is None:
        raise ValueError("postkill-es requires a local pre-holdout ES CSV")
    if not es_csv.is_file():
        raise ValueError(f"postkill-es ES CSV is missing: {es_csv}")
    _require_answers(root)
    assert_research_allowed(report_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_sha = file_sha256(es_csv)
    if require_known_csv and csv_sha != PRE_HOLDOUT_CSV_SHA256:
        raise ValueError("postkill-es ES CSV sha256 is not the attached pre-holdout tape")
    tape = load_pre_holdout_es(es_csv)
    assert_no_holdout_timestamps(tape.bars)
    prepared = prepare_pre_holdout(tape)
    specs = postkill_es_specs()
    seal_sha = _write_pre_holdout_seal(
        report_dir=report_dir,
        csv_sha=csv_sha,
        n_bars=len(tape.bars),
        first_ts=_iso_utc(tape.bars[0].ts_ns),
        last_ts=_iso_utc(tape.bars[-1].ts_ns),
        filename=es_csv.name,
    )
    status = DataStatus(
        usable=True,
        tapes=(tape,),
        searched=(str(es_csv),),
        missing=("NQ", "MES", "MNQ"),
        required={
            "instruments": "postkill ES only; NQ closed",
            "holdout": "pin 2026-01-28T23:00:00Z sealed; this CSV has no holdout bars",
            "configs": "exactly the three pre-registered p2p-* ids",
            "promotion": "none",
            "sim_real": "none",
        },
    )
    audit = work_dir / "audit.jsonl"
    seed_prior_dsr_n(audit)
    clear_materialize_cache()
    result = run_research_cycles(
        work_dir=work_dir,
        report_dir=report_dir,
        evolution_log_dir=None,
        repo_root=root,
        specs=specs,
        cycles_stem=POSTKILL_CYCLES_STEM,
        results_name=POSTKILL_RESULTS_NAME,
        allowed_instruments=frozenset({"ES"}),
        control_per_instrument=False,
        write_sidecars=False,
        seal_filename=POSTKILL_SEAL_NAME,
        require_known_files=False,
        control_geometry_mode="atr",
        control_block_seeds=(),
        prepared_tapes={prepared.instrument: prepared},
        status_override=status,
        seal_sha_override=seal_sha,
        required_control_geometries=required_midpoint_controls(),
    )
    write_postkill_report(
        result=result,
        report_dir=report_dir,
        repo_root=root,
        csv_sha=csv_sha,
        n_bars=len(tape.bars),
        first_ts=_iso_utc(tape.bars[0].ts_ns),
        last_ts=_iso_utc(tape.bars[-1].ts_ns),
        seal_sha=seal_sha,
        tape_missing=False,
        searched=(str(es_csv),),
    )
    return result


def write_blocked_report(*, report_dir: Path = DEFAULT_REPORTS, repo_root: Path | None = None) -> Path:
    """Fail-closed when the attached pre-holdout ES tape is not mounted."""
    root = repo_root if repo_root is not None else _REPO
    _require_answers(root)
    report_dir.mkdir(parents=True, exist_ok=True)
    write_postkill_report(
        result=None,
        report_dir=report_dir,
        repo_root=root,
        csv_sha="",
        n_bars=0,
        first_ts="",
        last_ts="",
        seal_sha="",
        tape_missing=True,
        searched=TAPE_SEARCHED,
    )
    return report_dir / END_JSON_NAME


def overall_verdict(report: CycleReport | None, *, tape_missing: bool) -> str:
    """Honest label. Survivors still do not promote. Missing tape is not a kill."""
    if tape_missing or report is None:
        return "tape_missing_no_new_trials"
    if report.stopped:
        return "stopped_control_failed"
    if report.n_tested == 0:
        return "not_tested"
    if report.n_survivors > 0:
        return "survivors_exist_no_promotion"
    return "all_kill_no_promotion"


def family_close_verdicts(rows: tuple[CycleRow, ...], *, tape_missing: bool) -> dict[str, str]:
    if tape_missing or not rows:
        return {"breakout": "pending_tape", "tod": "pending_tape"}
    by_id = {row.config_id: row for row in rows}
    rc = by_id.get("p2p-rc-es")
    vx = by_id.get("p2p-vx-es")
    tod = by_id.get("p2p-tod-es")
    breakout = "pending_tape"
    if rc is not None and vx is not None:
        rc_net = rc.net_pnl
        vx_net = vx.net_pnl
        if rc_net is not None and vx_net is not None and rc_net < 0.0 and vx_net < 0.0:
            breakout = "closed_net_negative"
        else:
            breakout = "open_needs_gate"
    tod_status = "pending_tape"
    if tod is not None:
        failed_dsr = "dsr_below_threshold" in tod.reject_reasons
        failed_oos = any(
            reason in tod.reject_reasons
            for reason in (
                "static_positive_share_below_60",
                "static_median_oos_not_positive",
                "negative_median_oos_after_costs",
            )
        )
        tod_status = "closed_failed_gates" if (failed_dsr or failed_oos or not tod.passed) else "open_needs_gate"
    return {"breakout": breakout, "tod": tod_status}


def _diag_row(src: Mapping[str, object], n_trades: int) -> dict[str, object]:
    comm = float(src["commission_usd"])
    spread = float(src["half_spread_usd"])
    slip = float(src["slippage_usd"])
    impact = float(src["impact_usd"])
    scale = float(n_trades) if n_trades else float("nan")
    stop = int(src["exit_stop"])
    target = int(src["exit_target"])
    time_stop = int(src["exit_time_stop"])
    session_end = int(src["exit_session_end"])
    return {
        "config_id": str(src["config_id"]),
        "n_trades": n_trades,
        "hitrate": float(src["hitrate"]),
        "break_even_win_rate": float(src["break_even_win_rate"]),
        "gross_pnl": float(src["gross_pnl"]),
        "net_pnl": float(src["net_pnl"]),
        "n_trials": int(src["n_trials"]),
        "dsr": float(src["dsr"]),
        "pbo": float(src["pbo"]),
        "pct_positive_oos": float(src["pct_positive_oos"]),
        "n_oos_windows": int(src["n_oos_windows"]),
        "commission_usd": comm,
        "half_spread_usd": spread,
        "slippage_usd": slip,
        "impact_usd": impact,
        "cost_total_usd": comm + spread + slip + impact,
        "commission_per_trade": comm / scale,
        "half_spread_per_trade": spread / scale,
        "slippage_per_trade": slip / scale,
        "impact_per_trade": impact / scale,
        "cost_per_trade": (comm + spread + slip + impact) / scale,
        "exit_stop": stop,
        "exit_target": target,
        "exit_time_stop": time_stop,
        "exit_session_end": session_end,
        "exit_stop_share": stop / scale,
        "exit_target_share": target / scale,
        "exit_session_end_share": session_end / scale,
        "mean_mfe_ticks": float(src["mean_mfe_ticks"]),
        "mean_mae_ticks": float(src["mean_mae_ticks"]),
        "mfe_minus_mae_ticks": float(src["mean_mfe_ticks"]) - float(src["mean_mae_ticks"]),
        "gross_points": float(src["gross_points"]),
        "net_points": float(src["net_points"]),
    }


def _require_answers(repo_root: Path) -> None:
    path = repo_root / "docs" / "research" / ANSWERS_NAME
    if not path.is_file():
        raise ValueError("postkill-es answers file is missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != ANSWERS_SHA256:
        raise ValueError("postkill-es answers sha256 is not the frozen 06:38 lock")


def _iso_utc(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_pre_holdout_seal(
    *,
    report_dir: Path,
    csv_sha: str,
    n_bars: int,
    first_ts: str,
    last_ts: str,
    filename: str,
) -> str:
    if POSTKILL_SEAL_NAME in {SEAL_NAME, ES_NQ_SEAL_NAME}:
        raise RuntimeError("postkill-es must not overwrite live holdout seals")
    body: dict[str, object] = {
        "holdout_start_utc": P2_HOLDOUT_START_UTC.isoformat(),
        "holdout_start_ns": P2_HOLDOUT_START_NS,
        "holdout_opened": False,
        "tape_kind": "pre_holdout_es",
        "holdout_months": 9,
        "note": (
            "Postkill follow-up on the pre-holdout ES tape. Holdout bars stay "
            "sealed. This sidecar is not the live MES/MNQ or ES/NQ seal."
        ),
        "sealed_at": utc_now_iso(),
        "instruments": {
            "ES": {
                "bar_size": "1m",
                "file_sha256": csv_sha,
                "first_utc": first_ts,
                "last_utc": last_ts,
                "n_bars": n_bars,
                "n_train": n_bars,
                "n_holdout": 0,
                "train_last_utc": last_ts,
                "holdout_first_utc": None,
                "holdout_last_utc": None,
                "path": filename,
                "zip_sha256": "",
            }
        },
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    body["seal_sha256"] = digest
    path = report_dir / POSTKILL_SEAL_NAME
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest


def _oos_positive(row: CycleRow) -> tuple[int | None, str]:
    windows = row.n_oos_windows
    pct = row.pct_positive_oos
    if windows is None or pct is None:
        return None, "n/a"
    n_pos = int(round(float(pct) * int(windows)))
    return n_pos, f"{n_pos}/{windows}"


def _row_payload(row: CycleRow) -> dict[str, object]:
    n_pos, exact_oos = _oos_positive(row)
    return {
        "config_id": row.config_id,
        "template_id": row.template_id,
        "family": row.family,
        "instrument": row.instrument,
        "tested": row.tested,
        "passed_gate": row.passed,
        "reject_reasons": list(row.reject_reasons),
        "death_reason": row.death_reason,
        "n_trades": row.n_trades,
        "hitrate": row.hitrate,
        "break_even_win_rate": row.break_even_win_rate,
        "hitrate_minus_be": row.hitrate_minus_be,
        "gross_pnl": row.gross_pnl,
        "net_pnl": row.net_pnl,
        "n_oos_windows": row.n_oos_windows,
        "n_positive_oos": n_pos,
        "exact_oos": exact_oos,
        "pct_positive_oos": row.pct_positive_oos,
        "dsr": row.dsr,
        "pbo": row.pbo,
        "n_trials": row.n_trials,
        "target_atr": row.target_atr,
        "stop_atr": row.stop_atr,
    }


def write_postkill_report(
    *,
    result: ResearchCycleResult | None,
    report_dir: Path,
    repo_root: Path,
    csv_sha: str,
    n_bars: int,
    first_ts: str,
    last_ts: str,
    seal_sha: str,
    tape_missing: bool,
    searched: tuple[str, ...],
) -> None:
    report = None if result is None else result.report
    verdict = overall_verdict(report, tape_missing=tape_missing)
    families = family_close_verdicts(tuple() if report is None else report.rows, tape_missing=tape_missing)
    answers = repo_root / "docs" / "research" / ANSWERS_NAME
    prereg = repo_root / "experiments" / "reports" / PREREG_NAME
    breakout_diag = breakout_diagnostics_from_limited_pit(report_dir, repo_root=repo_root)
    tod_diag = tod_diagnostics_from_limited_pit(report_dir, repo_root=repo_root)
    rows = () if report is None else report.rows
    payload: dict[str, object] = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "dsr_floor": FLOOR_DSR_PROBABILITY_MIN,
        "pbo_hard_reject": FLOOR_PBO_HARD_REJECT,
        "answers": ANSWERS_NAME,
        "answers_sha256": ANSWERS_SHA256,
        "answers_present": answers.is_file(),
        "prereg": PREREG_NAME,
        "prereg_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else "",
        "prereg_commit": "72078670",
        "holdout_pin": "2026-01-28T23:00:00Z",
        "holdout_opened": False,
        "nq_closed": True,
        "promotion": False,
        "sim_real": False,
        "plants_run": False,
        "extra_variants": False,
        "n_configs": len(LOCKED_IDS),
        "config_ids": list(LOCKED_IDS),
        "breakout_stretch_atr": BREAKOUT_STRETCH_ATR,
        "tod_lookback": TOD_LOOKBACK,
        "prior_limited_n_trials": PRIOR_LIMITED_N_TRIALS,
        "csv_sha256": csv_sha,
        "n_bars_es": n_bars,
        "es_first_ts": first_ts,
        "es_last_ts": last_ts,
        "holdout_seal_sha256": seal_sha,
        "tape_missing": tape_missing,
        "searched": list(searched),
        "n_tested": 0 if report is None else report.n_tested,
        "n_killed": 0 if report is None else report.n_killed,
        "n_survivors": 0 if report is None else report.n_survivors,
        "stopped": False if report is None else report.stopped,
        "stop_reason": "" if report is None else report.stop_reason,
        "control_note": "" if report is None else report.control_note,
        "overall_verdict": verdict,
        "breakout_family": families["breakout"],
        "tod_family": families["tod"],
        "breakout_diagnostics": list(breakout_diag),
        "tod_diagnostics": tod_diag,
        "configs": [_row_payload(row) for row in rows],
    }
    (report_dir / END_JSON_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    lines = _markdown_report(
        payload=payload,
        breakout_diag=breakout_diag,
        tod_diag=tod_diag,
        rows=rows,
        verdict=verdict,
        families=families,
        tape_missing=tape_missing,
        searched=searched,
        csv_sha=csv_sha,
        n_bars=n_bars,
        first_ts=first_ts,
        last_ts=last_ts,
        report=report,
    )
    (report_dir / END_REPORT_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _markdown_report(
    *,
    payload: Mapping[str, object],
    breakout_diag: tuple[dict[str, object], ...],
    tod_diag: Mapping[str, object],
    rows: tuple[CycleRow, ...],
    verdict: str,
    families: Mapping[str, str],
    tape_missing: bool,
    searched: tuple[str, ...],
    csv_sha: str,
    n_bars: int,
    first_ts: str,
    last_ts: str,
    report: CycleReport | None,
) -> list[str]:
    prereg_sha = str(payload["prereg_sha256"])
    lines = [
        "# P2 post-kill follow-up — end report (2026-10-30 06:38)",
        "",
        "Binding input (Steve forwarded; **not** Steve's opinion):",
        f"`docs/research/{ANSWERS_NAME}`",
        f"content sha256 `{ANSWERS_SHA256}` (prefix `311ea60a`).",
        "",
        "Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin",
        "`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**",
        "Optional plants **not run**. No new large cycle.",
        "",
        f"Pre-register: `{PREREG_NAME}` (commit `72078670`, content sha256 `{prereg_sha}`).",
        "Three fresh `p2p-*` ids. Breakout target 2.4 ATR / stop 0.9. TOD lookback 45.",
        "DSR N continues from limited-es high-water 78.",
        "",
        f"- CostModel `{COST_MODEL_VERSION}`, DSR floor `{FLOOR_DSR_PROBABILITY_MIN}`, "
        f"PBO hard `{FLOOR_PBO_HARD_REJECT}`",
        "- holdout_opened: `false`; nq_closed: `true`; promotion: `false`; plants: `false`",
        f"- **overall_verdict: `{verdict}`**",
        f"- breakout family: `{families['breakout']}`; TOD: `{families['tod']}`",
        "",
        "## Breakout diagnostics (limited-es PIT, not extra trials)",
        "",
        "| config | n | stop | target | time_stop | session_end | stop % | tgt % | sess % | "
        "mean MFE | mean MAE | MFE−MAE |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in breakout_diag:
        n_trades = int(row["n_trades"])
        lines.append(
            "| `{id}` | {n} | {st} | {tg} | {ts} | {se} | {sp:.1%} | {tp:.1%} | {ep:.1%} | "
            "{mfe:.3f} | {mae:.3f} | {delta:.3f} |".format(
                id=row["config_id"],
                n=n_trades,
                st=row["exit_stop"],
                tg=row["exit_target"],
                ts=row["exit_time_stop"],
                se=row["exit_session_end"],
                sp=float(row["exit_stop_share"]),
                tp=float(row["exit_target_share"]),
                ep=float(row["exit_session_end_share"]),
                mfe=float(row["mean_mfe_ticks"]),
                mae=float(row["mean_mae_ticks"]),
                delta=float(row["mfe_minus_mae_ticks"]),
            )
        )
    lines.extend(
        [
            "",
            "| config | comm $ | half-spread $ | slippage $ | impact $ | total $ | "
            "comm/t | spread/t | slip/t | impact/t | total/t | gross | net |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in breakout_diag:
        lines.append(
            "| `{id}` | {c:.2f} | {h:.2f} | {s:.2f} | {i:.2f} | {t:.2f} | "
            "{ct:.2f} | {ht:.2f} | {st:.2f} | {it:.2f} | {tt:.2f} | {g:.6g} | {n:.6g} |".format(
                id=row["config_id"],
                c=float(row["commission_usd"]),
                h=float(row["half_spread_usd"]),
                s=float(row["slippage_usd"]),
                i=float(row["impact_usd"]),
                t=float(row["cost_total_usd"]),
                ct=float(row["commission_per_trade"]),
                ht=float(row["half_spread_per_trade"]),
                st=float(row["slippage_per_trade"]),
                it=float(row["impact_per_trade"]),
                tt=float(row["cost_per_trade"]),
                g=float(row["gross_pnl"]),
                n=float(row["net_pnl"]),
            )
        )
    lines.extend(
        [
            "",
            "Session-end is 80–86% of exits. The 1.8 ATR target fills on ~2% of trades.",
            "Mean MFE ≈ mean MAE. Slippage dominates the four-leg bill (~$28–33/trade).",
            "Both siblings already beat gross BE 0.333 and are still net negative.",
            "",
            "## TOD pick (same geometry, longer horizon)",
            "",
            (
                "`p2l-tod-es` sibling: n={n}, hitrate={h:.3f} vs BE 0.545, gross {g:.6g}, "
                "net {net:.6g}, +OOS 3/8, DSR {d:.3f}. Session-end {se}/{n} ({sp:.1%}). "
                "Never promote on gross. Locked follow-up is `p2p-tod-es` lookback 45 "
                "(catalog hold 15–90m; RTH already locked)."
            ).format(
                n=int(tod_diag["n_trades"]),
                h=float(tod_diag["hitrate"]),
                g=float(tod_diag["gross_pnl"]),
                net=float(tod_diag["net_pnl"]),
                d=float(tod_diag["dsr"]),
                se=int(tod_diag["exit_session_end"]),
                sp=float(tod_diag["exit_session_end_share"]),
            ),
            "",
            "## New trials vs gates",
            "",
        ]
    )
    if tape_missing:
        lines.extend(
            [
                "No new `p2p-*` trials were executed. The attached pre-holdout ES tape is",
                "not on this VM. Searched:",
                "",
            ]
        )
        for path in searched:
            lines.append(f"- `{path}`")
        lines.extend(
            [
                "",
                "Required: local CSV sha256 `6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6`,",
                "818851 bars, `2023-10-01T22:01:00Z`–`2026-01-28T22:00:00Z` (previous path",
                "`/tmp/lumina-es/ES_pre_holdout.csv`). `$LUMINA_RESEARCH_DATA_DIR` unset.",
                "Google Drive had no `ES_pre_holdout` / `ES_continuous_unadj` CSV.",
                "Families stay `pending_tape` (not closed without a run). DSR N stays 78.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "| config | trades | hitrate | BE | gross | net | +OOS | DSR | PBO | n_trials | passed_gate | reject_reasons |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for row in rows:
            _n_pos, exact_oos = _oos_positive(row)
            hit = "n/a" if row.hitrate is None else f"{row.hitrate:.3f}"
            be = "n/a" if row.break_even_win_rate is None else f"{row.break_even_win_rate:.3f}"
            gross = "n/a" if row.gross_pnl is None else f"{row.gross_pnl:.6g}"
            net = "n/a" if row.net_pnl is None else f"{row.net_pnl:.6g}"
            dsr = "n/a" if row.dsr is None else f"{row.dsr:.3f}"
            pbo = "n/a" if row.pbo is None else f"{row.pbo:.3f}"
            reasons = ",".join(row.reject_reasons) if row.reject_reasons else "(none)"
            trades = "n/a" if row.n_trades is None else str(row.n_trades)
            trials = "n/a" if row.n_trials is None else str(row.n_trials)
            lines.append(
                f"| `{row.config_id}` | {trades} | {hit} | {be} | {gross} | "
                f"{net} | {exact_oos} | {dsr} | {pbo} | {trials} | "
                f"{str(row.passed).lower()} | {reasons} |"
            )
        if report is not None:
            lines.extend(
                [
                    "",
                    f"tested `{report.n_tested}` killed `{report.n_killed}` survivors `{report.n_survivors}`",
                    f"tape sha256 `{csv_sha[:8]}…`, `{n_bars}` bars, `{first_ts}`–`{last_ts}`",
                    f"control: {report.control_note or '(none)'}",
                    "",
                ]
            )
    lines.extend(
        [
            "## Hygiene",
            "",
            "- No live / SIM orders",
            "- Risk Core not modified",
            "- NQ templates remain closed",
            "- Holdout timestamps `>= 2026-01-28T23:00:00Z` stay unopened",
            "- Max new strategy configs = 3 pre-registered `p2p-*`",
            "- Optional plants not run",
            "- No new large hypothesis cycle",
            "",
        ]
    )
    return lines
