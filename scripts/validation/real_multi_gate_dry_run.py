#!/usr/bin/env python3
"""T3: REAL multi-gate dry-run (read-only — never arms REAL capital).

Usage:
  python scripts/validation/real_multi_gate_dry_run.py
  python scripts/validation/real_multi_gate_dry_run.py --workspace .
  python scripts/validation/real_multi_gate_dry_run.py --json

Exit 0 if safety invariants hold (twin cannot bypass, DNA needs human).
Exit 1 if an invariant is broken.
Note: exit 0 does NOT mean ready_for_real_capital — check JSON field.
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
    parser = argparse.ArgumentParser(description="REAL multi-gate dry-run (T3, read-only)")
    parser.add_argument("--workspace", type=str, default="", help="Workspace root")
    parser.add_argument("--json", action="store_true", help="Full JSON output")
    args = parser.parse_args(argv)

    from lumina_core.risk.real_multi_gate import run_real_multi_gate_dry_run

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    result = run_real_multi_gate_dry_run(workspace)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"real_multi_gate_dry_run ok={result.get('ok')} "
            f"ready_for_real={result.get('ready_for_real_capital')} "
            f"mode_switch_allowed={result.get('mode_switch_allowed')}"
        )
        inv = result.get("invariants") or {}
        for k, v in inv.items():
            print(f"  invariant {k}={v}")
        blockers = result.get("blockers") or []
        if blockers:
            print("  blockers:")
            for b in blockers[:12]:
                print(f"    - {b}")
        ap = result.get("aperture_coverage") or {}
        print(
            f"  aperture soft: reason={ap.get('reason')} "
            f"sample_size={ap.get('sample_size')} coverage={ap.get('lineage_coverage_pct')}"
        )
        print(f"  policy: {result.get('policy', {}).get('next_step_if_not_ready')}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
