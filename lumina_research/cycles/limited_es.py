"""Limited ES strategy-run: exactly the six pre-registered p2l-* configs.

Research-team GO 23:07. ES only. No NQ, no promotion, no SIM, holdout sealed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from lumina_research.cycles.catalog import HypothesisSpec, catalog
from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.holdout import (
    P2_HOLDOUT_START_NS,
    P2_HOLDOUT_START_UTC,
    assert_no_holdout_timestamps,
)
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
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.cost_model import COST_MODEL_VERSION
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN, FLOOR_PBO_HARD_REJECT

_REPO = Path(__file__).resolve().parents[2]
UTC = timezone.utc
LIMITED_CYCLES_STEM = "phase5_p2_limited_es"
LIMITED_RESULTS_NAME = "phase5_p2_limited_es_results.md"
LIMITED_SEAL_NAME = "phase5_p2_limited_es_holdout_seal.json"
END_REPORT_NAME = "phase5_p2_limited_es_end_report_2026-10-29.md"
END_JSON_NAME = "phase5_p2_limited_es_end.json"
PREREG_NAME = "phase5_p2_limited_es_preregister_2026-10-29.md"
GO_ANSWERS_NAME = "ONDERZOEKERS-ANTWOORDEN-LIMITEDGO-20261029T2307.md"
GO_ANSWERS_SHA256 = "332003298fadfff06f28fced134d0a8c1a363933705d573cb3bd0407d4d9c414"
PRE_HOLDOUT_CSV_SHA256 = "6100588d2f3e519bd815b8f952dc15f01d434cc2a2b70e6453d0c3a7477bbca6"
LIMITED_TIME_STOP = 2000
LOCKED_IDS: tuple[str, ...] = (
    "p2l-mr-es",
    "p2l-or-fade-es",
    "p2l-vwap-es",
    "p2l-tod-es",
    "p2l-rc-es",
    "p2l-vx-es",
)
_GRID: tuple[tuple[str, str, str, str, int, float, float, float], ...] = (
    ("p2l-mr-es", "mean_reversion", "mean_reversion", "fade", 60, 1.5, 1.0, 1.2),
    ("p2l-or-fade-es", "opening_range_fade", "opening_range", "fade", 30, 0.0, 1.0, 1.2),
    ("p2l-vwap-es", "vwap_distance", "vwap_distance", "fade", 60, 1.5, 1.0, 1.2),
    ("p2l-tod-es", "time_of_day_inventory", "time_of_day", "fade", 30, 0.0, 1.0, 1.2),
    ("p2l-rc-es", "range_compression", "range_compression", "breakout", 60, 0.25, 1.8, 0.9),
    ("p2l-vx-es", "volatility_expansion", "volatility_expansion", "breakout", 60, 0.75, 1.8, 0.9),
)


def limited_es_specs() -> tuple[HypothesisSpec, ...]:
    by_template = {item.template_id: item for item in catalog()}
    fade_t, fade_s = FADE_MIDPOINT_ATR
    bo_t, bo_s = BREAKOUT_MIDPOINT_ATR
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
        raise RuntimeError("limited ES grid must be the six pre-registered p2l-* ids")
    if any(item.instrument != "ES" for item in out):
        raise RuntimeError("limited ES grid is ES only")
    assert_nq_templates_closed(item.instrument for item in out)
    fade = {item.config_id for item in out if item.target_atr == fade_t and item.stop_atr == fade_s}
    breakout = {item.config_id for item in out if item.target_atr == bo_t and item.stop_atr == bo_s}
    if fade != {"p2l-mr-es", "p2l-or-fade-es", "p2l-vwap-es", "p2l-tod-es"}:
        raise RuntimeError("limited fade bucket must keep 1.0/1.2 on the four fade ids")
    if breakout != {"p2l-rc-es", "p2l-vx-es"}:
        raise RuntimeError("limited breakout bucket must keep 1.8/0.9 on rc and vx")
    if "p2l-tod-es" not in ids:
        raise RuntimeError("limited ES grid must keep p2l-tod-es")
    return tuple(out)


def run_limited_es_cycle(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    es_csv: Path | None = None,
    repo_root: Path | None = None,
    require_known_csv: bool = True,
) -> ResearchCycleResult:
    """Six p2l-* configs on the attached pre-holdout ES tape. No promotion."""
    root = repo_root if repo_root is not None else _REPO
    if es_csv is None:
        raise ValueError("limited-es requires a local pre-holdout ES CSV")
    _require_go(root)
    assert_research_allowed(report_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_sha = file_sha256(es_csv)
    if require_known_csv and csv_sha != PRE_HOLDOUT_CSV_SHA256:
        raise ValueError("limited-es ES CSV sha256 is not the attached pre-holdout tape")
    tape = load_pre_holdout_es(es_csv)
    assert_no_holdout_timestamps(tape.bars)
    prepared = prepare_pre_holdout(tape)
    specs = limited_es_specs()
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
            "instruments": "limited ES only; NQ closed",
            "holdout": "pin 2026-01-28T23:00:00Z sealed; this CSV has no holdout bars",
            "configs": "exactly the six pre-registered p2l-* ids including p2l-tod-es",
            "promotion": "none",
            "sim_real": "none",
        },
    )
    clear_materialize_cache()
    result = run_research_cycles(
        work_dir=work_dir,
        report_dir=report_dir,
        evolution_log_dir=None,
        repo_root=root,
        specs=specs,
        cycles_stem=LIMITED_CYCLES_STEM,
        results_name=LIMITED_RESULTS_NAME,
        allowed_instruments=frozenset({"ES"}),
        control_per_instrument=False,
        write_sidecars=False,
        seal_filename=LIMITED_SEAL_NAME,
        require_known_files=False,
        control_geometry_mode="atr",
        control_block_seeds=(),
        prepared_tapes={prepared.instrument: prepared},
        status_override=status,
        seal_sha_override=seal_sha,
        required_control_geometries=required_midpoint_controls(),
    )
    _write_end_report(
        result=result,
        report_dir=report_dir,
        repo_root=root,
        csv_sha=csv_sha,
        n_bars=len(tape.bars),
        first_ts=_iso_utc(tape.bars[0].ts_ns),
        last_ts=_iso_utc(tape.bars[-1].ts_ns),
        seal_sha=seal_sha,
    )
    return result


def overall_verdict(report: CycleReport) -> str:
    """Honest label. Survivors still do not promote."""
    if report.stopped:
        return "stopped_control_failed"
    if report.n_tested == 0:
        return "not_tested"
    if report.n_survivors > 0:
        return "survivors_exist_no_promotion"
    return "all_kill_no_promotion"


def _require_go(repo_root: Path) -> None:
    path = repo_root / "docs" / "research" / GO_ANSWERS_NAME
    if not path.is_file():
        raise ValueError("limited-es GO answers file is missing")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != GO_ANSWERS_SHA256:
        raise ValueError("limited-es GO answers sha256 is not the frozen 23:07 lock")


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
    if LIMITED_SEAL_NAME in {SEAL_NAME, ES_NQ_SEAL_NAME}:
        raise RuntimeError("limited-es must not overwrite live holdout seals")
    body: dict[str, object] = {
        "holdout_start_utc": P2_HOLDOUT_START_UTC.isoformat(),
        "holdout_start_ns": P2_HOLDOUT_START_NS,
        "holdout_opened": False,
        "tape_kind": "pre_holdout_es",
        "holdout_months": 9,
        "note": (
            "Pre-holdout ES tape: last bar is before the pin. Holdout bars are "
            "absent from this CSV and stay sealed. This sidecar is not the live "
            "MES/MNQ or ES/NQ seal."
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
    path = report_dir / LIMITED_SEAL_NAME
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
        "regime_vol_high": row.regime_vol_high,
        "regime_vol_low": row.regime_vol_low,
        "regime_trend_up": row.regime_trend_up,
        "regime_trend_down": row.regime_trend_down,
    }


def _write_end_report(
    *,
    result: ResearchCycleResult,
    report_dir: Path,
    repo_root: Path,
    csv_sha: str,
    n_bars: int,
    first_ts: str,
    last_ts: str,
    seal_sha: str,
) -> None:
    report = result.report
    verdict = overall_verdict(report)
    answers = repo_root / "docs" / "research" / GO_ANSWERS_NAME
    prereg = repo_root / "experiments" / "reports" / PREREG_NAME
    payload: dict[str, object] = {
        "generated_at": utc_now_iso(),
        "cost_model_version": COST_MODEL_VERSION,
        "dsr_floor": FLOOR_DSR_PROBABILITY_MIN,
        "pbo_hard_reject": FLOOR_PBO_HARD_REJECT,
        "answers": GO_ANSWERS_NAME,
        "answers_sha256": GO_ANSWERS_SHA256,
        "answers_present": answers.is_file(),
        "prereg": PREREG_NAME,
        "prereg_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else "",
        "holdout_pin": "2026-01-28T23:00:00Z",
        "holdout_opened": False,
        "nq_closed": True,
        "promotion": False,
        "sim_real": False,
        "extra_variants": False,
        "n_configs": len(LOCKED_IDS),
        "config_ids": list(LOCKED_IDS),
        "csv_sha256": csv_sha,
        "n_bars_es": n_bars,
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
        "overall_verdict": verdict,
        "configs": [_row_payload(row) for row in report.rows],
    }
    (report_dir / END_JSON_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# P2 limited ES strategy-run — end report (2026-10-29 23:07 GO)",
        "",
        "Binding input (Steve forwarded; **not** Steve's opinion):",
        f"`docs/research/{GO_ANSWERS_NAME}`",
        f"content sha256 `{GO_ANSWERS_SHA256}` (prefix `33200329`).",
        "",
        "Stacked draft PR #72. **No merge. No SIM/REAL orders. Holdout pin",
        "`2026-01-28T23:00:00Z` unopened. Risk Core untouched. ES CSV not in git.**",
        "Optional lower-hitrate / no-lookahead plants **not run**.",
        "",
        f"Pre-register: `{PREREG_NAME}`. Six configs including `p2l-tod-es`.",
        "No extra variants. Parameters were not changed after seeing results.",
        "",
        f"- CostModel `{COST_MODEL_VERSION}`, DSR floor `{FLOOR_DSR_PROBABILITY_MIN}`, "
        f"PBO hard `{FLOOR_PBO_HARD_REJECT}`",
        "- fade `1.0/1.2`, breakout `1.8/0.9`, RTH flatten, `time_stop_bars=2000`",
        "- Charter gate: WF 5–8 OOS, CPCV/static + bootstrap, DSR, PBO, costs, regimes",
        "- Null: v2 `linear_magnitude`, 32 seeds, fail at `n_edge ≥ 4/32` (7/8)",
        f"- tape csv sha256 `{csv_sha[:8]}…`, `{n_bars}` bars, `{first_ts}`–`{last_ts}`",
        "- holdout_opened: `false`; nq_closed: `true`; promotion: `false`",
        f"- tested `{report.n_tested}` killed `{report.n_killed}` survivors `{report.n_survivors}`",
        f"- planted_detected: `{report.planted_detected}` null_detected: `{report.null_detected}`",
        f"- control: {report.control_note or '(none)'}",
        f"- **overall_verdict: `{verdict}`**",
        "",
        "## Per-config gate",
        "",
        "| config | trades | hitrate | BE | hit-BE | gross | net | +OOS | DSR | PBO | passed_gate | reject_reasons |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        _n_pos, exact_oos = _oos_positive(row)
        hit = "n/a" if row.hitrate is None else f"{row.hitrate:.3f}"
        be = "n/a" if row.break_even_win_rate is None else f"{row.break_even_win_rate:.3f}"
        delta = "n/a" if row.hitrate_minus_be is None else f"{row.hitrate_minus_be:.3f}"
        gross = "n/a" if row.gross_pnl is None else f"{row.gross_pnl:.6g}"
        net = "n/a" if row.net_pnl is None else f"{row.net_pnl:.6g}"
        dsr = "n/a" if row.dsr is None else f"{row.dsr:.3f}"
        pbo = "n/a" if row.pbo is None else f"{row.pbo:.3f}"
        reasons = ",".join(row.reject_reasons) if row.reject_reasons else "(none)"
        trades = "n/a" if row.n_trades is None else str(row.n_trades)
        lines.append(
            f"| `{row.config_id}` | {trades} | {hit} | {be} | {delta} | {gross} | "
            f"{net} | {exact_oos} | {dsr} | {pbo} | {str(row.passed).lower()} | {reasons} |"
        )
    lines.extend(
        [
            "",
            "## Honest verdict",
            "",
        ]
    )
    if verdict == "all_kill_no_promotion":
        lines.append(
            "All six pre-registered configs fail the Validation Gate on this "
            "pre-holdout ES tape. That is a kill, not a near-miss. No promotion, "
            "no SIM, no parameter search after seeing the numbers, no extra variants."
        )
    elif verdict == "survivors_exist_no_promotion":
        lines.append(
            "One or more configs passed the packaged gate. The 23:07 GO still "
            "forbids promotion and SIM. Survivors stay research-only."
        )
    elif verdict == "stopped_control_failed":
        lines.append(
            "The cycle stopped because the midpoint positive control / 7/8 null "
            "gate failed. Template results were not used."
        )
    else:
        lines.append("The six configs were not tested. Fail-closed; no promotion.")
    lines.extend(
        [
            "",
            "## Hygiene",
            "",
            "- No live / SIM orders",
            "- Risk Core not modified",
            "- NQ templates remain closed",
            "- Holdout timestamps `>= 2026-01-28T23:00:00Z` were asserted absent",
            "- Max trials = the six pre-registered configs (controls are gate, not variants)",
            "- Optional diagnostics (lower-hitrate / no-lookahead plant) not run",
            "",
        ]
    )
    (report_dir / END_REPORT_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
