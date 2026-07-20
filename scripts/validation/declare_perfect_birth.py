#!/usr/bin/env python3
"""Declare Perfect Birth unlock only after measurable conjunction (Slice C).

Usage:
  python scripts/validation/declare_perfect_birth.py
  python scripts/validation/declare_perfect_birth.py --json
  python scripts/validation/declare_perfect_birth.py --force   # audited override; prefer not

Writes:
  state/perfect_birth_complete.flag
  state/perfect_birth_complete.json   (evidence; passed=true required by Phase 2 gate)
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
    parser = argparse.ArgumentParser(description="Declare Perfect Birth (conjunction-gated)")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write flag even if KPIs fail (audited; not recommended)",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default="",
        help="Workspace root (default: cwd / repo root)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate only; do not write flag/evidence",
    )
    args = parser.parse_args(argv)

    from lumina_core.birth.config import load_birth_v2_config
    from lumina_core.birth.perfect_birth_gate import (
        PerfectBirthThresholds,
        declare_perfect_birth,
        evaluate_perfect_birth_conjunction,
        gather_perfect_birth_kpis,
    )

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    thr = PerfectBirthThresholds()
    try:
        thr = PerfectBirthThresholds.from_curriculum_cfg(
            load_birth_v2_config(workspace).curriculum
        )
    except Exception:
        pass

    kpis = gather_perfect_birth_kpis(workspace)
    if args.dry_run:
        result = evaluate_perfect_birth_conjunction(kpis, thresholds=thr)
        payload = result.to_dict()
        payload["dry_run"] = True
        if args.json:
            print(json.dumps(payload, ensure_ascii=True, indent=2))
        else:
            print(f"passed={result.passed} failures={result.failures}")
        return 0 if result.passed else 1

    payload = declare_perfect_birth(
        workspace,
        thresholds=thr,
        kpis=kpis,
        force=bool(args.force),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(
            f"declared={payload.get('declared')} passed={payload.get('passed')} "
            f"reason={payload.get('reason')}"
        )
        if payload.get("failures"):
            print("failures:", "; ".join(str(x) for x in payload["failures"][:8]))
        if payload.get("declared"):
            print("flag:", payload.get("flag_path"))
            print("evidence:", payload.get("evidence_path"))
    if payload.get("declared") and (payload.get("passed") or args.force):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
