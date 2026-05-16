from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


_TRAINING_ACTIVE_STAGES = {
    "detected",
    "loading_data",
    "training_running",
    "pipeline_boot",
    "historical_loaded",
    "synthetic_top_up",
    "parallel_simulation",
    "ppo_training",
    "deferred_calendar",
}


@dataclass(frozen=True, slots=True)
class RuntimeSessionState:
    session_kind: str
    session_active: bool
    training_target_applicable: bool
    last_activity_ts: str | None
    activity_stale: bool


def _parse_iso(ts_raw: Any) -> datetime | None:
    text = str(ts_raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def resolve_runtime_session_state(
    *,
    first_boot_stage: str,
    process_alive: bool,
    current_mode: str,
    first_boot_timestamp: str | None = None,
    stale_after_seconds: int = 180,
) -> RuntimeSessionState:
    stage = str(first_boot_stage or "").strip().lower()
    mode = str(current_mode or "").strip().lower()
    stage_training = stage in _TRAINING_ACTIVE_STAGES
    is_live_mode = mode in {"sim", "sim_real_guard", "real"}

    if stage_training:
        session_kind = "first_boot_training"
    elif process_alive and is_live_mode:
        session_kind = "live_execution"
    elif process_alive and mode == "paper":
        session_kind = "paper_execution"
    elif process_alive:
        session_kind = "execution"
    else:
        session_kind = "idle"

    session_active = session_kind != "idle"
    training_target_applicable = stage_training

    parsed_ts = _parse_iso(first_boot_timestamp)
    if parsed_ts is None:
        return RuntimeSessionState(
            session_kind=session_kind,
            session_active=session_active,
            training_target_applicable=training_target_applicable,
            last_activity_ts=None,
            activity_stale=not session_active,
        )
    age = (datetime.now(timezone.utc) - parsed_ts).total_seconds()
    return RuntimeSessionState(
        session_kind=session_kind,
        session_active=session_active,
        training_target_applicable=training_target_applicable,
        last_activity_ts=parsed_ts.isoformat(),
        activity_stale=age > max(30, int(stale_after_seconds)),
    )


def is_live_exposure_context(*, session_kind: str, current_mode: str, process_alive: bool) -> bool:
    mode = str(current_mode or "").strip().lower()
    kind = str(session_kind or "").strip().lower()
    if not process_alive:
        return False
    if kind in {"live_execution", "paper_execution", "execution"}:
        return mode in {"sim", "sim_real_guard", "real"}
    return False

