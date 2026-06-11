#!/usr/bin/env python3
"""Phase 3 D1 golden path: verify one-human-20-min audits on genuine D4 campaign ctxs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lumina_core.audit.d1_golden_path import run_d1_golden_path_verify  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3 D1 live campaign golden path verify")
    parser.add_argument("--min-verified", type=int, default=3)
    parser.add_argument("--sample-unsafe", type=int, default=2)
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()

    result = run_d1_golden_path_verify(
        repo_root=ROOT,
        min_verified=args.min_verified,
        sample_unsafe=args.sample_unsafe,
        export=not args.no_export,
    )
    print("D1_GOLDEN_PATH_OK" if result.get("ok") else "D1_GOLDEN_PATH_FAIL")
    print(f"verified={result.get('verified_count')}/{result.get('sample_size')} discover_smoke={result.get('discover_smoke_ok')}")
    if result.get("manifest_path"):
        print(f"manifest={result['manifest_path']}")
    if not result.get("ok"):
        for r in result.get("results", []):
            if not r.get("ok"):
                print(f"  FAIL {r.get('ctx')}: {r.get('issues')}")
        if result.get("error"):
            print(f"  error: {result['error']}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
