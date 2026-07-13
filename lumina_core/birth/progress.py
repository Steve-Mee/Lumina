"""Birth progress file writer (SSOT for UI polling)."""

from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from lumina_core.birth.stage_scorecard import SCORECARD_PRESERVE_KEYS, enrich_progress_scorecard

_PHASES_NO_STAGES_PRESERVE = frozenset({"stage_stalled", "curriculum_learning"})


def read_birth_progress(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    # Canonical only (legacy first_boot read kept in first_boot_progress.py + callers for compat)
    path = root / "state" / "lumina_birth_progress.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    return {}


_STAGE_BLOCKER_PRESERVE_KEYS: frozenset[str] = frozenset(
    {"stage_blocker_metric", "stage_blocker_value", "pass_reason"}
)


def merge_birth_progress_extra(*parts: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge progress extra dicts with last-wins semantics.

    Never pass multiple ``**dict`` unpacks with overlapping keys to
    ``write_birth_progress`` — PEP 448 raises TypeError. Merge here first.
    """
    merged: dict[str, Any] = {}
    for part in parts:
        if part:
            merged.update(part)
    return merged


def _atomic_write_text(path: Path, encoded: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(encoded, encoding="utf-8")
    os.replace(tmp_path, path)


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
    new_stage = extra.get("curriculum_stage")
    prev_stage = prev.get("curriculum_stage")
    stage_changed = (
        new_stage is not None
        and prev_stage is not None
        and str(new_stage).strip() != str(prev_stage).strip()
    )
    _OOS_PRESERVE_KEYS: frozenset[str] = frozenset(
        {
            "oos_metrics",
            "failure_reasons",
            "remediation_attempt",
            "remediation_max",
            "data_manifest",
            "retryable",
            "certificate_ok",
            "runway_phase",
            "micro_oos_probe",
            "birth_exit_winrate",
        }
    )
    for key in SCORECARD_PRESERVE_KEYS:
        if (
            key == "stages_passed"
            and str(phase).strip().lower() in _PHASES_NO_STAGES_PRESERVE
            and key not in extra
        ):
            continue
        if stage_changed and key in _STAGE_BLOCKER_PRESERVE_KEYS:
            continue
        if key not in extra and key in prev:
            payload[key] = prev[key]
    for key in _OOS_PRESERVE_KEYS:
        if key not in extra and key in prev:
            payload[key] = prev[key]
    payload.update(extra)
    payload = enrich_progress_scorecard(payload)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    # Write canonical only. Legacy dual write removed for radical simplicity.
    path = root / "state" / "lumina_birth_progress.json"
    try:
        _atomic_write_text(path, encoded)
    except OSError:
        pass
