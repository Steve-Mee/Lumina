"""Distilled P2 data manifest: sha256s, ranges, rolls, gaps. No raw bars."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lumina_research.cycles.data import LoadedTape
from lumina_research.cycles.gaps import KNOWN_GAPS
from lumina_research.cycles.holdout import P2_HOLDOUT_START_UTC
from lumina_research.cycles.rolls import NT8_ROLL_DATES
from lumina_research.cycles.seal import CSV_SHA256, ZIP_SHA256, file_sha256
from lumina_research.validation.audit import utc_now_iso

MANIFEST_PATH = Path("data/research/manifest.json")


def write_data_manifest(
    tapes: tuple[LoadedTape, ...],
    *,
    repo_root: Path,
    dropped: dict[str, int],
) -> Path:
    instruments: dict[str, object] = {}
    for tape in tapes:
        source = file_sha256(tape.path) if tape.path.is_file() else ""
        instruments[tape.instrument] = {
            "path": f"$LUMINA_RESEARCH_DATA_DIR/{tape.instrument}/{tape.bar_size}/{tape.path.name}",
            "bar_size": tape.bar_size,
            "n_bars": len(tape.bars),
            "first_utc": _iso(tape.bars[0].ts_ns) if tape.bars else "",
            "last_utc": _iso(tape.bars[-1].ts_ns) if tape.bars else "",
            "file_sha256": source,
            "expected_csv_sha256": CSV_SHA256.get(tape.instrument, ""),
            "zip_sha256": ZIP_SHA256.get(tape.instrument, ""),
            "dropped_gap_bars": int(dropped.get(tape.instrument, 0)),
        }
    body = {
        "generated_at": utc_now_iso(),
        "holdout_start_utc": P2_HOLDOUT_START_UTC.isoformat(),
        "conventions": {
            "continuous": "unadjusted",
            "timestamps": "UTC bar-close",
            "bar_size": "1m",
            "rolls": "NinjaTrader 8",
            "gaps": "exclude, never fill",
        },
        "instruments": instruments,
        "nt8_rolls": [item.isoformat() for item in NT8_ROLL_DATES],
        "known_gaps": [
            {
                "instrument": item.instrument,
                "start_ns": item.start_ns,
                "end_ns": item.end_ns,
                "reason": item.reason,
            }
            for item in KNOWN_GAPS
        ],
        "note": "Raw CSVs are not in git. Load via $LUMINA_RESEARCH_DATA_DIR.",
    }
    path = repo_root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _iso(ts_ns: int) -> str:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()
