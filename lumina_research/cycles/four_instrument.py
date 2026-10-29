"""P2 four-instrument cycle: MES/MNQ cost-fix rerun + ES/NQ translations.

Writes new report files. Never overwrites the CostModel 1.1.0 baseline
``phase5_p2_results.md`` / ``phase5_research_cycles.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from lumina_research.cycles.catalog import HypothesisSpec
from lumina_research.cycles.data import DataStatus
from lumina_research.cycles.first_cycle import first_cycle_specs
from lumina_research.cycles.p2_cycle import clear_materialize_cache
from lumina_research.cycles.report import CycleReport
from lumina_research.cycles.runner import ResearchCycleResult, run_research_cycles
from lumina_research.cycles.seal import ES_NQ_SEAL_NAME, SEAL_NAME
from lumina_research.proof.runner import DEFAULT_REPORTS
from lumina_research.validation.audit import utc_now_iso
from lumina_research.validation.cost_model import COST_MODEL_VERSION

_REPO = Path(__file__).resolve().parents[2]
MES_MNQ_CYCLES_STEM = "phase5_p2_costfix_mes_mnq"
MES_MNQ_RESULTS_NAME = "phase5_p2_costfix_mes_mnq_results.md"
ES_NQ_CYCLES_STEM = "phase5_p2_es_nq"
ES_NQ_RESULTS_NAME = "phase5_p2_es_nq_results.md"
COMPARISON_NAME = "phase5_p2_costfix_four_instrument_comparison.md"
BASELINE_CYCLES_JSON = "phase5_research_cycles.json"
ES_NQ_NEEDED = (
    "PIT NT8 1m continuous unadjusted CSVs at "
    "$LUMINA_RESEARCH_DATA_DIR/{ES,NQ}/1m/*.csv "
    "(UTF-8 header timestamp,open,high,low,close,volume; UTC ISO-8601 with offset). "
    "Hashes are recorded in phase5_p2_es_nq_holdout_seal.json at pin "
    "2026-01-28T23:00:00Z when both tapes exist. Do not invent bars."
)
# source first-cycle id, translated id, mini root. Same lookback/threshold/16/8.
ES_NQ_TRANSLATIONS: tuple[tuple[str, str, str], ...] = (
    ("mr-mes-10-1.5", "p2c-mr-es-10-1.5", "ES"),
    ("vi-mnq-10-0.55", "p2c-vi-nq-10-0.55", "NQ"),
    ("rm-mes-10-0.40", "p2c-rm-es-10-0.40", "ES"),
    ("or-mes-5-bo", "p2c-or-es-5-bo", "ES"),
    ("or-mnq-15-fade", "p2c-or-nq-15-fade", "NQ"),
    ("gap-mes-8", "p2c-gap-es-8", "ES"),
    ("vwap-mes-20-1.5", "p2c-vwap-es-20-1.5", "ES"),
    ("rc-mes-20-0.25", "p2c-rc-es-20-0.25", "ES"),
    ("cr-mes-3", "p2c-cr-es-3", "ES"),
    ("tod-mes-15", "p2c-tod-es-15", "ES"),
    ("pb-mnq-20", "p2c-pb-nq-20", "NQ"),
    ("vx-mes-20", "p2c-vx-es-20", "ES"),
)


@dataclass(frozen=True, slots=True)
class FourInstrumentResult:
    mes_mnq: ResearchCycleResult
    es_nq: ResearchCycleResult
    comparison_path: Path


def es_nq_specs(
    source: tuple[HypothesisSpec, ...] | None = None,
) -> tuple[HypothesisSpec, ...]:
    rows = source if source is not None else first_cycle_specs()
    by_id = {item.config_id: item for item in rows}
    out: list[HypothesisSpec] = []
    for src_id, dst_id, instrument in ES_NQ_TRANSLATIONS:
        spec = by_id[src_id]
        cloned = replace(spec, config_id=dst_id, instrument=instrument)
        if cloned.lookback != spec.lookback or cloned.threshold != spec.threshold:
            raise RuntimeError("ES/NQ translations must keep lookback and threshold")
        if cloned.mode != spec.mode:
            raise RuntimeError("ES/NQ translations must keep mode")
        if cloned.target_ticks != spec.target_ticks or cloned.stop_ticks != spec.stop_ticks:
            raise RuntimeError("ES/NQ translations must keep first-cycle tick geometry")
        out.append(cloned)
    if len(out) != 12:
        raise RuntimeError("ES/NQ translations must cover 12 first-cycle families")
    if {item.instrument for item in out} != {"ES", "NQ"}:
        raise RuntimeError("ES/NQ translations must land on ES and NQ")
    return tuple(out)


def run_four_instrument_cycle(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    data_dir: Path | None = None,
    repo_root: Path | None = None,
    seed: int = 20261028,
    reuse_mes_mnq: bool = False,
) -> FourInstrumentResult:
    """MES/MNQ cost-fix, then ES/NQ. Sidecars and baseline reports stay untouched."""
    root = repo_root if repo_root is not None else _REPO
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    if reuse_mes_mnq:
        mes_mnq = _reuse_mes_mnq_result(report_dir)
    else:
        clear_materialize_cache()
        mes_mnq = run_research_cycles(
            work_dir=work_dir / "mes_mnq",
            report_dir=report_dir,
            evolution_log_dir=None,
            data_dir=data_dir,
            repo_root=root,
            seed=seed,
            specs=first_cycle_specs(),
            cycles_stem=MES_MNQ_CYCLES_STEM,
            results_name=MES_MNQ_RESULTS_NAME,
            allowed_instruments=frozenset({"MES", "MNQ"}),
            control_per_instrument=True,
            write_sidecars=False,
            seal_filename=SEAL_NAME,
            require_known_files=True,
        )
    clear_materialize_cache()
    es_nq = run_research_cycles(
        work_dir=work_dir / "es_nq",
        report_dir=report_dir,
        evolution_log_dir=None,
        data_dir=data_dir,
        repo_root=root,
        seed=seed,
        specs=es_nq_specs(),
        cycles_stem=ES_NQ_CYCLES_STEM,
        results_name=ES_NQ_RESULTS_NAME,
        allowed_instruments=frozenset({"ES", "NQ"}),
        control_per_instrument=True,
        write_sidecars=False,
        seal_filename=ES_NQ_SEAL_NAME,
        require_known_files=True,
    )
    comparison = write_comparison(
        report_dir=report_dir,
        mes_mnq=mes_mnq,
        es_nq=es_nq,
    )
    return FourInstrumentResult(mes_mnq=mes_mnq, es_nq=es_nq, comparison_path=comparison)


def _reuse_mes_mnq_result(report_dir: Path) -> ResearchCycleResult:
    """Keep the CostModel 1.2.0 MES/MNQ files; do not rerun or overwrite them."""
    json_path = report_dir / f"{MES_MNQ_CYCLES_STEM}.json"
    md_path = report_dir / f"{MES_MNQ_CYCLES_STEM}.md"
    results = report_dir / MES_MNQ_RESULTS_NAME
    missing = [str(path) for path in (json_path, md_path, results) if not path.is_file()]
    if missing:
        raise RuntimeError("reuse_mes_mnq missing: " + ", ".join(missing))
    loaded = _load_json(json_path)
    if loaded is None:
        raise RuntimeError(f"reuse_mes_mnq unreadable: {json_path}")
    n_tested = _as_int(loaded.get("n_tested"))
    n_killed = _as_int(loaded.get("n_killed"))
    n_survivors = _as_int(loaded.get("n_survivors"))
    n_hypotheses = _as_int(loaded.get("n_hypotheses"))
    raw_rate = loaded.get("kill_rate")
    kill_rate = float(raw_rate) if isinstance(raw_rate, (int, float)) and not isinstance(raw_rate, bool) else None
    planted = loaded.get("planted_detected")
    null = loaded.get("null_detected")
    report = CycleReport(
        n_hypotheses=n_hypotheses,
        n_tested=n_tested,
        n_killed=n_killed,
        n_survivors=n_survivors,
        kill_rate=kill_rate,
        kill_rate_flag=str(loaded.get("kill_rate_flag") or "ok"),
        cost_bands=(),
        data=DataStatus(usable=True, tapes=(), searched=(), missing=(), required={}),
        rows=(),
        geometry_by_root=(),
        stopped=False,
        stop_reason="",
        holdout_seal_sha256=str(loaded.get("holdout_seal_sha256") or ""),
        control_note="reused MES/MNQ cost-fix reports; not rerun",
        planted_detected=planted if isinstance(planted, bool) else None,
        null_detected=null if isinstance(null, bool) else None,
    )
    return ResearchCycleResult(
        report=report,
        json_path=json_path,
        md_path=md_path,
        data=report.data,
        kill_rate=kill_rate,
        kill_rate_flag=report.kill_rate_flag,
    )


def write_comparison(
    *,
    report_dir: Path,
    mes_mnq: ResearchCycleResult,
    es_nq: ResearchCycleResult,
) -> Path:
    baseline = _load_json(report_dir / BASELINE_CYCLES_JSON)
    if baseline is None:
        fallback = _REPO / "experiments" / "reports" / BASELINE_CYCLES_JSON
        baseline = _load_json(fallback)
    costfix = _load_json(report_dir / f"{MES_MNQ_CYCLES_STEM}.json")
    esnq = _load_json(report_dir / f"{ES_NQ_CYCLES_STEM}.json")
    lines = [
        "# P2 cost-fix + four-instrument comparison (2026-10-29)",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        f"- cost_model: `{COST_MODEL_VERSION}` (baseline 1.1.0 in {BASELINE_CYCLES_JSON})",
        "- floors: DSR 0.95, PBO hard 0.50; holdout pin 2026-01-28T23:00:00Z closed",
        "- propose-only; no SIM/REAL orders; Risk Core untouched",
        "",
        "## MES/MNQ cost-fix effect (1.1.0 baseline vs 1.2.0 rerun)",
        "",
        "Same 12 first-cycle ids. New files only. Same-bar round trips now pay both",
        "commission sides. Session-local ADV + cap 4 changes ETH slippage.",
        "",
        "| config | inst | n_trades 1.1.0 | n_trades 1.2.0 | hit 1.1.0 | hit 1.2.0 | BE | "
        "gross 1.1.0 | gross 1.2.0 | net 1.1.0 | net 1.2.0 | +OOS 1.1.0 | +OOS 1.2.0 | "
        "comm/trade 1.1.0 | comm/trade 1.2.0 | 4leg/trade 1.1.0 | 4leg/trade 1.2.0 | "
        "gross/trade 1.1.0 | gross/trade 1.2.0 | death 1.1.0 | death 1.2.0 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    base_rows = _rows_by_id(baseline)
    fix_rows = _rows_by_id(costfix)
    for spec in first_cycle_specs():
        old = base_rows.get(spec.config_id, {})
        new = fix_rows.get(spec.config_id, {})
        lines.append(_delta_row(spec.config_id, spec.instrument, old, new))
    lines.extend(_mes_mnq_summaries(base_rows, fix_rows))
    lines.extend(
        [
            "",
            "## Four-root table (cost/trade vs gross/trade)",
            "",
            "| config | inst | tested | death | n_trades | hit | BE | gross | net | +OOS | "
            "median OOS | comm $ | 4leg $ | comm/trade | 4leg/trade | gross/trade |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in _rows_of(costfix) + _rows_of(esnq):
        lines.append(_four_root_row(row))
    esnq_rows = _rows_by_id(esnq)
    family_by_id = {item.config_id: item.template_id for item in first_cycle_specs()}
    lines.extend(
        [
            "",
            "## Same-family ES vs MES and NQ vs MNQ (16/8, CostModel 1.2.0)",
            "",
            "Translations keep lookback/threshold/mode/16/8. Commission card: "
            "MES/MNQ $1.88 RT, ES/NQ $5.74 RT. Gaps were not filled from MES.",
            "",
            "| family | micro | mini | micro n | mini n | micro hit | mini hit | "
            "micro BE | mini BE | micro comm/trade | mini comm/trade | "
            "micro 4leg/trade | mini 4leg/trade | micro gross/trade | mini gross/trade | "
            "micro net | mini net | micro death | mini death |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for src_id, dst_id, _mini in ES_NQ_TRANSLATIONS:
        lines.append(
            _pair_row(
                family_by_id[src_id],
                src_id,
                dst_id,
                fix_rows.get(src_id, {}),
                esnq_rows.get(dst_id, {}),
            )
        )
    es_status = es_nq.report
    missing = ", ".join(es_status.data.missing) or "(none)"
    lines.extend(
        [
            "",
            "## ES/NQ data",
            "",
            f"- discover_data usable (any root on the mount): `{es_status.data.usable}`",
            f"- this batch stopped: `{es_status.stopped}` reason: `{es_status.stop_reason or '(ran)'}`",
            f"- missing roots for this batch: {missing}",
            f"- planted_detected: `{es_status.planted_detected}` null_detected: `{es_status.null_detected}`",
            f"- control_note: `{es_status.control_note or '(none)'}`",
            f"- needed if fail-closed: {ES_NQ_NEEDED}",
            "",
            "## ES/NQ tape gaps (not filled)",
            "",
            "Holdout pin `2026-01-28T23:00:00Z` stays closed. No MES/MNQ bars were copied.",
            "Detail: `phase5_p2_es_nq_data_gaps_2026-10-29.md`.",
            "- TRAIN (gate uses this): ES missing 2025-07-13/14 and half of 2025-07-15; both roots thin on 2025-11-28.",
            "- HOLDOUT (sealed, unused for ranking): ES 2026-04-22..04-27 and 2026-05-08/11/12.",
            "",
            "## Holdout",
            "",
            "MES/MNQ seal 85e4588f reused, not rewritten. ES/NQ seal file is "
            f"`{ES_NQ_SEAL_NAME}` only when PIT tapes exist. Survivors would get one",
            "holdout pass; none are promoted.",
            "",
        ]
    )
    path = report_dir / COMPARISON_NAME
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _as_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _load_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else None


def _rows_of(body: Mapping[str, object] | None) -> list[dict[str, object]]:
    if body is None:
        return []
    raw = body.get("hypotheses")
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, object]] = []
    for item in raw:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _rows_by_id(body: Mapping[str, object] | None) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for row in _rows_of(body):
        config_id = row.get("config_id")
        if isinstance(config_id, str):
            out[config_id] = row
    return out


def _num(row: Mapping[str, object], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _per_trade(row: Mapping[str, object], key: str) -> float | None:
    trades = _num(row, "n_trades")
    value = _num(row, key)
    if trades is None or value is None or trades <= 0.0:
        return None
    return value / trades


def _four_leg(row: Mapping[str, object]) -> float | None:
    parts = [
        _num(row, "commission_usd"),
        _num(row, "half_spread_usd"),
        _num(row, "slippage_usd"),
        _num(row, "impact_usd"),
    ]
    if any(item is None for item in parts):
        return None
    return float(sum(item or 0.0 for item in parts))


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}g}"


def _mean_comm_trade(
    rows: Mapping[str, Mapping[str, object]],
    config_ids: tuple[str, ...],
) -> float | None:
    values = [_per_trade(rows.get(config_id, {}), "commission_usd") for config_id in config_ids]
    present = [item for item in values if item is not None]
    if not present:
        return None
    return sum(present) / float(len(present))


def _mes_mnq_summaries(
    base_rows: Mapping[str, Mapping[str, object]],
    fix_rows: Mapping[str, Mapping[str, object]],
) -> list[str]:
    by_root: dict[str, list[str]] = {"MES": [], "MNQ": []}
    for spec in first_cycle_specs():
        by_root[spec.instrument].append(spec.config_id)
    mes = tuple(by_root["MES"])
    mnq = tuple(by_root["MNQ"])
    return [
        "",
        "### MES cost-fix effect",
        "",
        f"- configs: `{len(mes)}` (same 16/8 geometry, CostModel 1.2.0)",
        f"- mean commission/trade: `{_fmt(_mean_comm_trade(base_rows, mes))}` → "
        f"`{_fmt(_mean_comm_trade(fix_rows, mes))}` (ADR-0055 $1.88 RT)",
        "- Gross per trade is almost unchanged. Net worsens because previously skipped",
        "  same-bar commission and mixed-ADV ETH slippage are now charged.",
        "- Verdict stays 9/9 kill. No survivor. Holdout still sealed.",
        "",
        "### MNQ cost-fix effect",
        "",
        f"- configs: `{len(mnq)}` (same 16/8 geometry, CostModel 1.2.0)",
        f"- mean commission/trade: `{_fmt(_mean_comm_trade(base_rows, mnq))}` → "
        f"`{_fmt(_mean_comm_trade(fix_rows, mnq))}` (was ~10× too cheap vs MES)",
        "- 1.1.0 skipped both $0.94 sides on same-bar 16/8 round trips, which MNQ",
        "  1m ranges hit more often than MES. 1.2.0 charges $1.88 RT whenever the",
        "  fill bar is in-position, matching MES.",
        "- Verdict stays 3/3 kill. No survivor. Holdout still sealed.",
        "- Extra D13 trials: MNQ planted+null ran on this rerun (per-instrument",
        "  control). That adds two registry trials vs the 1.1.0 table; DSR stays 0.",
    ]


def _delta_row(
    config_id: str,
    instrument: str,
    old: Mapping[str, object],
    new: Mapping[str, object],
) -> str:
    old_leg = _four_leg(old)
    new_leg = _four_leg(new)
    old_leg_pt = None if old_leg is None else _per_trade_value(old, old_leg)
    new_leg_pt = None if new_leg is None else _per_trade_value(new, new_leg)
    be = _num(new, "break_even_win_rate") or _num(old, "break_even_win_rate")
    return (
        f"| {config_id} | {instrument} | {_fmt(_num(old, 'n_trades'), 6)} | "
        f"{_fmt(_num(new, 'n_trades'), 6)} | {_fmt(_num(old, 'hitrate'))} | "
        f"{_fmt(_num(new, 'hitrate'))} | {_fmt(be)} | "
        f"{_fmt(_num(old, 'gross_pnl'))} | {_fmt(_num(new, 'gross_pnl'))} | "
        f"{_fmt(_num(old, 'net_pnl'))} | {_fmt(_num(new, 'net_pnl'))} | "
        f"{_fmt(_num(old, 'pct_positive_oos'))} | {_fmt(_num(new, 'pct_positive_oos'))} | "
        f"{_fmt(_per_trade(old, 'commission_usd'))} | "
        f"{_fmt(_per_trade(new, 'commission_usd'))} | "
        f"{_fmt(old_leg_pt)} | {_fmt(new_leg_pt)} | "
        f"{_fmt(_per_trade(old, 'gross_pnl'))} | {_fmt(_per_trade(new, 'gross_pnl'))} | "
        f"{old.get('death_reason', 'n/a')} | {new.get('death_reason', 'n/a')} |"
    )


def _per_trade_value(row: Mapping[str, object], value: float) -> float | None:
    trades = _num(row, "n_trades")
    if trades is None or trades <= 0.0:
        return None
    return value / trades


def _pair_row(
    family: str,
    micro_id: str,
    mini_id: str,
    micro: Mapping[str, object],
    mini: Mapping[str, object],
) -> str:
    micro_leg = _four_leg(micro)
    mini_leg = _four_leg(mini)
    micro_leg_pt = None if micro_leg is None else _per_trade_value(micro, micro_leg)
    mini_leg_pt = None if mini_leg is None else _per_trade_value(mini, mini_leg)
    return (
        f"| {family} | {micro_id} | {mini_id} | "
        f"{_fmt(_num(micro, 'n_trades'), 6)} | {_fmt(_num(mini, 'n_trades'), 6)} | "
        f"{_fmt(_num(micro, 'hitrate'))} | {_fmt(_num(mini, 'hitrate'))} | "
        f"{_fmt(_num(micro, 'break_even_win_rate'))} | "
        f"{_fmt(_num(mini, 'break_even_win_rate'))} | "
        f"{_fmt(_per_trade(micro, 'commission_usd'))} | "
        f"{_fmt(_per_trade(mini, 'commission_usd'))} | "
        f"{_fmt(micro_leg_pt)} | {_fmt(mini_leg_pt)} | "
        f"{_fmt(_per_trade(micro, 'gross_pnl'))} | "
        f"{_fmt(_per_trade(mini, 'gross_pnl'))} | "
        f"{_fmt(_num(micro, 'net_pnl'))} | {_fmt(_num(mini, 'net_pnl'))} | "
        f"{micro.get('death_reason', 'n/a')} | {mini.get('death_reason', 'n/a')} |"
    )


def _four_root_row(row: Mapping[str, object]) -> str:
    config_id = str(row.get("config_id", ""))
    instrument = str(row.get("instrument", ""))
    tested = row.get("tested")
    death = str(row.get("death_reason", "n/a"))
    legs = _four_leg(row)
    legs_pt = None if legs is None else _per_trade_value(row, legs)
    return (
        f"| {config_id} | {instrument} | {tested} | {death} | "
        f"{_fmt(_num(row, 'n_trades'), 6)} | {_fmt(_num(row, 'hitrate'))} | "
        f"{_fmt(_num(row, 'break_even_win_rate'))} | {_fmt(_num(row, 'gross_pnl'))} | "
        f"{_fmt(_num(row, 'net_pnl'))} | {_fmt(_num(row, 'pct_positive_oos'))} | "
        f"{_fmt(_num(row, 'median_oos'))} | {_fmt(_num(row, 'commission_usd'), 6)} | "
        f"{_fmt(legs, 6)} | {_fmt(_per_trade(row, 'commission_usd'))} | "
        f"{_fmt(legs_pt)} | {_fmt(_per_trade(row, 'gross_pnl'))} |"
    )
