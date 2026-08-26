#!/usr/bin/env python3
"""T8/R3: Phase 2 SIM campaign ops — observe → shadow → apply (never REAL).

Usage:
  python scripts/validation/phase2_shadow_campaign.py
  python scripts/validation/phase2_shadow_campaign.py --json
  python scripts/validation/phase2_shadow_campaign.py --observe   # pre-PB audit only
  python scripts/validation/phase2_shadow_campaign.py --enable    # after Perfect Birth
  python scripts/validation/phase2_shadow_campaign.py --enable --scaffold   # lab only
  python scripts/validation/phase2_shadow_campaign.py --promote-apply
  python scripts/validation/phase2_shadow_campaign.py --disable
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
    parser = argparse.ArgumentParser(description="Phase 2 SIM shadow campaign (T8/R3)")
    parser.add_argument("--workspace", type=str, default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--observe",
        action="store_true",
        help="R3: enable observe campaign (propose+audit only; no PB required)",
    )
    parser.add_argument("--enable", action="store_true", help="Enable shadow after PB unlock")
    parser.add_argument(
        "--scaffold",
        action="store_true",
        help="Lab-only: allow enable without Perfect Birth (never production)",
    )
    parser.add_argument("--promote-apply", action="store_true", help="Shadow→SIM apply if evidence")
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.birth.phase2_autonomy.sim_campaign import (
        build_phase2_shadow_campaign_ops_report,
        disable_sim_campaign,
        enable_sim_observe_campaign,
        enable_sim_shadow_campaign,
        promote_sim_apply_campaign,
    )

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    action_result = None

    if args.disable:
        action_result = disable_sim_campaign(workspace)
    elif args.observe:
        action_result = enable_sim_observe_campaign(
            workspace,
            source="phase2_shadow_campaign_cli",
        )
    elif args.enable:
        action_result = enable_sim_shadow_campaign(
            workspace,
            allow_sim_scaffold=bool(args.scaffold),
            source="phase2_shadow_campaign_cli",
        )
    elif args.promote_apply:
        action_result = promote_sim_apply_campaign(workspace)

    report = build_phase2_shadow_campaign_ops_report(workspace)
    if action_result is not None:
        report["action_result"] = action_result

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"phase2_shadow_campaign unlock={report.get('perfect_birth_unlock')} "
            f"active={report.get('campaign_active')} mode={report.get('mode')} "
            f"ok={report.get('ok')}"
        )
        for item in report.get("ladder") or []:
            mark = "OK" if item.get("ok") else ".."
            print(f"  [{mark}] {item.get('id')}: {item.get('title')}")
        if action_result is not None:
            print(f"  action_result: {json.dumps(action_result, ensure_ascii=True, default=str)[:400]}")
        actions = report.get("ordered_actions") or []
        if actions:
            print("  next_actions:")
            for i, a in enumerate(actions[:6], 1):
                print(f"    {i}. {a}")
        print(f"  next_step: {report.get('next_step')}")
        print("  policy: REAL apply forbidden; twin required for apply")

    if action_result is not None and action_result.get("ok") is False:
        return 1
    # Status-only: exit 0 when report built; unlock+active preferred for green CI optional
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
