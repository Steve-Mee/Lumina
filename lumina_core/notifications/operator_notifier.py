"""Unified operator notification facade (ADR-0028)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.notifications.attention_events import AttentionEvent
from lumina_core.notifications.attention_notifier import notify_attention
from lumina_core.notifications.maturation_events import maturation_milestone_event
from lumina_core.notifications.milestone_events import MilestoneEvent
from lumina_core.notifications.milestone_notifier import notify_milestone

logger = logging.getLogger("lumina.notifications.operator")

_MATRIX_DEFAULTS: dict[str, bool] = {
    "maturation": True,
    "birth_milestones": True,
    "birth_attention": True,
    "real_safety": True,
    "evolution": True,
    "ops": True,
}

_CATEGORY_MATRIX_KEY: dict[str, str] = {
    "birth": "birth_attention",
    "real": "real_safety",
    "evolution": "evolution",
    "ops": "ops",
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_matrix() -> dict[str, bool]:
    tg_cfg = ConfigLoader.section("telegram", default={})
    tg_cfg = tg_cfg if isinstance(tg_cfg, dict) else {}
    raw = tg_cfg.get("notification_matrix")
    matrix = dict(_MATRIX_DEFAULTS)
    if isinstance(raw, dict):
        for key, default in _MATRIX_DEFAULTS.items():
            if key in raw:
                matrix[key] = _coerce_bool(raw[key], default)
    return matrix


def _matrix_enabled(key: str) -> bool:
    return _load_matrix().get(key, _MATRIX_DEFAULTS.get(key, True))


def notify_maturation(
    milestone_id: str,
    *,
    workspace_root: Path | str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Send maturation ladder milestone to Telegram (idempotent via MilestoneNotifier)."""
    if not _matrix_enabled("maturation"):
        logger.debug("operator.maturation_disabled id=%s", milestone_id)
        return False
    try:
        event = maturation_milestone_event(milestone_id, metadata=metadata)
        return notify_milestone(event, workspace_root=workspace_root)
    except Exception as exc:
        logger.debug("operator.maturation_notify_failed id=%s err=%s", milestone_id, exc)
        return False


def notify_problem(
    event: AttentionEvent,
    *,
    workspace_root: Path | str | None = None,
) -> bool:
    """Route attention event to Telegram with matrix category gating."""
    key = _CATEGORY_MATRIX_KEY.get(event.category.value, "birth_attention")
    if not _matrix_enabled(key):
        logger.debug("operator.attention_disabled category=%s reason=%s", event.category.value, event.reason_code)
        return False
    try:
        return notify_attention(event, workspace_root=workspace_root)
    except Exception as exc:
        logger.debug("operator.attention_notify_failed reason=%s err=%s", event.reason_code, exc)
        return False


def notify_birth_milestone(
    event: MilestoneEvent,
    *,
    workspace_root: Path | str | None = None,
) -> bool:
    """Birth milestone with matrix gating."""
    if not _matrix_enabled("birth_milestones"):
        return False
    return notify_milestone(event, workspace_root=workspace_root)
