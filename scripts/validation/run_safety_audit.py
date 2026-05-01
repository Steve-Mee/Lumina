"""Run Safety audits without interactive CI prompts.

Preferred path is `safety scan` with `SAFETY_API_KEY`.
If no key is available, we fall back to `safety check` on explicit
requirements files to keep scans non-interactive and deterministic.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str]) -> int:
    print(f"$ {' '.join(shlex.quote(part) for part in command)}")
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return completed.returncode


def main() -> int:
    safety_api_key = os.getenv("SAFETY_API_KEY", "").strip()
    if safety_api_key:
        report_path = REPO_ROOT / "state" / "safety_scan_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        print("SAFETY_API_KEY detected. Running `safety scan`.")
        return _run(
            [
                sys.executable,
                "-m",
                "safety",
                "--key",
                safety_api_key,
                "scan",
                "--target",
                str(REPO_ROOT),
                "--output",
                "screen",
                "--save-as",
                "json",
                str(report_path),
            ]
        )

    print("SAFETY_API_KEY not set. Falling back to `safety check` (non-interactive).")
    return _run(
        [
            sys.executable,
            "-m",
            "safety",
            "check",
            "-r",
            "requirements-core.txt",
            "-r",
            "requirements-trading.txt",
            "--full-report",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
