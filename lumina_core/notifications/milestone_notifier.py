"""Birth milestone notification dispatcher (ADR-0025)."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.config_loader import ConfigLoader
from lumina_core.notifications.milestone_events import (
    MilestoneEvent,
    milestone_ids_for_stage,
)
from lumina_core.notifications.telegram_notifier import TelegramNotifier

logger = logging.getLogger("lumina.notifications.milestone")

_INSTANCE: MilestoneNotifier | None = None
_INSTANCE_LOCK = threading.Lock()

_PHASE_MACRO_SEEDS: dict[str, tuple[str, ...]] = {
    "ticks_ready": ("history_loaded", "regime_map_ready"),
    "policy_init": ("history_loaded", "regime_map_ready"),
    "curriculum_stage": ("history_loaded", "regime_map_ready"),
    "curriculum_stage_complete": ("history_loaded", "regime_map_ready"),
    "curriculum_learning": ("history_loaded", "regime_map_ready"),
    "ppo_polish": (
        "history_loaded",
        "regime_map_ready",
        "curriculum_stage4_polish_passed",
        "refinement_started",
    ),
    "oos_evaluation": (
        "history_loaded",
        "regime_map_ready",
        "curriculum_stage4_polish_passed",
        "refinement_started",
    ),
    "certificate_remediation": (
        "history_loaded",
        "regime_map_ready",
        "curriculum_stage4_polish_passed",
        "refinement_started",
    ),
    "certificate_issued": (
        "history_loaded",
        "regime_map_ready",
        "curriculum_stage4_polish_passed",
        "refinement_started",
        "oos_evaluation_passed",
        "birth_certificate_issued",
    ),
    "completed": (
        "history_loaded",
        "regime_map_ready",
        "curriculum_stage4_polish_passed",
        "refinement_started",
        "oos_evaluation_passed",
        "birth_certificate_issued",
    ),
    "practice_completed": (
        "history_loaded",
        "regime_map_ready",
        "curriculum_stage4_polish_passed",
        "refinement_started",
        "practice_birth_completed",
    ),
}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class MilestoneNotifier:
    """Route positive birth milestones to Telegram with persistent idempotency."""

    def __init__(
        self,
        *,
        workspace_root: Path | str | None = None,
        telegram: TelegramNotifier | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        tg_cfg = ConfigLoader.section("telegram", default={})
        tg_cfg = tg_cfg if isinstance(tg_cfg, dict) else {}
        self._enabled = _coerce_bool(tg_cfg.get("milestone_alerts_enabled"), True)
        self._telegram = telegram or TelegramNotifier()
        self._lock = threading.RLock()
        self._state_path = self._workspace_root / "state" / "milestone_notified.json"

    def reset_notified(self) -> None:
        """Clear notified milestones for a fresh birth run."""
        with self._lock:
            self._save_notified(set())

    def notify(self, event: MilestoneEvent, *, workspace_root: Path | str | None = None) -> bool:
        if workspace_root is not None:
            self._workspace_root = Path(workspace_root)
            self._state_path = self._workspace_root / "state" / "milestone_notified.json"

        if not self._enabled:
            logger.debug("milestone.disabled id=%s", event.milestone_id)
            return False

        if self._is_notified(event.milestone_id):
            logger.debug("milestone.already_notified id=%s", event.milestone_id)
            return False

        ok = self._telegram.send_milestone_alert(event.title, event.telegram_body())
        if ok:
            self._record_notified(event.milestone_id)
            logger.info("milestone.sent id=%s title=%s", event.milestone_id, event.title)
        else:
            logger.warning("milestone.send_failed id=%s", event.milestone_id)
        return ok

    def seed_from_birth_state(
        self,
        *,
        stages_passed: list[str],
        phase: str,
        training_mode: str,
        workspace_root: Path | str | None = None,
    ) -> None:
        """Mark milestones as already notified on checkpoint resume (no Telegram send)."""
        if workspace_root is not None:
            self._workspace_root = Path(workspace_root)
            self._state_path = self._workspace_root / "state" / "milestone_notified.json"

        seeded: set[str] = {"birth_started"}
        phase_norm = str(phase or "").strip().lower()
        seeded.update(_PHASE_MACRO_SEEDS.get(phase_norm, ()))

        for stage in stages_passed:
            mid = milestone_ids_for_stage(stage)
            if mid:
                seeded.add(mid)

        if CurriculumStage.STAGE4_POLISH.value in stages_passed:
            seeded.add("curriculum_stage4_polish_passed")

        if str(training_mode).strip().lower() == "practice" and phase_norm == "practice_completed":
            seeded.add("practice_birth_completed")

        with self._lock:
            current = self._load_notified()
            current.update(seeded)
            self._save_notified(current)
        logger.info(
            "milestone.seeded count=%s phase=%s stages=%s",
            len(seeded),
            phase_norm,
            stages_passed,
        )

    def _load_notified(self) -> set[str]:
        if not self._state_path.is_file():
            return set()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                items = raw.get("notified", raw.get("milestones", []))
            elif isinstance(raw, list):
                items = raw
            else:
                items = []
            return {str(x) for x in items if x}
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return set()

    def _save_notified(self, notified: set[str]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"notified": sorted(notified)}
        self._state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def _is_notified(self, milestone_id: str) -> bool:
        with self._lock:
            return milestone_id in self._load_notified()

    def _record_notified(self, milestone_id: str) -> None:
        with self._lock:
            store = self._load_notified()
            store.add(milestone_id)
            self._save_notified(store)


def get_milestone_notifier(*, workspace_root: Path | str | None = None) -> MilestoneNotifier:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = MilestoneNotifier(workspace_root=workspace_root)
        elif workspace_root is not None:
            _INSTANCE._workspace_root = Path(workspace_root)
            _INSTANCE._state_path = _INSTANCE._workspace_root / "state" / "milestone_notified.json"
        return _INSTANCE


def notify_milestone(event: MilestoneEvent, *, workspace_root: Path | str | None = None) -> bool:
    return get_milestone_notifier(workspace_root=workspace_root).notify(event, workspace_root=workspace_root)


def seed_milestones_from_birth_state(
    *,
    stages_passed: list[str],
    phase: str,
    training_mode: str,
    workspace_root: Path | str | None = None,
) -> None:
    get_milestone_notifier(workspace_root=workspace_root).seed_from_birth_state(
        stages_passed=stages_passed,
        phase=phase,
        training_mode=training_mode,
        workspace_root=workspace_root,
    )


__all__ = [
    "MilestoneNotifier",
    "get_milestone_notifier",
    "notify_milestone",
    "seed_milestones_from_birth_state",
]
