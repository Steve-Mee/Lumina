#!/usr/bin/env python3
"""T7: Champion freeze verification gate (unit pack + optional workspace progress).

Usage:
  python scripts/validation/champion_freeze_gate.py
  python scripts/validation/champion_freeze_gate.py --workspace .
  python scripts/validation/champion_freeze_gate.py --json

Proves auto-resume / resume_stalled cannot train under freeze (Track A tests).
Does not start Birth or wipe data.
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

_MOCK_PYTEST = [
    "tests/birth/test_champion_freeze_recovery.py",
    "tests/test_birth_service_workspace.py::test_auto_resume_blocked_for_champion_freeze_even_when_autonomous",
    "tests/birth/test_starship_birth.py::test_hard_stop_training_after_swarm_reject",
    "tests/birth/test_starship_birth.py::test_hard_stop_implies_no_fresh_pool_training",
]


def _run_pytest() -> dict[str, Any]:
    cmd = [sys.executable, "-m", "pytest", *_MOCK_PYTEST, "-q", "--tb=line"]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-1500:],
        "stderr_tail": (proc.stderr or "")[-800:],
        "tests": list(_MOCK_PYTEST),
    }


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


def _load_checkpoint_metrics(workspace: Path) -> dict[str, Any]:
    path = workspace / "state" / "lumina_birth_checkpoint.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        metrics = raw.get("stage_metrics")
        out = dict(metrics) if isinstance(metrics, dict) else {}
        if raw.get("phase"):
            out.setdefault("phase", raw.get("phase"))
        return out
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Champion freeze verification gate (T7)")
    parser.add_argument("--workspace", type=str, default="", help="Workspace for progress scan")
    parser.add_argument("--no-pytest", action="store_true", help="Skip unit pack")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from lumina_core.birth.starship_swarm_gates import build_champion_freeze_verification_report

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    progress = _load_progress(workspace)
    metrics = _load_checkpoint_metrics(workspace)
    report = build_champion_freeze_verification_report(
        progress=progress,
        checkpoint_metrics=metrics,
    )

    result: dict[str, Any] = {
        "schema": "champion_freeze_gate_v1",
        "workspace": str(workspace),
        "report": report,
    }

    if not args.no_pytest:
        result["pytest"] = _run_pytest()
    else:
        result["pytest"] = {"ok": True, "skipped": True}

    result["ok"] = bool(result["pytest"].get("ok")) and bool(report.get("ok"))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    else:
        print(f"champion_freeze_gate ok={result['ok']}")
        print(
            f"  freeze_active={report.get('freeze_active')} "
            f"rejected={report.get('rejected_no_lift')} "
            f"accepted={report.get('champion_accepted')}"
        )
        print(f"  message: {report.get('message')}")
        if not args.no_pytest:
            print(
                f"  pytest ok={result['pytest'].get('ok')} "
                f"rc={result['pytest'].get('returncode')}"
            )
            if not result["pytest"].get("ok"):
                print(result["pytest"].get("stdout_tail") or "")
        print("  blocked_paths:", ", ".join(report.get("operator_paths", {}).get("blocked") or []))
        print("  accept:", report.get("operator_paths", {}).get("accept"))

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
