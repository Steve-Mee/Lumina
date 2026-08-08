#!/usr/bin/env python3
"""T9: Consolidated deep-audit regression pack (Tracks A–E + T1–T8 tooling).

Usage:
  python scripts/validation/run_deep_audit_gates.py
  python scripts/validation/run_deep_audit_gates.py --json
  python scripts/validation/run_deep_audit_gates.py --pytest-only
  python scripts/validation/run_deep_audit_gates.py --strict-ops   # fail if PB/phase2 not unlocked

Hard gate = unit/chaos pytest pack (must pass).
Soft ops = status CLIs (default: report only; do not fail empty campaigns).
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

# Safety-critical unit coverage for deep-audit tracks
_PYTEST_PATHS = [
    # Track A / T7 champion freeze
    "tests/birth/test_champion_freeze_recovery.py",
    "tests/test_birth_service_workspace.py::test_auto_resume_blocked_for_champion_freeze_even_when_autonomous",
    "tests/birth/test_starship_birth.py::test_hard_stop_training_after_swarm_reject",
    "tests/birth/test_starship_birth.py::test_hard_stop_implies_no_fresh_pool_training",
    # Track B Perfect Birth
    "tests/birth/test_perfect_birth_gate.py",
    # Track C Slice E boundaries
    "tests/birth/test_phase2_slice_e_boundaries.py",
    # Track D Twin
    "tests/evolution/test_twin_discipline.py",
    "tests/evolution/test_twin_mode_promotion_gate.py",
    "tests/risk/test_real_multi_gate.py",
    # Track E aperture + fabric
    "tests/risk/test_capital_aperture_lineage.py",
    "tests/broker/test_fabric_safe_mode_brain.py",
    "tests/broker/test_ninjatrader_guards.py::test_fabric_safe_mode_blocks_place_allows_cancel",
    "tests/broker/test_ninjatrader_guards.py::test_disconnect_blocks_orders_in_sim",
    # T4 recon
    "tests/engine/test_real_broker_recon_gate.py",
    # T8 phase2 campaign
    "tests/birth/test_phase2_sim_campaign.py",
    # T10 capital bus lineage
    "tests/risk/test_capital_bus_lineage.py",
]

def _run(cmd: list[str], *, timeout: int = 300) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "cmd": cmd,
        "stdout_tail": (proc.stdout or "")[-1200:],
        "stderr_tail": (proc.stderr or "")[-600:],
    }


def _run_pytest() -> dict[str, Any]:
    cmd = [sys.executable, "-m", "pytest", *_PYTEST_PATHS, "-q", "--tb=line"]
    return _run(cmd, timeout=600)


def _run_ops() -> dict[str, Any]:
    """Run ops CLIs. fabric_safe_mode uses full mock pytest — run gate without nested pytest skip."""
    out: dict[str, Any] = {}
    # Fabric gate includes its own pytest — use full mock gate
    out["fabric_safe_mode"] = _run(
        [sys.executable, "scripts/validation/fabric_safe_mode_gate.py"],
        timeout=180,
    )
    out["aperture_coverage"] = _run(
        [sys.executable, "scripts/validation/aperture_coverage_gate.py"]
    )
    out["real_multi_gate"] = _run(
        [sys.executable, "scripts/validation/real_multi_gate_dry_run.py"]
    )
    out["real_broker_recon"] = _run(
        [sys.executable, "scripts/validation/real_broker_recon_gate.py"]
    )
    # Soft campaign status (may exit 1 if not unlocked)
    out["perfect_birth_campaign"] = _run(
        [sys.executable, "scripts/validation/perfect_birth_campaign.py"]
    )
    out["twin_promote_ops"] = _run(
        [sys.executable, "scripts/validation/twin_promote_ops.py", "--isolated"]
    )
    out["twin_mode_ssot"] = _run(
        [sys.executable, "scripts/validation/twin_mode_ssot_audit.py"]
    )
    out["champion_freeze"] = _run(
        [sys.executable, "scripts/validation/champion_freeze_gate.py", "--no-pytest"]
    )
    out["phase2_shadow"] = _run(
        [sys.executable, "scripts/validation/phase2_shadow_campaign.py"]
    )
    out["capital_bus_lineage"] = _run(
        [sys.executable, "scripts/validation/capital_bus_lineage_gate.py"]
    )
    out["recovery_theater"] = _run(
        [sys.executable, "scripts/validation/recovery_theater_gate.py", "--no-pytest"]
    )
    out["self_play_lab"] = _run(
        [
            sys.executable,
            "scripts/validation/self_play_lab_gate.py",
            "--no-pytest",
            "--fixture",
            "--ignore-progress",
        ]
    )
    out["operator_residuals"] = _run(
        [sys.executable, "scripts/validation/operator_residuals_gate.py"]
    )
    return out


# Scripts that are soft-status (incomplete campaign is OK in CI)
_SOFT_OPS = frozenset(
    {
        "perfect_birth_campaign",
        "phase2_shadow",
        "twin_promote_ops",
        "champion_freeze",  # freeze may be active; report only
        "aperture_coverage",  # soft pass no samples
        "recovery_theater",
        "twin_mode_ssot",  # warn-level yaml seed issues reported; critical fails hard
        "self_play_lab",  # Phase 0 lab default-off; fixture ranking
        "operator_residuals",  # yellow/blocked human forks expected; red fails hard
    }
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deep-audit regression pack (T9)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pytest-only", action="store_true")
    parser.add_argument("--ops-only", action="store_true")
    parser.add_argument(
        "--strict-ops",
        action="store_true",
        help="Fail if soft ops scripts exit non-zero (e.g. PB not unlocked)",
    )
    args = parser.parse_args(argv)

    result: dict[str, Any] = {
        "schema": "deep_audit_gates_v1",
        "tracks": "A-E + T1-T8 tooling",
    }

    if not args.ops_only:
        result["pytest"] = _run_pytest()
    else:
        result["pytest"] = {"ok": True, "skipped": True}

    if not args.pytest_only:
        result["ops"] = _run_ops()
    else:
        result["ops"] = {"skipped": True}

    pytest_ok = bool(result["pytest"].get("ok"))
    ops = result.get("ops") or {}
    hard_ops_ok = True
    soft_ops_notes: list[str] = []
    if not ops.get("skipped"):
        for name, payload in ops.items():
            if not isinstance(payload, dict):
                continue
            if name in _SOFT_OPS:
                if not payload.get("ok"):
                    soft_ops_notes.append(f"{name}:rc={payload.get('returncode')}")
                if args.strict_ops and not payload.get("ok"):
                    hard_ops_ok = False
            else:
                if not payload.get("ok"):
                    hard_ops_ok = False

    result["soft_ops_notes"] = soft_ops_notes
    result["ok"] = pytest_ok and hard_ops_ok
    result["pytest_ok"] = pytest_ok
    result["hard_ops_ok"] = hard_ops_ok

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True, default=str))
    else:
        print(f"deep_audit_gates ok={result['ok']}")
        print(f"  pytest_ok={pytest_ok}")
        if not result["pytest"].get("skipped") and not pytest_ok:
            print(result["pytest"].get("stdout_tail") or "")
            print(result["pytest"].get("stderr_tail") or "")
        if not ops.get("skipped"):
            print("  ops:")
            for name, payload in ops.items():
                if not isinstance(payload, dict):
                    continue
                soft = "soft" if name in _SOFT_OPS else "hard"
                print(f"    [{soft}] {name}: ok={payload.get('ok')} rc={payload.get('returncode')}")
            if soft_ops_notes:
                print(f"  soft_ops_notes: {', '.join(soft_ops_notes)}")
        print(
            "  CI tip: python scripts/validation/run_deep_audit_gates.py "
            "(add --strict-ops only for full campaign green)"
        )

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
