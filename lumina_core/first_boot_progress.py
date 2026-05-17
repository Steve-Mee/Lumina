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


def is_sim_trades_complete(progress: Mapping[str, Any] | None) -> bool:
    src = progress or {}
    if src.get("sim_trades_complete") is True:
        return True
    target = resolve_first_boot_target_from_progress(src)
    if target <= 0:
        return False
    return resolve_first_boot_completed_trades(src) >= target


def resolve_ppo_batch_progress(progress: Mapping[str, Any] | None) -> tuple[int, int, float | None]:
    src = progress or {}
    try:
        batch_steps = max(0, int(src.get("ppo_batch_steps", 0) or 0))
    except (TypeError, ValueError):
        batch_steps = 0
    try:
        batch_total = max(0, int(src.get("ppo_batch_total", 0) or 0))
    except (TypeError, ValueError):
        batch_total = 0
    if batch_total <= 0:
        return batch_steps, 0, None
    raw_pct = src.get("ppo_batch_progress_pct", src.get("ppo_progress_pct"))
    try:
        pct = float(raw_pct)
        if pct < 0 or pct > 100:
            pct = (float(batch_steps) / float(batch_total)) * 100.0
    except (TypeError, ValueError):
        pct = (float(batch_steps) / float(batch_total)) * 100.0
    return batch_steps, batch_total, round(pct, 2)


def resolve_ppo_training_progress(
    progress: Mapping[str, Any] | None,
    *,
    default_total_steps: int = 300_000,
) -> tuple[int, int, float | None]:
    src = progress or {}
    # BIRTH ENGINE 2026-05-17
    raw_cumulative = src.get(
        "ppo_steps_cumulative",
        src.get("ppo_steps", src.get("policy_steps", src.get("birth_ppo_steps", 0))),
    )
    raw_total = src.get("ppo_timesteps_planned_total", src.get("ppo_timesteps_total", default_total_steps))
    try:
        cumulative = max(0, int(raw_cumulative or 0))
    except (TypeError, ValueError):
        cumulative = 0
    batch_steps, batch_total, _ = resolve_ppo_batch_progress(src)
    display_steps = cumulative + (batch_steps if batch_total > 0 else 0)
    try:
        total_steps = max(1, int(raw_total or default_total_steps))
    except (TypeError, ValueError):
        total_steps = max(1, int(default_total_steps))
    if display_steps > 0 and total_steps > 0:
        pct = (float(display_steps) / float(total_steps)) * 100.0
    else:
        pct = None
    return display_steps, total_steps, (round(pct, 2) if pct is not None else None)


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
