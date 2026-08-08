"""Phoenix/stall remediation extract (global residual)."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class StageLoopRecoveryPhoenixMixin:
    def _apply_phoenix_in_loop(self, *, stall_reason: str) -> bool:
        """Apply phoenix novelty inside rollout loop; True when loop should continue."""
        if not self.cur_cfg.autonomous_recovery_enabled or not self.cur_cfg.phoenix_loop_enabled:
            return False
        if bool(getattr(self.swarm_state, "rejected_no_lift", False)) or bool(
            getattr(self, "swarm_rejected_no_lift", False)
        ):
            logger.warning(
                "birth.phoenix.blocked_swarm_rejected_no_lift stall=%s",
                stall_reason,
            )
            self._write_progress(
                phase="stage_stalled",
                message=(
                    "Starship: swarm rejected (no tournament lift) — phoenix blocked; "
                    "champion frozen"
                ),
            )
            return False
        if should_brake_recovery_no_lift(self.plateau_state) or should_block_phoenix_no_lift(
            self.plateau_state
        ):
            logger.warning(
                "birth.phoenix.in_loop blocked_no_lift cycles=%s best=%.2f%%",
                self.plateau_state.full_recovery_cycles,
                float(self.plateau_state.best_winrate) * 100.0,
            )
            # Starship A3: no-lift → force swarm tournament once, never silent phoenix spam.
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                return True
            self.swarm_rejected_no_lift = True
            self._write_progress(
                phase="stage_stalled",
                message=(
                    "Starship no-lift brake: swarm tournament required before phoenix; "
                    "needs attention"
                ),
            )
            return False
        if should_block_phoenix_until_swarm(
            cfg=self.cur_cfg,
            swarm_state=self.swarm_state,
            allow_provisional=self.allow_provisional,
        ):
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                logger.info("birth.phoenix.blocked_swarm_first stall=%s", stall_reason)
                return True
            logger.warning("birth.phoenix.blocked_awaiting_swarm stall=%s", stall_reason)
            return False
        if self._maybe_entropy_life_support():
            return True
        patch = self.bus.phoenix_begin_cycle(
            self.stage,
            stall_reason=stall_reason,
            novelty=str(self.organism_autonomy_state.phoenix.last_action or "expand_data"),
        )
        if patch is None:
            return False
        self.organism_autonomy_state.autonomous_recovery_count += 1
        self.remediation_state.active = False
        self.remediation_state.remediation_step = 0
        self.remediation_state.remediation_rollouts_this_step = 0
        _cid = self.bus.emit(
            "plateau_reset_cycle",
            self.stage,
            {"stage_trades": self.stage_trades, "stage_wins": self.stage_wins},
        )
        self.bus.registry.pop_response(_cid)
        novelty_value = str(self.organism_autonomy_state.phoenix.last_action or "expand_data")
        detail = f"phoenix in-loop: {novelty_value}"
        if novelty_value in {"expand_data", "widen_horizon"}:
            self._maybe_expand_data()
            detail = f"{detail}; data expanded"
        elif novelty_value == "policy_swarm":
            self._start_policy_swarm()
            detail = f"{detail}; policy swarm started"
        elif novelty_value == "reward_sweep":
            self.remediation_state.meta_sweep_index += 1
            self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 1)
            detail = f"{detail}; reward sweep #{self.remediation_state.meta_sweep_index}"
        elif novelty_value == "soft_gate":
            detail = f"{detail}; soft gate floor {self.cur_cfg.stage1_winrate_pass_floor:.0%}"
        self.attempt = 0
        self.strong_recovery_mode = True
        self._write_progress(phase="phoenix_cycle", message=detail)
        logger.warning("birth.phoenix.in_loop %s", detail)
        return True
    def _apply_stall_remediation_action(self, action: StallRemediationAction | None) -> str:
        if action is None:
            return "no action"
        if self._maybe_entropy_life_support():
            return "starship exploration burst (entropy life-support)"
        detail = ""
        if action == StallRemediationAction.EXPAND_AND_RETRY:
            self._maybe_expand_data()
            detail = "expanded data window"
        elif action == StallRemediationAction.BUFFER_CURATE_ORACLE:
            removed = curate_buffer_bottom_half(self.host.buffer)
            self.strong_recovery_mode = True
            self._mine_and_inject(aggressive=True)
            detail = f"curated {removed} low-reward buffer trajectories"
        elif action == StallRemediationAction.REGIME_DIVERSE_SLICE:
            filtered = filter_train_ticks_for_holdout_profile(
                self.active_train,
                self.holdout_ticks_ref,
            )
            if filtered:
                self.active_train = list(filtered)
                self.active_stage_ticks = filter_ticks_for_stage(self.stage, self.active_train)
            detail = "regime-diverse train slice applied"
        elif action == StallRemediationAction.META_SWEEP:
            self.remediation_state.meta_sweep_index += 1
            self.escalation_level = min(
                self.cur_cfg.max_escalation_level,
                self.escalation_level + 1,
            )
            detail = f"meta explore sweep #{self.remediation_state.meta_sweep_index}"
        elif action == StallRemediationAction.ORACLE_DISTILL:
            detail = self._apply_oracle_distill()
        if self.remediation_state.remediation_cycle >= 2:
            freeze_armed = bool(
                getattr(self.cur_cfg, "starship_champion_freeze_enabled", True)
            ) and not bool(self.allow_provisional)
            rejected = bool(getattr(self.swarm_state, "rejected_no_lift", False)) or bool(
                getattr(self, "swarm_rejected_no_lift", False)
            )
            champ_path = str(
                getattr(self, "best_edgescore_policy_path", "")
                or getattr(self.plateau_state, "best_policy_path", "")
                or ""
            ).strip()
            if rejected or (freeze_armed and champ_path):
                if detail:
                    detail = (
                        f"{detail}; reinit skipped (champion freeze) "
                        f"cycle {self.remediation_state.remediation_cycle}"
                    )
                else:
                    detail = (
                        f"reinit skipped (champion freeze) "
                        f"cycle {self.remediation_state.remediation_cycle}"
                    )
            else:
                self.host.current_policy = self.host._create_birth_policy(
                    allow_load_existing=False
                )
                if self.intra_state is not None:
                    self.intra_state.hard_pct = 0.0
                    self._rebuild_intra_pools(self.active_stage_ticks)
                self.strong_recovery_mode = True
                if detail:
                    detail = (
                        f"{detail}; aggressive cycle {self.remediation_state.remediation_cycle}"
                    )
                else:
                    detail = f"aggressive cycle {self.remediation_state.remediation_cycle}"
        return detail
