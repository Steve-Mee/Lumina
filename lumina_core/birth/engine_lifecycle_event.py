"""Paused result / event curriculum / reload (M5 engine_lifecycle extract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator
from lumina_core.birth.progress import read_birth_progress, write_birth_progress

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineLifecycleEventMixin:
    def _paused_result(self) -> dict[str, Any]:
        from lumina_core.birth.starship_birth import build_pause_ssot_payload, write_pause_ssot

        write_birth_progress(
            self.workspace_root,
            stage="paused",
            phase="paused",
            message="Birth Phase gepauzeerd door gebruiker.",
            progress_pct=min(
                99.0,
                float(self.cumulative_trades) / max(1.0, float(self.birth_config.trade_budget_cap)) * 100.0,
            ),
            cumulative_trades=self.cumulative_trades,
            target_trades=self.birth_config.trade_budget_cap,
            birth_start_time=self.birth_start_time,
            ppo_steps=self.ppo_steps,
            user_initiated_stop=True,
        )
        # Starship A5: keep lumina_birth_progress + first_boot_progress identical.
        current = read_birth_progress(self.workspace_root)
        write_pause_ssot(
            self.workspace_root,
            build_pause_ssot_payload(
                progress=current,
                message="Birth Phase gepauzeerd door gebruiker.",
            ),
        )
        return {"status": "paused", "total_trades": self.cumulative_trades, "ppo_steps": self.ppo_steps}

    def get_curriculum_orchestrator(self) -> CurriculumOrchestrator | None:
        """Return the thin event-only CurriculumOrchestrator if wired."""
        return self._curriculum_orchestrator

    def start_event_driven_curriculum(self, *, stages: list[str] | None = None) -> str | None:
        """Kick off curriculum using the thin orchestrator + dedicated handlers.

        Returns curriculum_id or None if not wired.
        All heavy logic (plateau, phoenix, intra, remediation) executes inside
        handlers that publish strict events back to the orchestrator.
        """
        orch = self._curriculum_orchestrator
        if orch is None:
            return None
        from lumina_core.birth.curriculum import ordered_stages as _ordered

        stage_list = stages or [s.value for s in _ordered()]
        cap = int(getattr(self.birth_config, "trade_budget_cap", 1_000_000))
        practice = False
        try:
            cid = orch.start_curriculum(
                stages=stage_list,
                target_trades_cap=cap,
                practice_mode=practice,
            )
            return cid
        except Exception as exc:
            logger.exception("event-driven curriculum start failed: %s", exc)
            return None

    def reload_birth_config(self) -> None:
        """Hot-reload birth_v2 section from workspace config.yaml."""
        self.birth_config = load_birth_v2_config(self.workspace_root)
        if self._birth_handler_registry is not None:
            self._birth_handler_registry.sync_birth_cfg(
                self.birth_config.curriculum,
                self.birth_config.reward,
            )
        if self._birth_bus_client is not None:
            self._birth_bus_client.cfg = self.birth_config.curriculum
        logger.info("birth.config.hot_reload workspace=%s", self.workspace_root)

