"""Exact NT8 1m MES/MNQ file format and search locations for P2. Prep only; do not invent bars."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from lumina_research.cycles.holdout import HOLDOUT_MONTHS, HOLDOUT_MONTHS_MAX, HOLDOUT_MONTHS_MIN
from lumina_research.validation.audit import utc_now_iso

DATA_SPEC: Mapping[str, str] = {
    "universe_first": "MES and MNQ 1-minute bars; ES/NQ later after the micro cycle",
    "period": "recent 2-3 years through the export date",
    "holdout": (
        f"last {HOLDOUT_MONTHS} calendar months (allowed {HOLDOUT_MONTHS_MIN}-{HOLDOUT_MONTHS_MAX}) "
        "from the last bar; never used for template selection, first-cycle ranking, tuning, "
        "or Validation Gate calibration; evaluation-only accessor"
    ),
    "locations": (
        "$LUMINA_RESEARCH_DATA_DIR/{MES,MNQ}/1m/*.csv ; "
        "{--data-dir}/{MES,MNQ}/1m/*.csv ; "
        "{repo}/data/research/{MES,MNQ}/1m/*.csv"
    ),
    "filename_examples": "data/research/MES/1m/nt8_mes_1m.csv ; data/research/MNQ/1m/nt8_mnq_1m.csv",
    "format": "UTF-8 CSV with header timestamp,open,high,low,close,volume",
    "timestamp": "UTC ISO-8601 with offset, e.g. 2024-03-15T14:31:00+00:00 (convert NT8 CT → UTC)",
    "ohlc": "float CME MES/MNQ prices; high >= max(open,close,low); low <= min(open,close,high)",
    "volume": "float >= 0 (NT8 1m volume)",
    "nt8_instrument": "MES continuous or front month (e.g. MES 09-26); MNQ likewise",
    "nt8_bar": "1 Minute, CME Globex session (document RTH-only if that is what is exported)",
    "optional_vix": "data/research/VIX/1d/vix.csv columns timestamp,close for regime labels only",
    "code": "lumina_research.cycles.data.discover_data + lumina_research.cycles.holdout.access_bars",
}


def write_data_spec(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "phase5_p2_data_spec.md"
    lines = [
        "# Phase 5 P2 data spec (NT8 1m MES/MNQ)",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        "- status: prep only; this PR does not run the cycle on real bars",
        "",
    ]
    for key, value in DATA_SPEC.items():
        lines.append(f"- **{key}**: {value}")
    lines.extend(
        [
            "",
            "## CSV example",
            "",
            "```",
            "timestamp,open,high,low,close,volume",
            "2024-03-15T14:31:00+00:00,5212.25,5213.00,5211.75,5212.50,1842",
            "```",
            "",
            "## Holdout lock",
            "",
            "Call `access_bars(tape, purpose='gate'|'selection'|'tuning'|'calibration')` for train bars.",
            "Call `access_bars(tape, purpose='evaluation')` for the locked holdout.",
            "Any other purpose, a missing split, or a train bar with ts_ns inside the holdout raises `HoldoutLocked`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
