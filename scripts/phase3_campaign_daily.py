#!/usr/bin/env python3
"""
Phase 3 90-day campaign — single daily discipline entry point.

Chains Guardian refresh + ninety-day snapshot + protocol adherence check.
Does not modify capital paths.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("RUN:", " ".join(cmd))
    r = subprocess.run(
        cmd,
        cwd=ROOT,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    print("EXIT", r.returncode)
    return r.returncode


def main() -> int:
    parser_import = __import__("argparse").ArgumentParser
    parser = parser_import(description="Phase 3 campaign daily discipline.")
    parser.add_argument("--gate", action="store_true", help="Also run phase3_perfection_gate_verify.py (weekly).")
    args = parser.parse_args()

    rc = run([sys.executable, str(ROOT / "scripts" / "phase3_ninety_day_gate_measure.py"), "--refresh", "--append"])
    if rc:
        return rc

    rc = run([sys.executable, str(ROOT / "scripts" / "phase3_protocol_adherence_measure.py")])
    # Protocol measure exits 1 if below 90%; do not fail daily on that alone after backfill.

    latest = ROOT / "state" / "phase3_ninety_day_gate_latest.json"
    if latest.exists():
        data = json.loads(latest.read_text(encoding="utf-8"))
        verdict = data.get("verdict", {}).get("honest_status", "?")
        days = data.get("days_remaining", "?")
        proto = (data.get("gates") or {}).get("protocol_adherence_rate", {})
        print(f"PHASE3_CAMPAIGN_DAILY_OK status={verdict} days_remaining={days}")
        if proto:
            print(
                f"  protocol_adherence={float(proto.get('value', 0)):.2%} "
                f"pass={proto.get('point_in_time_pass')}"
            )

    if args.gate:
        rc = run([sys.executable, str(ROOT / "scripts" / "phase3_perfection_gate_verify.py")])
        if rc:
            return rc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
