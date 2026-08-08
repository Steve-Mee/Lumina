"""Wall trigger evaluation handler (M5 extract)."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.birth.birth_bus_choreography import publish_wall_triggered
from lumina_core.birth.wall_trigger_engine import evaluate_wall_trigger

logger = logging.getLogger("lumina.birth.wall_adaptation_handler")


class WallAdaptationTriggerMixin:
    """Handle wall_evaluate_trigger bus signal."""

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


__all__ = ["WallAdaptationTriggerMixin"]
