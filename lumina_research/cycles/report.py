"""P2 research-cycle report: pre-registration, deaths, survivors, data status."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from lumina_research.cycles.cost_bands import CostBand
from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.geometry import Geometry
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
                "band_min": item.band_min,
                "band_max": item.band_max,
                "in_band": item.in_band,
                "note": item.note,
            }
            for item in report.cost_bands
        ],
        "stopped": report.stopped,
        "stop_reason": report.stop_reason,
        "data": {
            "usable": report.data.usable,
            "searched": list(report.data.searched),
            "missing": list(report.data.missing),
            "required": dict(report.data.required),
            "tapes": [
                {
                    "instrument": item.instrument,
                    "bar_size": item.bar_size,
                    "path": str(item.path),
                    "n_bars": len(item.bars),
                }
                for item in report.data.tapes
            ],
        },
        "geometry": [_geometry_body(item) for item in report.geometry_by_root],
        "hypotheses": [_row_body(item) for item in report.rows],
        "survivors": [_row_body(item) for item in report.rows if item.passed],
    }
    json_path = directory / "phase5_research_cycles.json"
    json_path.write_text(json.dumps(body, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path = directory / "phase5_research_cycles.md"
    md_path.write_text(_markdown(report), encoding="utf-8")
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
    lines.extend(["", f"- searched: {', '.join(report.data.searched) or '(none)'}", f"- missing instruments: {', '.join(report.data.missing) or '(none)'}", ""])
    lines.extend(
        [
            "## Modeled costs vs briefed bands (CostModel unchanged)",
            "",
            "| root | modeled one-way ticks | band | in_band | note |",
            "|---|---|---|---|---|",
        ]
    )
    for band in report.cost_bands:
        lines.append(
            f"| {band.root} | {band.modeled_one_way_ticks:.3f} | {band.band_min:.1f}-{band.band_max:.1f} | "
            f"{band.in_band} | {band.note} |"
        )
    lines.extend(["", "## Costs and tick floors", "", "| root | target ticks | stop ticks | tick $ | RT cost ticks | net target $ | net stop $ | BE win rate |", "|---|---|---|---|---|---|---|---|"])
    for geo in report.geometry_by_root:
        lines.append(
            f"| {geo.root} | {geo.target_ticks} | {geo.stop_ticks} | {geo.tick_value_usd:.2f} | "
            f"{geo.roundtrip_cost_ticks:.3f} | {geo.net_target_usd:.2f} | {geo.net_stop_usd:.2f} | "
            f"{geo.break_even_win_rate:.3f} |"
        )
    lines.extend(["", "## Hypotheses", "", "| id | template | inst | tested | passed | death | PBO | DSR | WFE |", "|---|---|---|---|---|---|---|---|---|"])
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
    lines.append("")
    return "\n".join(lines)


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
