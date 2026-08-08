#!/usr/bin/env python3
"""T10: Capital-path Event Bus lineage inventory / typed-contract gate.

Usage:
  python scripts/validation/capital_bus_lineage_gate.py
  python scripts/validation/capital_bus_lineage_gate.py --json
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
    parser = argparse.ArgumentParser(description="Capital bus lineage gate (T10)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.risk.capital_bus_lineage import evaluate_capital_bus_lineage_gate

    result = evaluate_capital_bus_lineage_gate()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    else:
        print(f"capital_bus_lineage_gate ok={result.get('ok')} reason={result.get('reason')}")
        print(f"  {result.get('message')}")
        inv = result.get("inventory") or {}
        print(f"  core_topics: {', '.join(inv.get('core_topics') or [])}")
        print(f"  registered: {', '.join(inv.get('typed_models_registered') or [])}")
        if inv.get("typed_models_missing"):
            print(f"  missing: {', '.join(inv.get('typed_models_missing') or [])}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
