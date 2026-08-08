#!/usr/bin/env python3
"""T6: Twin promote ops proof (shadow→assisted→full_auto; fail-closed).

Usage:
  python scripts/validation/twin_promote_ops.py
  python scripts/validation/twin_promote_ops.py --json
  python scripts/validation/twin_promote_ops.py --promote assisted   # gated only
  python scripts/validation/twin_promote_ops.py --capital-mode sim

Never forces full_auto under REAL capital. Never seeds mode from yaml alone.
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
    parser = argparse.ArgumentParser(description="Twin promote ops proof (T6)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--capital-mode",
        type=str,
        default="",
        help="Override capital_mode_hint for report (sim|birth|real)",
    )
    parser.add_argument(
        "--promote",
        type=str,
        default="",
        choices=["", "assisted", "full_auto", "advisory", "active"],
        help="Attempt gated promote if readiness allows (optional)",
    )
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Use tmp-less isolated controller from status only (no TwinTrainingService)",
    )
    args = parser.parse_args(argv)

    from lumina_core.evolution.twin_discipline import build_twin_promote_ops_report

    promote_result = None
    status = None
    controller = None

    if not args.isolated:
        try:
            from lumina_core.evolution.twin_training_service import TwinTrainingService

            svc = TwinTrainingService()
            if args.capital_mode and hasattr(svc.twin, "mode_controller"):
                svc.twin.mode_controller.set_capital_mode_hint(args.capital_mode)
            status = svc.mode_status()
            if args.promote:
                promote_result = svc.promote_mode(args.promote)
                status = svc.mode_status()
        except Exception as exc:
            status = {"mode": "shadow", "error": str(exc), "readiness": {}}
    else:
        from lumina_core.evolution.twin_mode_controller import TwinModeController

        controller = TwinModeController(initial_mode="shadow")
        if args.capital_mode:
            controller.set_capital_mode_hint(args.capital_mode)
        status = controller.status()
        if args.promote:
            promote_result = controller.try_promote(args.promote)
            status = controller.status()

    report = build_twin_promote_ops_report(
        mode_status=status,
        controller=controller,
        capital_mode=args.capital_mode or None,
    )
    if promote_result is not None:
        report["promote_attempt"] = promote_result

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"twin_promote_ops live_mode={report.get('live_mode')} "
            f"capital={report.get('capital_mode')} "
            f"authority={report.get('authority')}"
        )
        for item in report.get("ladder") or []:
            mark = "OK" if item.get("ok") else ".."
            print(f"  [{mark}] {item.get('id')}: {item.get('title')}")
        rd = report.get("readiness") or {}
        print(
            f"  ready.assisted={rd.get('assisted', {}).get('ready')} "
            f"ready.full_auto={rd.get('full_auto', {}).get('ready')} "
            f"capital_allows_full_auto={rd.get('full_auto', {}).get('capital_allows')}"
        )
        if promote_result is not None:
            print(
                f"  promote_attempt promoted={promote_result.get('promoted')} "
                f"reason={promote_result.get('reason')}"
            )
        actions = report.get("ordered_actions") or []
        if actions:
            print("  next_actions:")
            for i, a in enumerate(actions[:6], 1):
                print(f"    {i}. {a}")
        print(f"  next_step: {report.get('next_step')}")

    # Exit 0 when report built and (if promote requested) promote succeeded or skipped readiness
    if promote_result is not None and not promote_result.get("promoted"):
        # already_at_mode counts as success
        if promote_result.get("reason") != "already_at_mode":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
