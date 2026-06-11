#!/usr/bin/env python3
"""CLI: Protocol Adherence Rate for evolution/log meta entries."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lumina_core.audit.protocol_adherence import measure_protocol_adherence

LATEST_STATE = ROOT / "state" / "phase3_protocol_adherence_latest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure Protocol Adherence Rate.")
    parser.add_argument("--since", default="2026-05-31", help="ISO date filter (filename prefix).")
    parser.add_argument("--json", action="store_true", help="Print full JSON.")
    args = parser.parse_args()

    since = date.fromisoformat(args.since)
    result = measure_protocol_adherence(since=since, dna_root=ROOT / "project-dna" / "lumina")
    LATEST_STATE.parent.mkdir(parents=True, exist_ok=True)
    LATEST_STATE.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(
        f"PROTOCOL_ADHERENCE rate={result['rate']:.2%} "
        f"({result['adherent_entries']}/{result['total_entries']}) pass={result['pass']}"
    )
    if args.json:
        print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
