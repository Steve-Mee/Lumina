#!/usr/bin/env python3
"""T2: Capital aperture lineage coverage gate (H1 ≥95% when samples exist).

Usage:
  python scripts/validation/aperture_coverage_gate.py
  python scripts/validation/aperture_coverage_gate.py --workspace .
  python scripts/validation/aperture_coverage_gate.py --min-pct 95 --min-samples 10
  python scripts/validation/aperture_coverage_gate.py --phase2   # 80% band
  python scripts/validation/aperture_coverage_gate.py --json

Exit codes:
  0 — ok (including soft pass: no/thin samples)
  1 — hard fail: enough samples but coverage below target
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
    parser = argparse.ArgumentParser(description="Aperture lineage coverage gate (H1/T2)")
    parser.add_argument(
        "--workspace",
        type=str,
        default="",
        help="Workspace root (default: repo root)",
    )
    parser.add_argument(
        "--min-pct",
        type=float,
        default=None,
        help="Coverage target %% (default: 95 H1, or 80 with --phase2)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=10,
        help="Minimum sample_size before hard-failing on coverage (default 10)",
    )
    parser.add_argument(
        "--audit-limit",
        type=int,
        default=200,
        help="Max recent log rows to sample (default 200)",
    )
    parser.add_argument(
        "--phase2",
        action="store_true",
        help="Use phase2 coverage band (80%%) instead of H1 95%%",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    args = parser.parse_args(argv)

    from lumina_core.risk.capital_aperture_lineage import evaluate_aperture_coverage_gate

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    result = evaluate_aperture_coverage_gate(
        workspace_root=workspace,
        audit_limit=max(1, int(args.audit_limit)),
        min_coverage_pct=args.min_pct,
        min_sample_size=max(1, int(args.min_samples)),
        phase2_band=bool(args.phase2),
    )

    if args.json:
        # Avoid huge nested residual dump noise unless needed — keep snapshot compact
        out = dict(result)
        snap = out.get("snapshot")
        if isinstance(snap, dict):
            out["snapshot"] = {
                k: snap[k]
                for k in (
                    "schema",
                    "audit_source",
                    "sample_size",
                    "with_decision_context_id",
                    "without_decision_context_id",
                    "lineage_coverage_pct",
                    "target_coverage_pct",
                    "coverage_meets_h1_goal",
                    "coverage_meets_phase2_goal",
                    "generated_at",
                )
                if k in snap
            }
        print(json.dumps(out, indent=2, ensure_ascii=True))
    else:
        print(
            f"aperture_coverage_gate ok={result.get('ok')} "
            f"soft_pass={result.get('soft_pass')} reason={result.get('reason')}"
        )
        print(f"  {result.get('message')}")
        print(
            f"  sample_size={result.get('sample_size')} "
            f"coverage={result.get('lineage_coverage_pct')}% "
            f"target={result.get('target_coverage_pct')}%"
        )
        snap = result.get("snapshot") or {}
        if snap.get("audit_source"):
            print(f"  source={snap.get('audit_source')}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
