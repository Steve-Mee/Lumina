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
from lumina_research.cycles.first_cycle import first_cycle_specs
from lumina_research.cycles.p2_cycle import clear_materialize_cache
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
) -> FourInstrumentResult:
    """MES/MNQ cost-fix, then ES/NQ. Sidecars and baseline reports stay untouched."""
    root = repo_root if repo_root is not None else _REPO
    work_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
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
        require_known_files=False,
    )
    comparison = write_comparison(
        report_dir=report_dir,
        mes_mnq=mes_mnq,
        es_nq=es_nq,
    )
    return FourInstrumentResult(mes_mnq=mes_mnq, es_nq=es_nq, comparison_path=comparison)


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
    lines.extend(
        [
            "",
            "### MNQ commission artefact",
            "",
            "1.1.0 skipped both commission sides on same-bar 16/8 round trips, so MNQ",
            "commission/trade sat near $0.08 while MES sat near $1.16. 1.2.0 charges",
            "both $0.94 sides ($1.88 RT) whenever a fill bar is in-position.",
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
    es_status = es_nq.report
    missing = ", ".join(es_status.data.missing) or "(none)"
    lines.extend(
        [
            "",
            "## ES/NQ data",
            "",
            f"- usable: `{es_status.data.usable}` stopped: `{es_status.stopped}` "
            f"reason: `{es_status.stop_reason or '(ran)'}`",
            f"- missing: {missing}",
            f"- planted_detected: `{es_status.planted_detected}` null_detected: `{es_status.null_detected}`",
            f"- needed if fail-closed: {ES_NQ_NEEDED}",
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
