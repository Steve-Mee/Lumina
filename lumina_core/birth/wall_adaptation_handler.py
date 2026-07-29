"""WallAdaptationHandler — EventBus owner for wall triggers and autonomous recovery."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import BirthStageRolloutSnapshot
from lumina_core.birth.adaptation_recovery_engine import (
    AdaptationApplyResult,
    apply_adaptation_to_state,
    plan_adaptive_recovery,
    plan_never_stop_recovery,
)
from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.birth_bus_choreography import (
    TOPIC_SNAPSHOT,
    publish_adaptation_applied,
    publish_recovery_metrics,
    publish_wall_triggered,
)
from lumina_core.birth.birth_bus_serde import deserialize_learning_snapshot
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.wall_trigger_engine import evaluate_wall_trigger

logger = logging.getLogger("lumina.birth.wall_adaptation_handler")


class WallAdaptationHandler:
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

    def _handle_wall_evaluate_trigger(
        self, cid: str, stage_name: str, ctx: dict[str, Any]
    ) -> None:
        from lumina_core.birth.phase2_autonomy.handler_hooks import phase2_wall_closed_loop

        stage = self._parse_stage(stage_name)
        phase2_meta, eval_cfg = phase2_wall_closed_loop(
            self._phase2,
            cfg=self.cfg,
            registry=self._registry,
            correlation_id=cid,
            stage_name=stage_name,
            ctx=ctx,
        )
        wr_stag = int(ctx.get("winrate_stagnation_count", 0))
        hold_stag = int(ctx.get("hold_stagnation_count", 0))
        raw_entropy = ctx.get("policy_entropy", None)
        policy_entropy: float | None
        try:
            policy_entropy = float(raw_entropy) if raw_entropy is not None else None
        except (TypeError, ValueError):
            policy_entropy = None
        result = evaluate_wall_trigger(
            stage=stage,
            stage_trades=int(ctx.get("stage_trades", 0)),
            stage_wins=int(ctx.get("stage_wins", 0)),
            required=int(ctx.get("required", 0)),
            hold_ratio=float(ctx.get("hold_ratio", 0.0)),
            constitution_violations=int(ctx.get("constitution_violations", 0)),
            range_flat_ratio=float(ctx.get("range_flat_ratio", 0.0)),
            range_round_trips=int(ctx.get("range_round_trips", 0)),
            range_total_signals=int(ctx.get("range_total_signals", 0)),
            elapsed_stage_sec=float(ctx.get("elapsed_stage_sec", 0.0)),
            winrate_stagnation_count=wr_stag,
            hold_stagnation_count=hold_stag,
            wall_budget_exhausted=bool(ctx.get("wall_budget_exhausted", False)),
            allow_provisional=bool(ctx.get("allow_provisional", False)),
            failure_key=str(ctx.get("failure_key", "")),
            force=bool(ctx.get("force", False)),
            low_velocity_attempts=int(ctx.get("low_velocity_attempts", 0)),
            last_adaptation_stage_trades=int(
                ctx.get("last_adaptation_stage_trades", self.state.last_adaptation_stage_trades)
            ),
            rollouts_since_last_adaptation=int(
                ctx.get(
                    "rollouts_since_last_adaptation",
                    getattr(self.state, "rollouts_since_last_adaptation", 0),
                )
                or 0
            ),
            cfg=eval_cfg,
            policy_entropy=policy_entropy,
            ppo_steps=int(ctx.get("ppo_steps", 0) or 0),
        )
        if not result.triggered:
            self._set_response(cid, "trigger", None)
            if phase2_meta:
                self._set_response(cid, "phase2_wall", phase2_meta)
            return

        self.state.wall_triggers_total += 1
        force_flag = bool(ctx.get("force", False))
        if force_flag or result.trigger_type in {
            "trades_beyond_gate",
            "constitution_stall",
            "adaptation_stuck",
        }:
            logger.info(
                "birth.wall.force trigger=%s stage=%s trades=%s required=%s total_triggers=%s",
                result.trigger_type,
                stage_name,
                int(ctx.get("stage_trades", 0)),
                int(ctx.get("required", 0)),
                self.state.wall_triggers_total,
            )
        publish_wall_triggered(
            self.bus,
            producer="birth.wall_adaptation_handler",
            correlation_id=cid,
            stage=stage_name,
            trigger_type=result.trigger_type,
            failure_key=result.failure_key,
            elapsed_stage_sec=float(ctx.get("elapsed_stage_sec", 0.0)),
            constitution_violations=int(ctx.get("constitution_violations", 0)),
            context={
                "pending": result.pending,
                "constitution_blocked": result.constitution_blocked,
                "phase2_wall": phase2_meta or {},
            },
        )
        self._set_response(
            cid,
            "trigger",
            {
                "triggered": True,
                "trigger_type": result.trigger_type,
                "failure_key": result.failure_key,
                "pending": result.pending,
                "constitution_blocked": result.constitution_blocked,
                "phase2_wall": phase2_meta or {},
            },
        )

    def _meta_plan_from_ctx(self, ctx: dict[str, Any]) -> Any | None:
        if not self.cfg.meta_controller_enabled or self._registry is None:
            return None
        snap_raw = ctx.get("snapshot")
        if not isinstance(snap_raw, dict):
            return None
        snap = deserialize_learning_snapshot(snap_raw)
        controller = self._registry.meta.controller
        return controller.decide_adaptation(
            snap,
            winrate=float(ctx.get("winrate", 0.0)),
            escalation_level=int(ctx.get("escalation_level", self.state.escalation_level)),
            adaptation_tier=int(ctx.get("adaptation_tier", self.state.adaptation_tier)),
            retries_this_stage=int(
                ctx.get("retries_this_stage", self.state.retries_this_stage)
            ),
            original_rollout_chunk=int(ctx.get("original_rollout_chunk", 0)),
            failure_key=str(ctx.get("failure_key", "")),
        )

    def _handle_adaptation_try_recovery(
        self, cid: str, stage_name: str, ctx: dict[str, Any]
    ) -> None:
        trigger_type = str(ctx.get("trigger_type", "certified_stall"))
        failure_key = str(ctx.get("failure_key", ""))
        stage_trades = int(ctx.get("stage_trades", 0))
        required = int(ctx.get("required", 0))
        current_winrate = float(ctx.get("current_winrate", 0.0))
        winrate_history = list(ctx.get("winrate_history", []))
        original_rollout_chunk = int(ctx.get("original_rollout_chunk", 0))
        rollout_chunk_trades = int(ctx.get("rollout_chunk_trades", 0))
        trade_budget_remaining = int(ctx.get("trade_budget_remaining", 0))
        terminal_blocked = bool(ctx.get("terminal_blocked", False))
        constitution_blocked = bool(ctx.get("constitution_blocked", False))
        learning_health = str(ctx.get("learning_health", "flat"))

        meta_plan = self._meta_plan_from_ctx(ctx)
        plan = plan_adaptive_recovery(
            cfg=self.cfg,
            state=self.state,
            failure_key=failure_key,
            trigger_type=trigger_type,
            stage_trades=stage_trades,
            required=required,
            current_winrate=current_winrate,
            winrate_history=winrate_history,
            original_rollout_chunk=original_rollout_chunk,
            rollout_chunk_trades=rollout_chunk_trades,
            trade_budget_remaining=trade_budget_remaining,
            terminal_blocked=terminal_blocked,
            constitution_blocked=constitution_blocked,
            meta_plan=meta_plan,
            learning_health=learning_health,
        )
        from lumina_core.birth.phase2_autonomy.handler_hooks import phase2_recovery_closed_loop

        phase2_extra = phase2_recovery_closed_loop(
            self._phase2,
            wall_state=self.state,
            registry=self._registry,
            cfg=self.cfg,
            correlation_id=cid,
            stage_name=stage_name,
            ctx=ctx,
            learning_health=learning_health,
            stage_trades=stage_trades,
            required=required,
            constitution_blocked=constitution_blocked,
        )
        self._publish_apply_result(
            cid,
            stage_name,
            plan,
            current_winrate=current_winrate,
            stage_trades=stage_trades,
            original_rollout_chunk=original_rollout_chunk,
            phase2_extra=phase2_extra,
        )

    def _handle_never_stop(self, cid: str, stage_name: str, ctx: dict[str, Any]) -> None:
        from lumina_core.birth.phase2_autonomy.handler_hooks import phase2_recovery_closed_loop

        plan = plan_never_stop_recovery(
            cfg=self.cfg,
            state=self.state,
            failure_key=str(ctx.get("failure_key", "")),
            rollout_chunk_trades=int(ctx.get("rollout_chunk_trades", 0)),
            terminal_blocked=bool(ctx.get("terminal_blocked", False)),
        )
        phase2_extra = phase2_recovery_closed_loop(
            self._phase2,
            wall_state=self.state,
            registry=self._registry,
            cfg=self.cfg,
            correlation_id=cid,
            stage_name=stage_name,
            ctx=ctx,
            learning_health=str(ctx.get("learning_health", "flat")),
            stage_trades=int(ctx.get("stage_trades", 0)),
            required=int(ctx.get("required", 0)),
            constitution_blocked=bool(ctx.get("constitution_blocked", False)),
        )
        self._publish_apply_result(
            cid,
            stage_name,
            plan,
            current_winrate=float(ctx.get("current_winrate", 0.0)),
            stage_trades=int(ctx.get("stage_trades", 0)),
            original_rollout_chunk=int(ctx.get("original_rollout_chunk", 0)),
            phase2_extra=phase2_extra,
        )

    def _publish_apply_result(
        self,
        cid: str,
        stage_name: str,
        plan: AdaptationApplyResult,
        *,
        current_winrate: float = 0.0,
        stage_trades: int = 0,
        original_rollout_chunk: int = 0,
        phase2_extra: dict[str, Any] | None = None,
    ) -> None:
        from lumina_core.birth.phase2_autonomy.handler_hooks import merge_instance_spawn_flags

        p2 = phase2_extra or {}
        spawn_plateau, spawn_phoenix = merge_instance_spawn_flags(
            plan_spawn_plateau=bool(plan.spawn_plateau),
            plan_spawn_phoenix=bool(plan.spawn_phoenix_reset),
            phase2_extra=p2,
        )

        if not plan.applied or plan.decision is None:
            self._set_response(
                cid,
                "adaptation",
                {
                    "applied": False,
                    "dispatch": plan.dispatch,
                    "phase2": p2,
                    "spawn_plateau": spawn_plateau,
                    "spawn_phoenix_reset": spawn_phoenix,
                },
            )
            return

        for key, value in plan.state_delta.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)

        updated, chunk = apply_adaptation_to_state(
            self.state,
            plan.decision,
            failure_key=plan.decision.reason,
            current_winrate=current_winrate,
            stage_trades=stage_trades,
            max_escalation_level=int(self.cfg.max_escalation_level),
            max_adaptation_tiers=int(self.cfg.max_adaptation_tiers),
            max_stage_retries=int(self.cfg.max_stage_retries),
            exploration_chunk_size=int(self.cfg.exploration_chunk_size),
            original_rollout_chunk=original_rollout_chunk,
        )
        self.state = updated

        patch_dict: dict[str, Any] = {}
        if plan.parameter_patch is not None:
            patch_dict = {
                k: v
                for k, v in asdict(plan.parameter_patch).items()
                if v is not None
            }
            if plan.parameter_patch.winrate_trend_window is not None:
                self.state.effective_winrate_window = int(
                    plan.parameter_patch.winrate_trend_window
                )
            if plan.parameter_patch.reward_trend_window is not None:
                self.state.effective_reward_window = int(
                    plan.parameter_patch.reward_trend_window
                )

        # Phase 2 param apply may already have mutated state; surface in patch_dict
        param_raw = p2.get("param")
        param_info: dict[str, Any] = param_raw if isinstance(param_raw, dict) else {}
        param_payload = param_info.get("apply_payload")
        if param_info.get("applied") and isinstance(param_payload, dict):
            changes = param_payload.get("changes") or {}
            if isinstance(changes, dict) and changes:
                patch_dict = {**patch_dict, **{f"phase2_{k}": v for k, v in changes.items()}}

        publish_adaptation_applied(
            self.bus,
            producer="birth.wall_adaptation_handler",
            correlation_id=cid,
            stage=stage_name,
            reason=plan.decision.reason,
            adaptation_tier=self.state.adaptation_tier,
            retries_this_stage=self.state.retries_this_stage,
            chunk_target=chunk,
            escalation_level=self.state.escalation_level,
            parameter_patch=patch_dict,
            dispatch=plan.dispatch,
            recovery_kind=plan.recovery_kind,
        )
        publish_recovery_metrics(
            self.bus,
            producer="birth.wall_adaptation_handler",
            correlation_id=cid,
            stage=stage_name,
            wall_triggers_total=self.state.wall_triggers_total,
            recovery_attempts=self.state.recovery_attempts,
            recovery_successes=self.state.recovery_successes,
            autonomous_recovery_rate_pct=self.state.autonomous_recovery_rate_pct,
        )

        self._set_response(
            cid,
            "adaptation",
            {
                "applied": True,
                "dispatch": plan.dispatch,
                "recovery_kind": plan.recovery_kind,
                "decision": {
                    "should_retry": plan.decision.should_retry,
                    "reason": plan.decision.reason,
                    "new_chunk_target": chunk,
                    "escalation_increase": plan.decision.escalation_increase,
                    "log_message": plan.decision.log_message,
                },
                "mine": plan.mine,
                "mine_aggressive": plan.mine_aggressive,
                "expand_data": plan.expand_data,
                "spawn_plateau": spawn_plateau,
                "spawn_phoenix_reset": spawn_phoenix,
                "parameter_patch": patch_dict,
                "state": self.state.to_metrics(),
                "phase2": p2,
            },
        )

    def _handle_apply_result(self, cid: str, ctx: dict[str, Any]) -> None:
        """Executor confirms I/O side-effects completed (metrics only)."""
        if bool(ctx.get("success", False)):
            self._set_response(cid, "ok", True)
        else:
            self._set_response(cid, "ok", False)


__all__ = ["WallAdaptationHandler"]
