"""Run Wave B PR-B1 targeted tests."""
from __future__ import annotations

import subprocess
import sys

ARGS = [
    sys.executable,
    "-m",
    "pytest",
    "tests/birth/",
    "-k",
    "engine or config or plateau_evolution or birth_engine",
    "-q",
    "--tb=line",
]

if __name__ == "__main__":
    raise SystemExit(subprocess.call(ARGS))
