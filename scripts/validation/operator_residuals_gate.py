#!/usr/bin/env python3
"""OR1–OR6 operator residual board.

Aggregates Fabric, aperture, Perfect Birth, twin SSOT/promote, champion freeze,
and recovery theater status. Does not auto-declare PB, promote twin, or wipe birth.

Usage:
  python scripts/validation/operator_residuals_gate.py
  python scripts/validation/operator_residuals_gate.py --workspace .
  python scripts/validation/operator_residuals_gate.py --fabric-mock
  python scripts/validation/operator_residuals_gate.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OR1–OR6 operator residuals board")
    parser.add_argument("--workspace", type=str, default="")
    parser.add_argument(
        "--fabric-mock",
        action="store_true",
        help="Also run Fabric SAFE_MODE mock gate (slower)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.ops.operator_residuals import build_operator_residuals_report

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    report = build_operator_residuals_report(
        workspace=workspace,
        run_fabric_mock=bool(args.fabric_mock),
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    else:
        counts = report.get("counts") or {}
        print(
            f"operator_residuals ok={report.get('ok')} "
            f"green={counts.get('green')} yellow={counts.get('yellow')} "
            f"red={counts.get('red')} blocked={counts.get('blocked')}"
        )
        for item in report.get("items") or []:
            mark = {
                "green": "OK",
                "yellow": "..",
                "red": "FAIL",
                "blocked": "STOP",
            }.get(str(item.get("status")), "??")
            print(
                f"  [{mark}] {item.get('id')} {item.get('title')}: {item.get('summary')}"
            )
            for a in (item.get("next_actions") or [])[:2]:
                print(f"       → {a}")
        sp3 = report.get("sp3_sp4_readiness") or {}
        print(
            f"  SP3/SP4 ready={sp3.get('ready')} blockers={sp3.get('blockers') or []}"
        )
        sp = report.get("sp1_sp2_status") or {}
        print(f"  SP1: {sp.get('SP1')}")
        print(f"  SP2: {sp.get('SP2')}")
        print(f"  runbook: {report.get('commands', {}).get('runbook')}")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
