from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.safety_gate
def test_headless_launcher_cli_honors_sim_mode_override(tmp_path: Path) -> None:
    summary_path = tmp_path / "launcher_summary.json"
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["LUMINA_HEADLESS_SUMMARY_PATH"] = str(summary_path)
    env.pop("LUMINA_MODE", None)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lumina_launcher",
            "--headless",
            "--mode=sim",
            "--duration=1m",
            "--broker=paper",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert summary_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["runtime"] == "headless"
    assert payload["mode"] == "sim"
    assert payload["broker_mode"] == "paper"
    assert payload["broker_status"] == "paper_ok"
    assert "SIM LEARNING MODE ACTIVE" in result.stdout