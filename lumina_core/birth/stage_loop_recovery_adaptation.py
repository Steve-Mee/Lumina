"""Adaptive stall recovery, budget extend, never-stop (stage-loop recovery)."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.plateau_escalator import (
    adaptation_stuck_escape_allowed,
    can_force_never_stop_recovery,
    record_forced_recovery,
    remediation_is_exhausted,
    reset_plateau_for_new_cycle,
    should_block_plateau_recovery,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_recovery_adaptation")


class StageLoopRecoveryAdaptationMixin(StageLoopMixinBase):
    """Bus-driven adaptation recovery and trade-budget extension."""

    def _trade_budget_remaining(self) -> int:
        return max(0, int(self.effective_trade_budget_cap) - int(self.host.cumulative_trades))

    def _remediation_exhausted_now(self) -> bool:
        return remediation_is_exhausted(
            remediation_active=self.remediation_state.active,
            remediation_step=self.remediation_state.remediation_step,
            remediation_cycle=self.remediation_state.remediation_cycle,
            cfg=self.cur_cfg,
        )

    def _should_terminal_stall_in_adaptive(self) -> bool:
        """True when plateau recovery must stop (budget-gated never-stop)."""
        if self.plateau_state.active and should_block_plateau_recovery(
            self.plateau_state,
            cfg=self.cur_cfg,
            remediation_exhausted=self._remediation_exhausted_now(),
            trade_budget_remaining=self._trade_budget_remaining(),
            stage_trades=self.stage_trades,
            required=self.required,
        ):
            return True
        if self.plateau_state.active:
            return False
        if (
            self.data_exhausted
            and len(self.host.buffer) < 80
            and self.adaptation_tier >= self.cur_cfg.max_adaptation_tiers - 1
        ):
            return True
        return False

    def _maybe_extend_trade_budget(self) -> bool:
        if self.host.cumulative_trades < self.effective_trade_budget_cap:
            return False
        old_cap = self.effective_trade_budget_cap
        self.effective_trade_budget_cap = int(self.effective_trade_budget_cap * 1.25) + 1000
        logger.info(
            "birth.budget_extended old_cap=%s new_cap=%s cumulative_trades=%s tier=%s",
            old_cap,
            self.effective_trade_budget_cap,
            self.host.cumulative_trades,
            self.adaptation_tier,
        )
        return True

    def _sync_adaptation_from_bus(self) -> None:
        wa = self.bus.wall_adaptation_state
        self.retries_this_stage = int(wa.retries_this_stage)
        self.adaptation_tier = int(wa.adaptation_tier)
        self.escalation_level = int(wa.escalation_level)
        self.adaptation_history = list(wa.adaptation_history)
        self.last_adaptation_stage_trades = int(wa.last_adaptation_stage_trades)
        self.adaptation_stuck_escapes = int(wa.adaptation_stuck_escapes)

    def _apply_bus_adaptation_result(self, result: dict[str, Any]) -> bool:
        if not result.get("applied"):
            return False
        self._sync_adaptation_from_bus()
        decision = result.get("decision") if isinstance(result.get("decision"), dict) else {}
        chunk = decision.get("new_chunk_target")
        if chunk is not None:
            self.cur_cfg.rollout_chunk_trades = int(chunk)
        if result.get("mine"):
            self._mine_and_inject(aggressive=bool(result.get("mine_aggressive", False)))
        if result.get("expand_data"):
            self._maybe_expand_data()
        if result.get("spawn_plateau") and not self.plateau_state.active:
            self.bus.plateau_enter(self.stage, stage_trades=self.stage_trades, stage_wins=self.stage_wins)
            self.ppo_steps_at_plateau_evolution_step = int(self.host.ppo_steps)
        if result.get("spawn_phoenix_reset"):
            self._apply_phoenix_reset()
            reset_plateau_for_new_cycle(
                self.plateau_state,
                stage_trades=self.stage_trades,
                stage_wins=self.stage_wins,
            )
        self.attempt = 0
        self.winrate_stagnation_count = 0
        self.hold_stagnation_count = 0
        self.wall_budget_exhausted = False
        self.stage_started_at = time.time()
        self.host._persist_checkpoint(
            training_mode=self.training_mode,
            curriculum_stage=self.stage.value,
            policy_path=str(self.host.final_policy_path),
            phase="curriculum_learning",
            stage_metrics=self._stage_metrics_payload(),
        )
        logger.info(
            "birth.adaptation.applied reason=%s tier=%s new_chunk=%s escalation=%s",
            decision.get("reason", ""),
            self.adaptation_tier,
            self.cur_cfg.rollout_chunk_trades,
            self.escalation_level,
        )
        self._write_progress(
            phase="curriculum_learning",
            message=(
                f"Adaptive recovery tier {self.adaptation_tier + 1}/{self.cur_cfg.max_adaptation_tiers} "
                f"· retry {self.retries_this_stage}/{self.cur_cfg.max_stage_retries}: "
                f"{decision.get('log_message', '')}"
            ),
        )
        return True

    def _adaptation_recovery_context(self, 
        *,
        failure_key: str,
        trigger_type: str = "certified_stall",
        constitution_blocked: bool = False,
    ) -> dict[str, Any]:
        from lumina_core.birth.birth_bus_serde import serialize_learning_snapshot

        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        snap_raw: dict[str, Any] | None = None
        learning_health = "flat"
        if self.cur_cfg.meta_controller_enabled:
            snap, _ = self._observe_snapshot()
            snap_raw = serialize_learning_snapshot(snap)
            learning_health = str(snap.learning_health.value)
        return {
            "trigger_type": trigger_type,
            "failure_key": failure_key,
            "stage_trades": self.stage_trades,
            "required": self.required,
            "current_winrate": current_winrate,
            "winrate_history": list(self.winrate_history),
            "original_rollout_chunk": self.original_rollout_chunk,
            "rollout_chunk_trades": self.cur_cfg.rollout_chunk_trades,
            "trade_budget_remaining": self._trade_budget_remaining(),
            "terminal_blocked": self._should_terminal_stall_in_adaptive(),
            "constitution_blocked": constitution_blocked,
            "learning_health": learning_health,
            "snapshot": snap_raw,
            "winrate": current_winrate,
            "escalation_level": self.escalation_level,
            "adaptation_tier": self.adaptation_tier,
            "retries_this_stage": self.retries_this_stage,
        }

    def _try_adaptive_stall_recovery(self, 
        *,
        failure_key: str,
        trigger_type: str = "certified_stall",
        constitution_blocked: bool = False,
    ) -> bool:
        if not self.cur_cfg.adaptation_enabled or self.cur_cfg.wall_behavior != "adaptive":
            return False
        self._maybe_extend_trade_budget()
        if self._should_terminal_stall_in_adaptive():
            return False
        result = self.bus.adaptation_try_recovery(
            self.stage,
            **self._adaptation_recovery_context(
                failure_key=failure_key,
                trigger_type=trigger_type,
                constitution_blocked=constitution_blocked,
            ),
        )
        return self._apply_bus_adaptation_result(result)

    def _force_never_stop_recovery(self, *, failure_key: str) -> bool:
        """Keep curriculum loop alive when recovery tiers remain (ADR-0017)."""
        if not self.cur_cfg.adaptation_enabled or self.cur_cfg.wall_behavior != "adaptive":
            return False
        if self._should_terminal_stall_in_adaptive():
            return False
        self._maybe_extend_trade_budget()
        if self.plateau_state.active and not can_force_never_stop_recovery(
            self.plateau_state, cfg=self.cur_cfg
        ):
            return self._try_plateau_evolution(failure_key=failure_key)
        if self.plateau_state.active:
            record_forced_recovery(self.plateau_state)
        logger.info(
            "birth.never_stop force_recovery failure=%s tier=%s retries=%s",
            failure_key,
            self.adaptation_tier,
            self.retries_this_stage,
        )
        result = self.bus.adaptation_never_stop(
            self.stage,
            failure_key=failure_key,
            rollout_chunk_trades=self.cur_cfg.rollout_chunk_trades,
            terminal_blocked=self._should_terminal_stall_in_adaptive(),
            current_winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
            stage_trades=self.stage_trades,
            original_rollout_chunk=self.original_rollout_chunk,
        )
        applied = self._apply_bus_adaptation_result(result)
        if applied and self.adaptation_tier >= 1:
            self._mine_and_inject()
        if applied and self.adaptation_tier >= 2 and self.cur_cfg.auto_expand_on_adaptation:
            self._maybe_expand_data()
        return applied

    def _try_adaptation_stuck_escape(self, *, failure_key: str) -> bool:
        if not adaptation_stuck_escape_allowed(
            escapes_used=self.adaptation_stuck_escapes,
            max_escapes=self.cur_cfg.max_adaptation_stuck_escapes,
            trade_budget_remaining=self._trade_budget_remaining(),
        ):
            return False
        logger.warning(
            "birth.adaptation.stuck_escape attempt=%s/%s trades=%s tier=%s failure=%s",
            self.adaptation_stuck_escapes + 1,
            self.cur_cfg.max_adaptation_stuck_escapes,
            self.stage_trades,
            self.adaptation_tier,
            failure_key,
        )
        self._maybe_extend_trade_budget()
        result = self.bus.adaptation_try_recovery(
            self.stage,
            **self._adaptation_recovery_context(
                failure_key=failure_key,
                trigger_type="adaptation_stuck",
            ),
        )
        return self._apply_bus_adaptation_result(result)
