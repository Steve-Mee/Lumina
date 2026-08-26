#!/usr/bin/env python3
"""Print birth code fingerprint for the current interpreter/cwd.

Usage (from repo root):
  python scripts/birth_runtime_fingerprint.py
  python scripts/birth_runtime_fingerprint.py --compare-progress
  python scripts/birth_runtime_fingerprint.py --geometry-check
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


def _geometry_ordered_check() -> dict:
    """Prove loaded calibrate rejects shuffle macro (quality_geom_v4 plant law)."""
    from lumina_core.birth.birth_trade_geometry import (
        MACRO_STOP_THRESHOLD,
        calibrate_birth_stops,
        is_time_ordered,
    )

    ticks = []
    px = 5000.0
    for i in range(400):
        px += 1.0 if i % 2 == 0 else -0.8
        ticks.append(
            {
                "bar_index": i,
                "last": px,
                "close": px,
                "trend_atr_norm": 0.0003,
            }
        )
    shuffled = list(ticks)
    random.Random(7).shuffle(shuffled)
    g_c = calibrate_birth_stops(ticks, max_hold_bars=90)
    g_s = calibrate_birth_stops(shuffled, max_hold_bars=180)
    ok = (
        is_time_ordered(ticks)
        and not is_time_ordered(shuffled)
        and g_c.time_ordered
        and g_c.stop_pct < MACRO_STOP_THRESHOLD
        and (g_s.source != "move_distribution" or g_s.stop_pct < MACRO_STOP_THRESHOLD)
        and g_s.macro_rejected
    )
    return {
        "geometry_check_ok": bool(ok),
        "chrono_stop": round(float(g_c.stop_pct), 6),
        "chrono_source": g_c.source,
        "shuffle_stop": round(float(g_s.stop_pct), 6),
        "shuffle_source": g_s.source,
        "shuffle_macro_rejected": bool(g_s.macro_rejected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compare-progress",
        action="store_true",
        help="Compare this process fingerprint to state/lumina_birth_progress.json",
    )
    parser.add_argument(
        "--geometry-check",
        action="store_true",
        help="Run time-ordered geometry poison-shuffle self-test",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from lumina_core.birth.runtime_diagnostics import (
        collect_birth_code_fingerprint,
        log_birth_code_fingerprint,
        progress_diagnostic_fields,
    )

    fp = log_birth_code_fingerprint(reason="cli")
    payload = {**progress_diagnostic_fields(), "modules": fp.get("modules")}
    if args.geometry_check:
        payload["geometry_self_test"] = _geometry_ordered_check()
    print(json.dumps(payload, indent=2))

    if args.geometry_check and not payload["geometry_self_test"].get("geometry_check_ok"):
        print("GEOMETRY_CHECK_FAILED", file=sys.stderr)
        return 5

    if args.compare_progress:
        prog_path = root / "state" / "lumina_birth_progress.json"
        if not prog_path.is_file():
            print("NO_PROGRESS_FILE", prog_path, file=sys.stderr)
            return 2
        prog = json.loads(prog_path.read_text(encoding="utf-8"))
        live_fp = str(fp.get("birth_code_fingerprint") or "")
        prog_fp = str(prog.get("birth_code_fingerprint") or "")
        print("--- compare ---")
        print("cli_fingerprint ", live_fp)
        print("progress_fp     ", prog_fp or "(missing — birth writer not emitting diag)")
        print("cli_pid         ", fp.get("pid"))
        print("progress_pid    ", prog.get("birth_runtime_pid"))
        print("match           ", bool(prog_fp) and prog_fp == live_fp)
        print(
            "geometry_time_ordered",
            prog.get("geometry_time_ordered"),
            "stop",
            prog.get("birth_trade_stop_pct"),
            "src",
            prog.get("birth_trade_geometry_source"),
        )
        if not prog_fp:
            print(
                "HINT: progress missing birth_code_fingerprint → running birth "
                "process is not on quality_geom_v4 code (restart uvicorn/birth).",
                file=sys.stderr,
            )
            return 3
        if prog_fp != live_fp:
            print(
                "HINT: fingerprint mismatch → birth process loaded different files "
                "than this CLI (cwd/PYTHONPATH/old process).",
                file=sys.stderr,
            )
            return 4
        # Honesty gate on live progress geometry scale.
        try:
            stop = float(prog.get("birth_trade_stop_pct") or 0.0)
            if stop >= 0.005 and str(prog.get("birth_trade_geometry_source") or "") == "move_distribution":
                print(
                    "HINT: progress still shows macro move_distribution — restart + wipe "
                    "or frozen geometry not applied.",
                    file=sys.stderr,
                )
                return 6
        except (TypeError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
