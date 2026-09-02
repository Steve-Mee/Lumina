#!/usr/bin/env python3
"""Append Stage-4 HUD snapshots while the certified-shadow plant runs."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRESS = ROOT / "workspace" / "state" / "lumina_birth_progress.json"
CHECKPOINT = ROOT / "workspace" / "state" / "lumina_birth_checkpoint.json"
OUT = ROOT / "s4_gate_b2_monitor.jsonl"
KEYS = (
    "timestamp",
    "curriculum_stage",
    "stage",
    "stage_trades",
    "stage_wins",
    "stage_policy_trades",
    "stage_plant_trades",
    "occupancy",
    "pass_reason",
    "stage_blocker_metric",
    "stage_blocker_value",
    "s3_inband_idle_armed",
    "s3_inband_explore",
    "s3_inband_hold_tax_steps",
    "participation_passthrough",
    "participation_force_open",
    "participation_force_hold",
    "participation_force_flat",
    "edge_vs_first_touch",
    "median_loss_r",
    "mean_r",
    "stages_passed",
    "phase",
    "status",
)


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def snapshot() -> dict:
    progress = _load(PROGRESS)
    ckpt = _load(CHECKPOINT)
    row: dict = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "curriculum_stage": ckpt.get("curriculum_stage") or progress.get("curriculum_stage"),
        "stages_passed": ckpt.get("stages_passed") or progress.get("stages_passed"),
    }
    for key in KEYS:
        if key in progress:
            row[key] = progress[key]
    scorecard = progress.get("stage_scorecard") if isinstance(progress.get("stage_scorecard"), dict) else {}
    for key in (
        "s3_inband_idle_armed",
        "s3_inband_explore",
        "s3_inband_hold_tax_steps",
        "participation_passthrough",
        "participation_force_open",
        "participation_inband_explore",
        "stage_policy_trades",
        "stage_plant_trades",
    ):
        if key in scorecard and key not in row:
            row[key] = scorecard[key]
    return row


def main() -> None:
    last = ""
    while True:
        row = snapshot()
        blob = json.dumps(row, default=str)
        sig = json.dumps(
            {
                k: row.get(k)
                for k in (
                    "curriculum_stage",
                    "stage_trades",
                    "stage_policy_trades",
                    "pass_reason",
                    "s3_inband_idle_armed",
                    "s3_inband_explore",
                    "occupancy",
                )
            },
            default=str,
        )
        if sig != last:
            OUT.parent.mkdir(parents=True, exist_ok=True)
            with OUT.open("a", encoding="utf-8") as fh:
                fh.write(blob + "\n")
            last = sig
            print(blob[:500], flush=True)
        time.sleep(5.0)


if __name__ == "__main__":
    main()
