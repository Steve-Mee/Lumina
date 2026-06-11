#!/usr/bin/env python3
"""
Phase 3 Track C close-out gate: D1 golden path + D5 scan + D6 self-score + core audit/dna tests.

Reproduces daily aperture forcing stack after Track C (D3 C1, D1, D5, D6) completion.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    print("RUN:", " ".join(cmd))
    r = subprocess.run(
        cmd,
        cwd=ROOT,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    print("EXIT", r.returncode)
    return r.returncode


def main() -> int:
    tests = [
        "tests/dna/test_invariants_d5.py",
        "tests/dna/test_capital_aperture_scan.py",
        "tests/dna/test_guardian_self_score.py",
        "tests/audit/test_d1_golden_path.py",
        "tests/audit/test_aperture_audit_artifact.py",
        "tests/audit/test_protocol_adherence.py",
    ]
    rc = run([sys.executable, "-m", "pytest", "-q", "--tb=line", *tests])
    if rc:
        return rc

    rc = run([sys.executable, str(ROOT / "scripts" / "phase3_d1_golden_path_verify.py")])
    if rc:
        return rc

    rc = run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dna_guardian" / "validate_dna.py"),
            "--report",
            "--d1-audits",
            "--strict-self-score",
        ]
    )
    if rc:
        return rc

    latest = ROOT / "project-dna" / "lumina" / "interfaces" / "export" / "dna_health_latest.json"
    if latest.exists():
        import json

        data = json.loads(latest.read_text(encoding="utf-8"))
        aperture = data.get("aperture") or {}
        gss = aperture.get("guardian_self_score") or {}
        score = float(gss.get("overall_score", 0))
        if score < 8.0:
            print(f"TRACK_C_GATE_FAIL: guardian_self_score {score} < 8.0 in dna_health_latest.json")
            return 1
        print(f"TRACK_C_GATE_OK self_score={score} status={gss.get('status')}")
    else:
        print("TRACK_C_GATE_WARN: dna_health_latest.json missing (run validate_dna --create-entry to export)")

    print("PHASE3_TRACK_C_GATE_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
