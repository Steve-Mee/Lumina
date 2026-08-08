#!/usr/bin/env python3
"""ADR-0037 Phase 0: Self-play lab gate (shadow ranking only).

Usage:
  python scripts/validation/self_play_lab_gate.py
  python scripts/validation/self_play_lab_gate.py --fixture
  python scripts/validation/self_play_lab_gate.py --workspace . --json
  python scripts/validation/self_play_lab_gate.py --enable-lab
  python scripts/validation/self_play_lab_gate.py --no-pytest

Never places orders. Never mutates birth progress. Never REAL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_PYTEST = ["tests/birth/test_self_play_lab.py"]


def _load_progress(workspace: Path) -> dict[str, Any]:
    for name in ("lumina_birth_progress.json", "first_boot_progress.json"):
        path = workspace / "state" / name
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return raw if isinstance(raw, dict) else {}
            except Exception:
                return {}
    return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Self-play lab gate (ADR-0037 Phase 0)")
    parser.add_argument("--workspace", type=str, default="")
    parser.add_argument("--fixture", action="store_true", help="Rank offline fixture variants")
    parser.add_argument(
        "--enable-lab",
        action="store_true",
        help="Opt-in enabled=True for this report only (still no apply)",
    )
    parser.add_argument("--capital-mode", type=str, default="sim")
    parser.add_argument(
        "--ignore-progress",
        action="store_true",
        help="Do not load workspace birth progress (pure fixture / ignore live freeze)",
    )
    parser.add_argument("--no-pytest", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.birth.self_play import SelfPlayLabConfig, build_self_play_lab_report

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    progress = {} if args.ignore_progress else _load_progress(workspace)
    cfg = SelfPlayLabConfig(
        enabled=bool(args.enable_lab),
        capital_mode_hint=str(args.capital_mode or "sim"),
        allow_apply=False,
    )
    report = build_self_play_lab_report(
        config=cfg,
        progress=progress,
        capital_mode=args.capital_mode,
        use_fixture=True,
    )

    result: dict[str, Any] = {
        "schema": "self_play_lab_gate_v1",
        "workspace": str(workspace),
        "report": report,
    }

    if not args.no_pytest:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *_PYTEST, "-q", "--tb=line"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        result["pytest"] = {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-800:],
        }
    else:
        result["pytest"] = {"ok": True, "skipped": True}

    result["ok"] = bool(result["pytest"].get("ok")) and bool(report.get("ok"))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"self_play_lab_gate ok={result['ok']} "
            f"enabled={report.get('enabled')} phase={report.get('phase')} "
            f"variants={report.get('variant_count')}"
        )
        gate = report.get("gate") or {}
        print(f"  gate.allowed={gate.get('allowed')} reason={gate.get('reason')}")
        ranked = report.get("ranked") or []
        if ranked:
            top = ranked[0]
            print(
                f"  top={top.get('variant_id')} "
                f"tournament_score={top.get('tournament_score')} "
                f"lift_ok={top.get('lift_ok')}"
            )
        residuals = report.get("operator_residuals") or []
        if residuals:
            print("  operator_residuals:")
            for r in residuals:
                print(f"    - {r}")
        for a in (report.get("ordered_actions") or [])[:4]:
            print(f"  action: {a}")
        if not args.no_pytest:
            print(f"  pytest ok={result['pytest'].get('ok')}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
