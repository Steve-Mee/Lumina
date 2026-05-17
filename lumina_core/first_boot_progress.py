"""Canonical first-boot progress and target-trade resolvers."""

from __future__ import annotations

from typing import Any, Mapping

from lumina_core.first_boot_ui import FIRST_BOOT_DEFAULT_TRADES, normalize_first_boot_training_trades

_STAGE_ALIASES: dict[str, str] = {
    # BIRTH ENGINE 2026-05-17
    "birth_phase": "training_running",
    "birth_running": "training_running",
    "birth_detected": "detected",
    "birth_loading_data": "loading_data",
    "birth_paused": "paused",
    "birth_completed": "completed",
    "birth_completed_waiting_user_action": "completed_waiting_user_action",
}


def resolve_first_boot_completed_trades(progress: Mapping[str, Any] | None) -> int:
    src = progress or {}
    for key in ("trades_done", "trades", "sim_trades", "cumulative_trades", "total_trades", "birth_trades"):
        value = src.get(key)
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if count >= 0:
            return count
    return 0


def resolve_first_boot_target_trades(config_payload: Mapping[str, Any] | None) -> int:
    cfg = config_payload or {}
    first_boot = cfg.get("first_boot")
    if not isinstance(first_boot, Mapping):
        return FIRST_BOOT_DEFAULT_TRADES
    return normalize_first_boot_training_trades(first_boot.get("training_trades", FIRST_BOOT_DEFAULT_TRADES))


def resolve_first_boot_target_from_progress(progress: Mapping[str, Any] | None) -> int:
    src = progress or {}
    raw = src.get("target_trades")
    try:
        target = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, target)


def resolve_first_boot_stage(progress: Mapping[str, Any] | None) -> str:
    src = progress or {}
    stage = str(src.get("stage", "")).strip().lower()
    if not stage:
        return stage
    return _STAGE_ALIASES.get(stage, stage)


def resolve_ppo_training_progress(
    progress: Mapping[str, Any] | None,
    *,
    default_total_steps: int = 300_000,
) -> tuple[int, int, float | None]:
    src = progress or {}
    # BIRTH ENGINE 2026-05-17
    raw_steps = src.get("ppo_steps", src.get("policy_steps", src.get("birth_ppo_steps", 0)))
    raw_total = src.get("ppo_timesteps_total", default_total_steps)
    try:
        steps = max(0, int(raw_steps or 0))
    except (TypeError, ValueError):
        steps = 0
    try:
        total_steps = max(1, int(raw_total or default_total_steps))
    except (TypeError, ValueError):
        total_steps = max(1, int(default_total_steps))
    raw_pct = src.get("ppo_progress_pct")
    try:
        pct = float(raw_pct)
        if pct < 0 or pct > 100:
            pct = (float(steps) / float(total_steps)) * 100.0
    except (TypeError, ValueError):
        pct = (float(steps) / float(total_steps)) * 100.0 if total_steps > 0 else None
    return steps, total_steps, (round(pct, 2) if pct is not None else None)


def resolve_ppo_progress_interval(config_payload: Mapping[str, Any] | None) -> int:
    cfg = config_payload or {}
    first_boot = cfg.get("first_boot")
    raw = None
    if isinstance(first_boot, Mapping):
        raw = first_boot.get("ppo_progress_interval")
    try:
        value = int(raw or 10_000)
    except (TypeError, ValueError):
        value = 10_000
    return max(1_000, min(100_000, value))
