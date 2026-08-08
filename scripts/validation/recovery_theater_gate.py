#!/usr/bin/env python3
"""T11: Recovery theater residual gate — single active surface SSOT.

Usage:
  python scripts/validation/recovery_theater_gate.py
  python scripts/validation/recovery_theater_gate.py --workspace .
  python scripts/validation/recovery_theater_gate.py --json
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

_PYTEST = [
    "tests/birth/test_recovery_compress.py",
    "tests/birth/test_champion_freeze_recovery.py::test_champion_freeze_verification_report_frozen",
]


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
    parser = argparse.ArgumentParser(description="Recovery theater residual gate (T11)")
    parser.add_argument("--workspace", type=str, default="")
    parser.add_argument("--no-pytest", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.birth.recovery_compress import build_recovery_theater_ops_report

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    progress = _load_progress(workspace)
    report = build_recovery_theater_ops_report(progress)

    result: dict[str, Any] = {
        "schema": "recovery_theater_gate_v1",
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
        print(f"recovery_theater_gate ok={result['ok']}")
        print(
            f"  active={report.get('active')} next={report.get('next_action')} "
            f"theater={report.get('theater')}"
        )
        residual = report.get("residual_parallel_layers") or []
        if residual:
            print(f"  residual_layers (reported only): {', '.join(residual)}")
        flags = report.get("flags") or {}
        if flags.get("champion_freeze"):
            print("  champion_freeze=True → accept_champion_or_wipe only")
        if not args.no_pytest:
            print(f"  pytest ok={result['pytest'].get('ok')}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
