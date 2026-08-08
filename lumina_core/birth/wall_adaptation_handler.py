"""WallAdaptationHandler — EventBus owner for wall triggers and autonomous recovery.

M5: trigger evaluate in ``wall_adaptation_triggers``; recovery/publish in
``wall_adaptation_recovery``.
"""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import BirthStageRolloutSnapshot
from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.birth_bus_choreography import TOPIC_SNAPSHOT
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.wall_adaptation_recovery import WallAdaptationRecoveryMixin
from lumina_core.birth.wall_adaptation_triggers import WallAdaptationTriggerMixin

logger = logging.getLogger("lumina.birth.wall_adaptation_handler")


class WallAdaptationHandler(WallAdaptationTriggerMixin, WallAdaptationRecoveryMixin):
    """Subscribes to rollout snapshots; publishes wall triggers and adaptation facts."""

    def __init__(
        self,
        event_bus: EventBus,
        cfg: BirthCurriculumConfig,
        *,
        registry: Any | None = None,
        phase2_orchestrator: Any | None = None,
    ) -> None:
        if event_bus is None:
            raise ValueError("WallAdaptationHandler requires EventBus")
        self.bus = event_bus
        self.cfg = cfg
        self.state = WallAdaptationState(
            effective_winrate_window=int(cfg.winrate_trend_window),
            effective_reward_window=int(cfg.reward_trend_window),
        )
        self._registry = registry
        self._phase2 = phase2_orchestrator
        self._token: str | None = None

    def attach(self) -> str:
        if self._token is None:
            self._token = self.bus.subscribe(TOPIC_SNAPSHOT, self._on_snapshot)
        return self._token or ""

    def detach(self) -> None:
        if self._token:
            try:
                self.bus.unsubscribe(self._token)
            except Exception:
                pass
            self._token = None

    def _set_response(self, correlation_id: str, key: str, value: Any) -> None:
        if self._registry is not None and hasattr(self._registry, "set_response"):
            self._registry.set_response(correlation_id, key, value)

    def _on_snapshot(self, event: DomainEvent) -> None:
        try:
            snap_evt = event.typed_payload(BirthStageRolloutSnapshot)
        except Exception as exc:
            logger.warning("wall_adaptation_handler.snapshot_schema_violation: %s", exc)
            return

        cid = snap_evt.correlation_id
        signal = snap_evt.signal
        ctx = snap_evt.context

        try:
            if signal == "wall_restore_state":
                self.state = WallAdaptationState.from_metrics(
                    ctx.get("metrics"),
                    cfg=self.cfg,
                )
                self._set_response(cid, "ok", True)
            elif signal == "wall_evaluate_trigger":
                self._handle_wall_evaluate_trigger(cid, snap_evt.stage, ctx)
            elif signal == "adaptation_try_recovery":
                self._handle_adaptation_try_recovery(cid, snap_evt.stage, ctx)
            elif signal == "adaptation_never_stop":
                self._handle_never_stop(cid, snap_evt.stage, ctx)
            elif signal == "adaptation_metrics":
                self._set_response(cid, "metrics", self.state.to_metrics())
            elif signal == "adaptation_apply_result":
                self._handle_apply_result(cid, ctx)
        except Exception as exc:
            logger.warning(
                "wall_adaptation_handler.signal_failed signal=%s: %s", signal, exc
            )
            self._set_response(cid, "error", str(exc))

    def _parse_stage(self, stage_name: str) -> CurriculumStage:
        return CurriculumStage(str(stage_name))


__all__ = ["WallAdaptationHandler"]
