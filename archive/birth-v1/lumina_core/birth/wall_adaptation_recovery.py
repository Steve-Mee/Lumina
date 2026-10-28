"""Wall adaptation recovery + apply publish (M5 extract)."""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from lumina_core.birth.adaptation_recovery_engine import (
    AdaptationApplyResult,
    apply_adaptation_to_state,
    plan_adaptive_recovery,
    plan_never_stop_recovery,
)
from lumina_core.birth.birth_bus_choreography import (
    publish_adaptation_applied,
    publish_recovery_metrics,
)
from lumina_core.birth.birth_bus_serde import deserialize_learning_snapshot

logger = logging.getLogger("lumina.birth.wall_adaptation_handler")


class WallAdaptationRecoveryMixin:
    """Recovery planning + adaptation apply publish."""

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



__all__ = ["WallAdaptationRecoveryMixin"]
