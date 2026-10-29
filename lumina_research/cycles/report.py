"""P2 research-cycle report: pre-registration, deaths, survivors, data status."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from lumina_research.cycles.cost_bands import CostBand
from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.geometry import Geometry
from lumina_research.cycles.independence import IndependenceRow
from lumina_research.cycles.p2_cycle import HoldoutEvalRow
from lumina_research.validation.audit import utc_now_iso


@dataclass(frozen=True, slots=True)
class CycleRow:
    hypothesis_id: str
    config_id: str
    template_id: str
    family: str
    instrument: str
    pre_registered: bool
    tested: bool
    passed: bool
    reject_reasons: tuple[str, ...]
    pbo: float | None
    dsr: float | None
    wfe: float | None
    n_oos_windows: int | None
    median_oos: float | None
    geometry: Geometry
    death_reason: str
    n_trades: int | None = None
    hitrate: float | None = None
    break_even_win_rate: float | None = None
    hitrate_minus_be: float | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None
    commission_usd: float | None = None
    half_spread_usd: float | None = None
    slippage_usd: float | None = None
    impact_usd: float | None = None
    is_sharpes: tuple[float, ...] = ()
    oos_sharpes: tuple[float, ...] = ()
    regime_vol_high: float | None = None
    regime_vol_low: float | None = None
    regime_trend_up: float | None = None
    regime_trend_down: float | None = None
    n_trials: int | None = None
    n_days: int | None = None
    pct_positive_oos: float | None = None
    bootstrap_sharpes: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class CycleReport:
    n_hypotheses: int
    n_tested: int
    n_killed: int
    n_survivors: int
    kill_rate: float | None
    kill_rate_flag: str
    cost_bands: tuple[CostBand, ...]
    data: DataStatus
    rows: tuple[CycleRow, ...]
    geometry_by_root: tuple[Geometry, ...]
    stopped: bool
    stop_reason: str
    holdout_seal_sha256: str = ""
    wf_note: str = ""
    independence: tuple[IndependenceRow, ...] = ()
    holdout_eval: tuple[HoldoutEvalRow, ...] = ()
    n_days: int = 0
    previous_holdout_seal_sha256: str = ""
    control_note: str = ""
    planted_detected: bool | None = None
    null_detected: bool | None = None


def write_cycle_reports(report: CycleReport, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    body = {
        "generated_at": utc_now_iso(),
        "agent_id": "hypothesis_agent",
        "n_hypotheses": report.n_hypotheses,
        "n_tested": report.n_tested,
        "n_killed": report.n_killed,
        "n_survivors": report.n_survivors,
        "kill_rate": report.kill_rate,
        "kill_rate_flag": report.kill_rate_flag,
        "cost_bands": [
            {
                "root": item.root,
                "modeled_one_way_ticks": item.modeled_one_way_ticks,
                "modeled_one_way_usd": item.modeled_one_way_usd,
                "modeled_one_way_bp": item.modeled_one_way_bp,
                "band_min": item.band_min,
                "band_max": item.band_max,
                "band_min_usd": item.band_min_usd,
                "band_max_usd": item.band_max_usd,
                "in_band": item.in_band,
                "note": item.note,
                "tick_value_usd": item.tick_value_usd,
                "commission_usd_per_contract_per_side": item.commission_usd_per_contract_per_side,
                "commission_usd_round_trip": item.commission_usd_round_trip,
                "half_spread_usd_per_contract": item.half_spread_usd_per_contract,
                "modeled_eth_one_way_usd": item.modeled_eth_one_way_usd,
                "modeled_eth_one_way_bp": item.modeled_eth_one_way_bp,
            }
            for item in report.cost_bands
        ],
        "stopped": report.stopped,
        "stop_reason": report.stop_reason,
        "data": {
            "usable": report.data.usable,
            "searched": [_portable_fs_path(item) for item in report.data.searched],
            "missing": list(report.data.missing),
            "required": dict(report.data.required),
            "tapes": [
                {
                    "instrument": item.instrument,
                    "bar_size": item.bar_size,
                    "path": _portable_fs_path(item.path),
                    "n_bars": len(item.bars),
                }
                for item in report.data.tapes
            ],
        },
        "geometry": [_geometry_body(item) for item in report.geometry_by_root],
        "hypotheses": [_row_body(item) for item in report.rows],
        "survivors": [_row_body(item) for item in report.rows if item.passed],
        "holdout_seal_sha256": report.holdout_seal_sha256,
        "wf_note": report.wf_note,
        "independence": [
            {
                "config_id": item.config_id,
                "family": item.family,
                "kept": item.kept,
                "reason": item.reason,
                "max_abs_corr": item.max_abs_corr,
            }
            for item in report.independence
        ],
        "holdout_eval": [
            {
                "config_id": item.config_id,
                "family": item.family,
                "instrument": item.instrument,
                "n_days": item.n_days,
                "mean_net": item.mean_net,
                "sharpe": item.sharpe,
                "n_positive_days": item.n_positive_days,
                "max_drawdown": item.max_drawdown,
            }
            for item in report.holdout_eval
        ],
        "n_days": report.n_days,
        "previous_holdout_seal_sha256": report.previous_holdout_seal_sha256,
        "control_note": report.control_note,
        "planted_detected": report.planted_detected,
        "null_detected": report.null_detected,
    }
    json_path = directory / "phase5_research_cycles.json"
    json_path.write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path = directory / "phase5_research_cycles.md"
    md_path.write_text(_markdown(report), encoding="utf-8")
    (directory / "phase5_p2_results.md").write_text(_results_table(report), encoding="utf-8")
    return json_path, md_path


def _geometry_body(item: Geometry) -> dict[str, object]:
    return {
        "root": item.root,
        "target_ticks": item.target_ticks,
        "stop_ticks": item.stop_ticks,
        "tick_value_usd": item.tick_value_usd,
        "roundtrip_cost_ticks": item.roundtrip_cost_ticks,
        "net_target_ticks": item.net_target_ticks,
        "net_stop_ticks": item.net_stop_ticks,
        "net_target_usd": item.net_target_usd,
        "net_stop_usd": item.net_stop_usd,
        "break_even_win_rate": item.break_even_win_rate,
    }


def _row_body(item: CycleRow) -> dict[str, object]:
    return {
        "hypothesis_id": item.hypothesis_id,
        "config_id": item.config_id,
        "template_id": item.template_id,
        "family": item.family,
        "instrument": item.instrument,
        "pre_registered": item.pre_registered,
        "tested": item.tested,
        "passed": item.passed,
        "reject_reasons": list(item.reject_reasons),
        "pbo": item.pbo,
        "dsr": item.dsr,
        "wfe": item.wfe,
        "n_oos_windows": item.n_oos_windows,
        "median_oos": item.median_oos,
        "geometry": _geometry_body(item.geometry),
        "death_reason": item.death_reason,
        "n_trades": item.n_trades,
        "hitrate": item.hitrate,
        "break_even_win_rate": item.break_even_win_rate,
        "hitrate_minus_be": item.hitrate_minus_be,
        "gross_pnl": item.gross_pnl,
        "net_pnl": item.net_pnl,
        "commission_usd": item.commission_usd,
        "half_spread_usd": item.half_spread_usd,
        "slippage_usd": item.slippage_usd,
        "impact_usd": item.impact_usd,
        "is_sharpes": list(item.is_sharpes),
        "oos_sharpes": list(item.oos_sharpes),
        "regime_vol_high": item.regime_vol_high,
        "regime_vol_low": item.regime_vol_low,
        "regime_trend_up": item.regime_trend_up,
        "regime_trend_down": item.regime_trend_down,
        "n_trials": item.n_trials,
        "n_days": item.n_days,
        "pct_positive_oos": item.pct_positive_oos,
        "bootstrap_sharpes": list(item.bootstrap_sharpes),
    }


def _markdown(report: CycleReport) -> str:
    kill = "n/a" if report.kill_rate is None else f"{report.kill_rate:.4f}"
    lines = [
        "# Phase 5 P2 research cycles",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        f"- hypotheses: `{report.n_hypotheses}` tested: `{report.n_tested}` killed: `{report.n_killed}` survivors: `{report.n_survivors}`",
        f"- kill_rate: `{kill}` (expectation > 0.90, diagnostic flag `{report.kill_rate_flag}`)",
        f"- stopped: `{report.stopped}` reason: `{report.stop_reason}`",
        f"- real data usable: `{report.data.usable}`",
        "",
        "## Data requirement (if unusable)",
        "",
    ]
    for key, value in report.data.required.items():
        lines.append(f"- **{key}**: {value}")
    searched = ", ".join(_portable_fs_path(item) for item in report.data.searched) or "(none)"
    lines.extend(
        ["", f"- searched: {searched}", f"- missing instruments: {', '.join(report.data.missing) or '(none)'}", ""]
    )
    lines.extend(
        [
            "## Modeled costs vs instrument-specific USD/contract bands",
            "",
            "| root | comm $/side | comm $ RT | half-spread $ | RTH $/contract | RTH bp | ETH $/contract | band $/contract | in_band | note |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for band in report.cost_bands:
        lines.append(
            f"| {band.root} | {band.commission_usd_per_contract_per_side:.2f} | "
            f"{band.commission_usd_round_trip:.2f} | {band.half_spread_usd_per_contract:.3f} | "
            f"{band.modeled_one_way_usd:.3f} | {band.modeled_one_way_bp:.3f} | "
            f"{band.modeled_eth_one_way_usd:.3f} | {band.band_min_usd:.2f}-{band.band_max_usd:.2f} | "
            f"{band.in_band} | {band.note} |"
        )
    lines.extend(
        [
            "",
            "## Costs and tick floors",
            "",
            "| root | target ticks | stop ticks | tick $ | RT cost ticks | net target $ | net stop $ | BE win rate |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for geo in report.geometry_by_root:
        lines.append(
            f"| {geo.root} | {geo.target_ticks} | {geo.stop_ticks} | {geo.tick_value_usd:.2f} | "
            f"{geo.roundtrip_cost_ticks:.3f} | {geo.net_target_usd:.2f} | {geo.net_stop_usd:.2f} | "
            f"{geo.break_even_win_rate:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Hypotheses",
            "",
            "| id | template | inst | tested | passed | death | PBO | DSR | WFE |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in report.rows:
        pbo = "n/a" if row.pbo is None else f"{row.pbo:.3f}"
        dsr = "n/a" if row.dsr is None else f"{row.dsr:.3f}"
        wfe = "n/a" if row.wfe is None else f"{row.wfe:.3f}"
        lines.append(
            f"| {row.hypothesis_id} | {row.template_id} | {row.instrument} | {row.tested} | {row.passed} | "
            f"{row.death_reason} | {pbo} | {dsr} | {wfe} |"
        )
    survivors = [row for row in report.rows if row.passed]
    lines.extend(["", "## Survivors", ""])
    if not survivors:
        lines.append("None. Expected: most economically simple hypotheses die at the Validation Gate.")
    else:
        for row in survivors:
            lines.append(f"- `{row.hypothesis_id}` PBO={row.pbo} DSR={row.dsr} WFE={row.wfe} OOS={row.median_oos}")
    if report.holdout_seal_sha256:
        lines.extend(
            [
                "",
                "## Holdout seal",
                "",
                f"- sha256: `{report.holdout_seal_sha256}`",
                f"- previous_seal: `{report.previous_holdout_seal_sha256 or 'n/a'}`",
                f"- windows: {report.wf_note}",
                f"- n_days: `{report.n_days}`",
                "- pin: `2026-01-28T23:00:00+00:00` Globex session boundary (legacy `2026-01-29T00:00:00Z` recorded)",
                "- holdout sealed and unopened for ranking, tuning, and gate calibration",
                "- 1m four-leg costs (ADR-0055/1.2 RTH-ETH session slippage) then Globex session-day resample",
                "- floors unchanged: DSR>=0.95, PBO hard 0.50 / warn 0.25, min 6 OOS; static rules use A2 not WFE",
                "- geometry is pre-registered per template; shadow only; zero orders; S0 freeze untouched",
                f"- positive_control_detected: `{report.planted_detected}` null_detected: `{report.null_detected}`",
                f"- control: {report.control_note or 'n/a'}",
                "",
            ]
        )
    if report.independence:
        lines.extend(
            ["", "## Independence", "", "| config | family | kept | reason | abs_corr |", "|---|---|---|---|---|"]
        )
        for indep in report.independence:
            corr = "n/a" if indep.max_abs_corr is None else f"{indep.max_abs_corr:.3f}"
            lines.append(f"| {indep.config_id} | {indep.family} | {indep.kept} | {indep.reason} | {corr} |")
    if report.holdout_eval:
        lines.extend(
            [
                "",
                "## Holdout evaluation (survivors only, one pass)",
                "",
                "| config | days | mean | Sharpe | +days | maxDD |",
                "|---|---|---|---|---|---|",
            ]
        )
        for eval_row in report.holdout_eval:
            lines.append(
                f"| {eval_row.config_id} | {eval_row.n_days} | {eval_row.mean_net:.6f} | {eval_row.sharpe:.3f} | "
                f"{eval_row.n_positive_days} | {eval_row.max_drawdown:.6f} |"
            )
    elif report.holdout_seal_sha256:
        lines.extend(
            [
                "",
                "## Holdout evaluation (survivors only, one pass)",
                "",
                "Skipped: no independent survivors. The sealed window was not used for ranking or calibration.",
                "",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _portable_fs_path(path: Path | str) -> str:
    raw = str(path)
    root = os.environ.get("LUMINA_RESEARCH_DATA_DIR", "").rstrip("/")
    if not root:
        return raw
    if raw == root:
        return "$LUMINA_RESEARCH_DATA_DIR"
    prefix = root + "/"
    if raw.startswith(prefix):
        return "$LUMINA_RESEARCH_DATA_DIR/" + raw[len(prefix) :]
    return raw


def death_reason(*, tested: bool, passed: bool, reasons: Sequence[str], stopped: bool) -> str:
    if not tested:
        return "not_tested_no_real_data" if stopped else "not_tested"
    if passed:
        return "survived"
    if reasons:
        return ",".join(reasons)
    return "rejected_without_reasons"


def mapping_metric(metrics: Mapping[str, object], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _results_table(report: CycleReport) -> str:
    lines = [
        "# Phase 5 P2 results (kill / survive)",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        f"- tested: `{report.n_tested}` killed: `{report.n_killed}` survivors: `{report.n_survivors}`",
        f"- kill_rate: `{'n/a' if report.kill_rate is None else f'{report.kill_rate:.4f}'}`",
        f"- holdout_seal: `{report.holdout_seal_sha256 or 'n/a'}`",
        f"- previous_holdout_seal: `{report.previous_holdout_seal_sha256 or 'n/a'}`",
        f"- windows: `{report.wf_note or 'n/a'}`",
        f"- n_days: `{report.n_days}`",
        f"- planted_detected: `{report.planted_detected}` null_detected: `{report.null_detected}`",
        "",
        "| config | template | inst | verdict | death / reason | PBO | DSR | WFE | OOS windows | median OOS | n_trades | hitrate | BE | gross | net | N | +OOS | n_days |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report.rows:
        verdict = "survive" if row.passed else ("untested" if not row.tested else "kill")
        pbo = "n/a" if row.pbo is None else f"{row.pbo:.3f}"
        dsr = "n/a" if row.dsr is None else f"{row.dsr:.3f}"
        wfe = "n/a" if row.wfe is None else f"{row.wfe:.3f}"
        windows = "n/a" if row.n_oos_windows is None else str(row.n_oos_windows)
        median = "n/a" if row.median_oos is None else f"{row.median_oos:.6g}"
        trades = "n/a" if row.n_trades is None else str(row.n_trades)
        hit = "n/a" if row.hitrate is None else f"{row.hitrate:.3f}"
        be = "n/a" if row.break_even_win_rate is None else f"{row.break_even_win_rate:.3f}"
        gross = "n/a" if row.gross_pnl is None else f"{row.gross_pnl:.6g}"
        net = "n/a" if row.net_pnl is None else f"{row.net_pnl:.6g}"
        trials = "n/a" if row.n_trials is None else str(row.n_trials)
        pos = "n/a" if row.pct_positive_oos is None else f"{row.pct_positive_oos:.3f}"
        days = "n/a" if row.n_days is None else str(row.n_days)
        lines.append(
            f"| {row.config_id} | {row.template_id} | {row.instrument} | {verdict} | "
            f"{row.death_reason} | {pbo} | {dsr} | {wfe} | {windows} | {median} | "
            f"{trades} | {hit} | {be} | {gross} | {net} | {trials} | {pos} | {days} |"
        )
    lines.extend(
        [
            "",
            "## Per-config diagnostics (D14)",
            "",
            "| config | commission $ | half-spread $ | slippage $ | impact $ | IS Sharpes | OOS Sharpes | volH | volL | trendU | trendD | bootstrap n |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in report.rows:
        comm = "n/a" if row.commission_usd is None else f"{row.commission_usd:.4g}"
        spread = "n/a" if row.half_spread_usd is None else f"{row.half_spread_usd:.4g}"
        slip = "n/a" if row.slippage_usd is None else f"{row.slippage_usd:.4g}"
        impact = "n/a" if row.impact_usd is None else f"{row.impact_usd:.4g}"
        is_s = "n/a" if not row.is_sharpes else ",".join(f"{item:.3f}" for item in row.is_sharpes)
        oos_s = "n/a" if not row.oos_sharpes else ",".join(f"{item:.3f}" for item in row.oos_sharpes)
        vol_h = "n/a" if row.regime_vol_high is None else f"{row.regime_vol_high:.3f}"
        vol_l = "n/a" if row.regime_vol_low is None else f"{row.regime_vol_low:.3f}"
        up = "n/a" if row.regime_trend_up is None else f"{row.regime_trend_up:.3f}"
        down = "n/a" if row.regime_trend_down is None else f"{row.regime_trend_down:.3f}"
        boot = str(len(row.bootstrap_sharpes))
        lines.append(
            f"| {row.config_id} | {comm} | {spread} | {slip} | {impact} | {is_s} | {oos_s} | "
            f"{vol_h} | {vol_l} | {up} | {down} | {boot} |"
        )
    kept = [indep for indep in report.independence if indep.kept]
    lines.extend(["", "## Independent survivors", ""])
    if not kept:
        lines.append("None.")
    else:
        for kept_row in kept:
            corr = "n/a" if kept_row.max_abs_corr is None else f"{kept_row.max_abs_corr:.3f}"
            lines.append(f"- `{kept_row.config_id}` family=`{kept_row.family}` abs_corr={corr}")
    if report.holdout_eval:
        lines.extend(
            [
                "",
                "## Holdout (survivors only, one pass, not a second gate)",
                "",
                "| config | days | mean net | Sharpe | +days | maxDD |",
                "|---|---|---|---|---|---|",
            ]
        )
        for eval_row in report.holdout_eval:
            lines.append(
                f"| {eval_row.config_id} | {eval_row.n_days} | {eval_row.mean_net:.6f} | {eval_row.sharpe:.3f} | "
                f"{eval_row.n_positive_days} | {eval_row.max_drawdown:.6f} |"
            )
    elif report.holdout_seal_sha256:
        lines.extend(
            [
                "",
                "## Holdout evaluation",
                "",
                "Skipped: no independent survivors. The sealed window was not used for ranking or calibration.",
                "",
            ]
        )
    lines.append("")
    return "\n".join(lines)
