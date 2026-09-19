"""Birth progress file writer (SSOT for UI polling)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from lumina_core.birth.stage_scorecard import SCORECARD_PRESERVE_KEYS, enrich_progress_scorecard
from lumina_core.io.atomic_fs import atomic_write_text

_PHASES_NO_STAGES_PRESERVE = frozenset({"stage_stalled", "curriculum_learning"})

# Session clock is set by write args — never clobber with stale SCORECARD preserve.
_SESSION_CLOCK_KEYS: frozenset[str] = frozenset({"birth_start_time", "elapsed_sec"})
# Attention banners must not survive a new birth session (fresh birth_start_time).
_ATTENTION_PRESERVE_KEYS: frozenset[str] = frozenset(
    {
        "needs_attention",
        "attention_reason_code",
        "attention_summary",
        "attention_recommended_actions",
        "attention_notified_at",
    }
)
# Stall/freeze leftovers must not poison a new session (wipe → Activate).
_NEW_SESSION_DROP_KEYS: frozenset[str] = frozenset(
    {
        *_ATTENTION_PRESERVE_KEYS,
        "retryable",
        "auto_recovery_active",
        "is_advancing",
        "terminal_freeze",
        "terminal_stall_reason",
        "pass_reason",
        "stage_blocker_metric",
        "stage_blocker_value",
        "swarm_rejected_no_lift",
        "swarm_champion_accepted",
        "oos_sharpe",
        "oos_dd_pct",
    }
)


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
    atomic_write_text(path, encoded)


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

    prev_start = float(prev.get("birth_start_time") or 0.0)
    # New session when caller supplies a start that differs from the stored clock.
    new_session = bool(birth_start_time > 0 and (prev_start <= 0 or abs(float(birth_start_time) - prev_start) > 0.5))

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
            "oos_regime_breakdown",
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
        # Explicit session clock from this write must win over stale preserve.
        if key in _SESSION_CLOCK_KEYS and birth_start_time > 0:
            continue
        # Do not carry attention / freeze leftovers from a previous birth into a new session.
        if new_session and key in _NEW_SESSION_DROP_KEYS and key not in extra:
            continue
        if key not in extra and key in prev:
            payload[key] = prev[key]
    for key in _OOS_PRESERVE_KEYS:
        if new_session and key in _NEW_SESSION_DROP_KEYS and key not in extra:
            continue
        if key not in extra and key in prev:
            payload[key] = prev[key]
    payload.update(extra)
    # S5 HUD Sharpe/DD must not flicker to "—" when a later write omits or nulls them.
    if (
        not new_session
        and str(payload.get("curriculum_stage") or prev.get("curriculum_stage") or "")
        == "stage5_probe_handoff"
    ):
        for key in ("oos_sharpe", "oos_dd_pct"):
            if payload.get(key) is None and prev.get(key) is not None:
                payload[key] = prev[key]
    # Re-assert session clock after extra merge (extras must not smuggle old start).
    if birth_start_time > 0:
        payload["birth_start_time"] = float(birth_start_time)
        payload["elapsed_sec"] = round(max(0.0, time.time() - float(birth_start_time)), 2)
    # Never carry "user paused" into active training phases unless explicitly set.
    stage_l = str(payload.get("stage", "") or "").strip().lower()
    phase_l = str(payload.get("phase", "") or "").strip().lower()
    if stage_l not in {"paused", "interrupted"} and phase_l not in {"paused", "interrupted"}:
        if "user_initiated_stop" not in extra:
            payload["user_initiated_stop"] = False
    # Terminal stall must not keep live-training HUD fields (is_advancing / PPO sub-phase).
    # Those leftovers make the operator UI flip genesis ↔ mission ↔ stall overlay.
    _LIVE_SUB_PHASES = frozenset(
        {
            "ppo_training",
            "curriculum_learning",
            "curriculum_stage",
            "curriculum_research",
            "parallel_simulation",
            "policy_init",
            "ppo_polish",
            "loading_history",
            "loading_data",
            "ticks_ready",
            "enriching_regimes",
            "enriching_news",
        }
    )
    if stage_l == "stage_stalled" or phase_l == "stage_stalled":
        payload["is_advancing"] = False
        sub = str(payload.get("sub_phase") or "").strip().lower()
        if sub in _LIVE_SUB_PHASES or not sub:
            payload["sub_phase"] = "stage_stalled"
            payload["sub_phase_label"] = "Curriculum stalled"
        if payload.get("retryable") is False:
            payload["auto_recovery_active"] = False
        if int(payload.get("ppo_steps") or 0) == 0 and not new_session:
            prev_steps = int(prev.get("ppo_steps") or 0)
            if prev_steps > 0:
                payload["ppo_steps"] = prev_steps
        pass_reason = str(payload.get("pass_reason") or "")
        if "None" in pass_reason or "days=0" in pass_reason:
            # Hollow foundation_fail must not override an honest freeze/stall message.
            payload["pass_reason"] = None
    payload = enrich_progress_scorecard(payload)
    encoded = json.dumps(payload, ensure_ascii=True, indent=2)
    path = root / "state" / "lumina_birth_progress.json"
    try:
        _atomic_write_text(path, encoded)
    except OSError:
        pass
    # Pause SSOT still dual-writes first_boot. Mirror canonical so the two
    # files cannot disagree after resume (paused vs hervat split-brain).
    legacy = root / "state" / "first_boot_progress.json"
    if legacy.is_file():
        try:
            _atomic_write_text(legacy, encoded)
        except OSError:
            pass
