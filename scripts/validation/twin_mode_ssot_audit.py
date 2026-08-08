#!/usr/bin/env python3
"""T15: Twin mode SSOT audit — config.yaml vs state file vs live controller.

Usage:
  python scripts/validation/twin_mode_ssot_audit.py
  python scripts/validation/twin_mode_ssot_audit.py --workspace .
  python scripts/validation/twin_mode_ssot_audit.py --live
  python scripts/validation/twin_mode_ssot_audit.py --json

Never promotes. Never forces full_auto from yaml.
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
    parser = argparse.ArgumentParser(description="Twin mode SSOT audit (T15)")
    parser.add_argument("--workspace", type=str, default="")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Probe TwinTrainingService / TwinModeController live mode",
    )
    parser.add_argument(
        "--capital-mode",
        type=str,
        default="",
        help="Override capital_mode_hint for audit",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Also fail on warn-level findings (yaml full_auto seed, auto_promote_fa)",
    )
    args = parser.parse_args(argv)

    from lumina_core.evolution.twin_mode_ssot_audit import build_twin_mode_ssot_audit

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    live_mode = None
    if args.live:
        try:
            from lumina_core.evolution.twin_training_service import TwinTrainingService

            svc = TwinTrainingService()
            if args.capital_mode and hasattr(svc.twin, "mode_controller"):
                svc.twin.mode_controller.set_capital_mode_hint(args.capital_mode)
            status = svc.mode_status() if hasattr(svc, "mode_status") else {}
            live_mode = str((status or {}).get("mode") or "shadow")
        except Exception as exc:
            live_mode = None
            if args.json:
                # still build report; attach error later
                pass
            else:
                print(f"  live probe failed: {exc}", file=sys.stderr)

    report = build_twin_mode_ssot_audit(
        workspace=workspace,
        live_mode=live_mode,
        capital_mode_hint=args.capital_mode or None,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"twin_mode_ssot_audit ok={report.get('ok')} "
            f"ssot={report.get('ssot_mode')} source={report.get('ssot_source')} "
            f"authority={report.get('authority')} capital={report.get('capital_mode')}"
        )
        cfg = report.get("config") or {}
        st = report.get("state") or {}
        print(
            f"  config.raw={cfg.get('raw')} config.canonical={cfg.get('canonical')} "
            f"full_auto_seed_ignored={cfg.get('full_auto_seed_ignored')}"
        )
        print(
            f"  state.exists={st.get('exists')} state.mode={st.get('mode')} "
            f"path={st.get('path')}"
        )
        live = report.get("live") or {}
        if live.get("provided"):
            print(f"  live.mode={live.get('mode')}")
        for f in report.get("findings") or []:
            if f.get("ok") and f.get("severity") == "info":
                continue
            mark = "OK" if f.get("ok") else f.get("severity", "!!").upper()
            print(f"  [{mark}] {f.get('id')}: {f.get('detail')}")
        actions = report.get("ordered_actions") or []
        if actions:
            print("  next_actions:")
            for i, a in enumerate(actions[:6], 1):
                print(f"    {i}. {a}")

    if args.strict and report.get("has_warnings"):
        return 1
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
