#!/usr/bin/env python3
"""T5: Perfect Birth operator campaign report (checklist + gaps; never declares).

Usage:
  python scripts/validation/perfect_birth_campaign.py
  python scripts/validation/perfect_birth_campaign.py --workspace .
  python scripts/validation/perfect_birth_campaign.py --json

Declare (separate, conjunction-only):
  python scripts/validation/declare_perfect_birth.py --dry-run
  python scripts/validation/declare_perfect_birth.py
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
    parser = argparse.ArgumentParser(description="Perfect Birth campaign report (T5)")
    parser.add_argument("--workspace", type=str, default="", help="Workspace root")
    parser.add_argument("--json", action="store_true", help="Full JSON")
    args = parser.parse_args(argv)

    from lumina_core.birth.perfect_birth_gate import build_perfect_birth_campaign_report

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    report = build_perfect_birth_campaign_report(workspace)

    if args.json:
        # Drop nested status dump noise if huge sources — keep full by default for ops
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"perfect_birth_campaign unlock={report.get('unlock_valid')} "
            f"would_pass={report.get('would_pass')} "
            f"checklist={report.get('checklist_passed')}/{report.get('checklist_total')}"
        )
        for item in report.get("checklist") or []:
            mark = "OK" if item.get("ok") else ".."
            print(
                f"  [{mark}] {item.get('id')}: actual={item.get('actual')} "
                f"target={item.get('target')}"
            )
        actions = report.get("ordered_actions") or []
        if actions:
            print("  next_actions:")
            for i, a in enumerate(actions[:8], 1):
                print(f"    {i}. {a}")
        print(f"  next_step: {report.get('next_step')}")
        cmds = report.get("commands") or {}
        print(f"  declare: {cmds.get('declare')}")

    # Exit 0 only when fully unlocked (flag+evidence); campaign progress uses soft non-zero otherwise
    return 0 if report.get("unlock_valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
