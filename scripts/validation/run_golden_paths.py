from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "state" / "golden_path_baseline.json"
TEST_TARGETS = [
    "tests/test_trade_mode_golden_paths.py",
    "tests/test_order_path_regression.py",
]


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", *TEST_TARGETS]
    started = datetime.now(timezone.utc)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    ended = datetime.now(timezone.utc)

    payload = {
        "timestamp_utc": ended.isoformat(),
        "started_utc": started.isoformat(),
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "command": " ".join(cmd),
        "targets": TEST_TARGETS,
        "return_code": int(proc.returncode),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }

    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

    print(f"Golden path baseline written: {BASELINE_PATH}")
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
