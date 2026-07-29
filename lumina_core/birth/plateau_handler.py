"""PlateauHandler — EventBus owner for plateau detection and escalation."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    BirthPlateauEntered,
    BirthPlateauEvolutionStep,
    BirthPlateauTrapDetected,
    BirthStageRolloutSnapshot,
)
from lumina_core.birth.birth_bus_choreography import TOPIC_SNAPSHOT
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    PlateauEnterContext,
    PlateauState,
    action_for_step,
    begin_evolution_step,
    detect_hold_trap,
    detect_over_trading_trap,
    enter_plateau,
    increment_evolution_rollout,
    record_evolution_outcome,
    record_forced_recovery,
    reset_plateau_for_new_cycle,
    revert_evolution_step_on_noop,
    should_enter_plateau,
    should_force_advance_evolution_step,
    should_trigger_plateau_evolution_step,
)

logger = logging.getLogger("lumina.birth.plateau_handler")


class PlateauHandler:
    """Subscribes to rollout snapshots; publishes plateau facts."""

    def __init__(
        self,
        event_bus: EventBus,
        cfg: BirthCurriculumConfig,
        *,
        registry: Any | None = None,
    ) -> None:
        if event_bus is None:
            raise ValueError("PlateauHandler requires EventBus")
        self.bus = event_bus
        self.cfg = cfg
        self.state = PlateauState()
        self._registry = registry
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
            logger.warning("plateau_handler.snapshot_schema_violation: %s", exc)
            return

        cid = snap_evt.correlation_id
        signal = snap_evt.signal
        ctx = snap_evt.context

        try:
            if signal == "plateau_restore_state":
                self.state = PlateauState.from_metrics(ctx.get("metrics"))
                self._set_response(cid, "ok", True)
            elif signal == "plateau_check_enter":
                skill_raw = ctx.get("skill_failing")
                skill_failing = None if skill_raw is None else bool(skill_raw)
                enter_ctx = PlateauEnterContext(
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                    required=int(ctx.get("required", 0)),
                    winrate_trend_slope=ctx.get("winrate_trend_slope"),
                    velocity_stall_attempts=int(ctx.get("velocity_stall_attempts", 0)),
                    meta_self_eval_phase=str(ctx.get("meta_self_eval_phase", "")),
                    pass_metric_target=float(ctx.get("pass_metric_target", 0.45) or 0.45),
                    plateau_quarantine_active=bool(ctx.get("plateau_quarantine_active", False)),
                    stage=snap_evt.stage,
                    wall_budget_exhausted=bool(ctx.get("wall_budget_exhausted", False)),
                    meta_learning_health=str(ctx.get("meta_learning_health", "") or ""),
                    skill_failing=skill_failing,
                )
                should = should_enter_plateau(enter_ctx, cfg=self.cfg)
                self._set_response(cid, "should_enter", should)
                if should:
                    trap = detect_over_trading_trap(
                        range_flat_ratio=float(ctx.get("range_flat_ratio", 0.0)),
                        range_round_trips=int(ctx.get("range_round_trips", 0)),
                        required=int(ctx.get("required", 0)),
                        velocity_stall=bool(ctx.get("velocity_stall", False)),
                        cfg=self.cfg,
                    )
                    trap_payload = BirthPlateauTrapDetected(
                        correlation_id=cid,
                        stage=snap_evt.stage,
                        detected=trap,
                        range_flat_ratio=float(ctx.get("range_flat_ratio", 0.0)),
                        range_round_trips=int(ctx.get("range_round_trips", 0)),
                    )
                    self.bus.publish(
                        topic="birth.plateau.trap.detected",
                        producer="birth.plateau_handler",
                        payload=trap_payload.model_dump(mode="json"),
                        metadata={"correlation_id": cid},
                    )
            elif signal == "plateau_enter":
                enter_plateau(
                    self.state,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                )
                winrate = float(ctx.get("stage_wins", 0)) / float(
                    max(1, int(ctx.get("stage_trades", 0)))
                )
                entered = BirthPlateauEntered(
                    stage=snap_evt.stage,
                    winrate=winrate,
                    trades_at_detection=int(ctx.get("stage_trades", 0)),
                    evolution_step=int(self.state.evolution_step),
                )
                self.bus.publish(
                    topic="birth.plateau.entered",
                    producer="birth.plateau_handler",
                    payload=entered.model_dump(mode="json"),
                    metadata={"correlation_id": cid},
                )
                self._set_response(cid, "entered", True)
            elif signal == "plateau_should_trigger_evolution":
                should = should_trigger_plateau_evolution_step(
                    self.state,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                    cfg=self.cfg,
                )
                self._set_response(cid, "should_trigger", should)
            elif signal == "plateau_begin_evolution_step":
                action = begin_evolution_step(
                    self.state,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                )
                step_payload = BirthPlateauEvolutionStep(
                    correlation_id=cid,
                    stage=snap_evt.stage,
                    evolution_step=int(self.state.evolution_step),
                    action=action.value if action else "none",
                    entered=True,
                )
                self.bus.publish(
                    topic="birth.plateau.evolution.step",
                    producer="birth.plateau_handler",
                    payload=step_payload.model_dump(mode="json"),
                    metadata={"correlation_id": cid},
                )
                self._set_response(
                    cid,
                    "action",
                    action.value if action else None,
                )
            elif signal == "plateau_increment_rollout":
                increment_evolution_rollout(self.state)
                self._set_response(cid, "ok", True)
            elif signal == "plateau_record_outcome":
                action_raw = ctx.get("action")
                action = (
                    EvolutionAction(str(action_raw)) if action_raw else None
                )
                record_evolution_outcome(
                    self.state,
                    action=action,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                    detail=str(ctx.get("detail", "")),
                    failure_key=str(ctx.get("failure_key", "")),
                    forced=bool(ctx.get("forced", False)),
                )
                self._set_response(cid, "ok", True)
            elif signal == "plateau_detect_hold_trap":
                trapped = detect_hold_trap(
                    hold_ratio=float(ctx.get("hold_ratio", 0.0)),
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    cfg=self.cfg,
                )
                self._set_response(cid, "hold_trap", trapped)
            elif signal == "plateau_detect_over_trading_trap":
                trapped = detect_over_trading_trap(
                    range_flat_ratio=float(ctx.get("range_flat_ratio", 0.0)),
                    range_round_trips=int(ctx.get("range_round_trips", 0)),
                    required=int(ctx.get("required", 0)),
                    velocity_stall=bool(ctx.get("velocity_stall", False)),
                    cfg=self.cfg,
                )
                trap_payload = BirthPlateauTrapDetected(
                    correlation_id=cid,
                    stage=snap_evt.stage,
                    detected=trapped,
                    range_flat_ratio=float(ctx.get("range_flat_ratio", 0.0)),
                    range_round_trips=int(ctx.get("range_round_trips", 0)),
                )
                self.bus.publish(
                    topic="birth.plateau.trap.detected",
                    producer="birth.plateau_handler",
                    payload=trap_payload.model_dump(mode="json"),
                    metadata={"correlation_id": cid},
                )
                self._set_response(cid, "over_trading_trap", trapped)
            elif signal == "plateau_should_force_advance":
                should = should_force_advance_evolution_step(
                    self.state,
                    cfg=self.cfg,
                    current_winrate=float(ctx.get("current_winrate", 0.0)),
                )
                self._set_response(cid, "force_advance", should)
            elif signal == "plateau_revert_noop":
                revert_evolution_step_on_noop(self.state)
                self._set_response(cid, "ok", True)
            elif signal == "plateau_record_forced_recovery":
                record_forced_recovery(self.state)
                self._set_response(cid, "ok", True)
            elif signal == "plateau_reset_cycle":
                reset_plateau_for_new_cycle(
                    self.state,
                    stage_trades=int(ctx.get("stage_trades", 0)),
                    stage_wins=int(ctx.get("stage_wins", 0)),
                )
                self._set_response(cid, "ok", True)
            elif signal == "plateau_action_for_step":
                action = action_for_step(int(ctx.get("step", 0)))
                self._set_response(
                    cid, "action", action.value if action else None
                )
            elif signal == "plateau_get_state":
                self._set_response(cid, "state", self.state.to_metrics())
            elif signal == "plateau_try_evolution":
                # Composite: check + begin + basic record. Returns action info for orchestrator.
                current_wr = float(ctx.get("current_winrate", 0.0))
                pass_target = float(ctx.get("pass_target", 0.0))
                should = should_trigger_plateau_evolution_step(
                    self.state,
                    cfg=self.cfg,
                    current_winrate=current_wr,
                    allow_start=bool(ctx.get("allow_start", True)),
                    pass_target=pass_target,
                )
                action = None
                if should:
                    action = begin_evolution_step(
                        self.state,
                        stage_trades=int(ctx.get("stage_trades", 0)),
                        stage_wins=int(ctx.get("stage_wins", 0)),
                    )
                    if action and action != EvolutionAction.TERMINAL:
                        self._set_response(cid, "evolution", {
                            "action": action.value if hasattr(action, "value") else str(action),
                            "applied": True,
                        })
                        return
                self._set_response(cid, "evolution", {"action": None, "applied": False})
            elif signal == "resolve_terminal_stall":
                from lumina_core.hybrid_quarantine import (
                    PLATEAU_TERMINAL_PASSTHROUGH,
                    handler_terminal_passthrough,
                    log_quarantine,
                )

                passthrough = handler_terminal_passthrough()
                log_quarantine(
                    PLATEAU_TERMINAL_PASSTHROUGH,
                    strict=not passthrough,
                    detail="resolve_terminal_stall",
                )
                if passthrough:
                    # Placeholder rich response; actual terminal shape built in recovery glue
                    self._set_response(cid, "terminal", {"handled": True})
                else:
                    pending = ctx if isinstance(ctx, dict) else {}
                    self._set_response(
                        cid,
                        "terminal",
                        {
                            "handled": False,
                            "reason": "handler_terminal_passthrough_disabled",
                            "pending": pending,
                        },
                    )
        except Exception as exc:
            logger.warning("plateau_handler.signal_failed signal=%s: %s", signal, exc)
            self._set_response(cid, "error", str(exc))


__all__ = ["PlateauHandler", "PlateauState"]
