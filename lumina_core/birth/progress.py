"""Birth progress file writer (SSOT for UI polling)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.stage_scorecard import SCORECARD_PRESERVE_KEYS, enrich_progress_scorecard

_PHASES_NO_STAGES_PRESERVE = frozenset({"stage_stalled", "curriculum_learning"})


def read_birth_progress(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    for rel in ("state/lumina_birth_progress.json", "state/first_boot_progress.json"):
        path = root / rel
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def write_birth_progress(
    workspace_root: Path | str,
    *,
    stage: str,
    phase: str,
    message: str,
    progress_pct: float,
    cumulative_trades: int = 0,
    target_trades: int = 0,
    ppo_steps: int = 0,
    birth_start_time: float = 0.0,
    **extra: Any,
) -> None:
    root = Path(workspace_root)
    prev = read_birth_progress(root)
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": str(stage).strip().lower(),
        "phase": str(phase).strip().lower(),
        "message": str(message),
        "target_trades": int(target_trades),
        "trades_done": int(cumulative_trades),
        "cumulative_trades": int(cumulative_trades),
        "total_trades": int(cumulative_trades),
        "ppo_steps": int(ppo_steps),
        "progress_pct": round(max(0.0, min(100.0, float(progress_pct))), 2),
        "elapsed_sec": round(max(0.0, time.time() - birth_start_time), 2) if birth_start_time > 0 else 0.0,
    }
    if birth_start_time > 0:
        payload["birth_start_time"] = float(birth_start_time)
    elif prev.get("birth_start_time"):
        payload["birth_start_time"] = float(prev["birth_start_time"])
    if prev.get("elapsed_sec") and birth_start_time <= 0:
        payload["elapsed_sec"] = prev.get("elapsed_sec", 0.0)
    for key in SCORECARD_PRESERVE_KEYS:
        if (
            key == "stages_passed"
            and str(phase).strip().lower() in _PHASES_NO_STAGES_PRESERVE
            and key not in extra
        ):
            continue
        if key not in extra and key in prev:
            payload[key] = prev[key]
    payload.update(extra)
    payload = enrich_progress_scorecard(payload)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    for rel in ("state/lumina_birth_progress.json", "state/first_boot_progress.json"):
        path = root / rel
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8")
        except OSError:
            pass
