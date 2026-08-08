"""Plateau evolution ladder advance / try / exhausted remediation (M5)."""

from __future__ import annotations

from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    begin_evolution_step,
    evolution_ladder_exhausted,
    should_force_advance_evolution_step,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_scorecard import learning_metric_target
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionAdvanceMixin(StageLoopMixinBase):
    """In-loop ladder advancement and post-exhaust remediation handoff."""

    def _plateau_pass_target(self) -> float:
        return learning_metric_target(
            self.stage,
            cfg=self.cur_cfg,
            pass_criteria=self.stage_pass_criteria,
        )

    def _try_evolution_exhausted_remediation(self, *, failure_key: str) -> bool:
        """Start stall remediation when evolution ladder is done (no phantom steps)."""
        if not self.plateau_state.active or self.allow_provisional:
            return False
        if not evolution_ladder_exhausted(
            self.plateau_state,
            stage=self.stage,
            max_steps=self._evolution_max_steps(),
        ):
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            rejected = bool(
                getattr(self.swarm_state, "rejected_no_lift", False)
                or getattr(self, "swarm_rejected_no_lift", False)
            ) and not bool(
                getattr(self, "swarm_champion_accepted", False)
                or getattr(self.swarm_state, "champion_accepted", False)
            )
            if rejected:
                self._write_progress(
                    phase="swarm_reject_attention",
                    message=(
                        "Swarm tournament produced no tournament lift — "
                        "champion frozen; accept champion or wipe."
                    ),
                )
            return False
        if bool(getattr(self.cur_cfg, "starship_stall_after_swarm_only", True)):
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                return True
            if not str(getattr(self.swarm_state, "committed_variant_id", "") or "").strip():
                if self._ensure_swarm_first() or bool(self.swarm_state.active):
                    return True
        pending = self._plateau_terminal_pending(failure_key=failure_key)
        if pending is None:
            return False
        return self._try_stall_remediation_on_terminal(pending)

    def _maybe_advance_plateau_evolution_in_loop(self) -> bool:
        """Advance plateau evolution between rollouts (mirrors remediation loop)."""
        if not self.plateau_state.active or self.allow_provisional:
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            self.plateau_state.evolution_step = max(
                int(self.plateau_state.evolution_step),
                int(self._evolution_max_steps()),
            )
            return False
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        pass_target = self._plateau_pass_target()
        ppo_since = self._ppo_steps_since_evolution_step()
        forced = should_force_advance_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
            stage_trades=self.stage_trades,
            required=self.required,
        )
        if not should_trigger_plateau_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            allow_start=False,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
            stage_trades=self.stage_trades,
            required=self.required,
        ):
            return False
        if self._maybe_entropy_life_support():
            return True
        if bool(self.swarm_state.active):
            return False
        action = begin_evolution_step(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            stage=self.stage,
            max_steps=self._evolution_max_steps(),
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = self._apply_plateau_evolution_action(action)
        self._finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key=self._stage_failure_key(),
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _try_plateau_evolution(self, *, failure_key: str) -> bool:
        if not self.plateau_state.active or self.allow_provisional:
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            self.plateau_state.evolution_step = max(
                int(self.plateau_state.evolution_step),
                int(self._evolution_max_steps()),
            )
            return False
        if self._maybe_entropy_life_support():
            return True
        if bool(self.swarm_state.active):
            return False
        if bool(getattr(self.cur_cfg, "starship_swarm_first_enabled", True)):
            if self._ensure_swarm_first():
                return True
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        pass_target = self._plateau_pass_target()
        ppo_since = self._ppo_steps_since_evolution_step()
        forced = should_force_advance_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        )
        if not should_trigger_plateau_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            allow_start=True,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        ):
            return False
        action = begin_evolution_step(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            stage=self.stage,
            max_steps=self._evolution_max_steps(),
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = self._apply_plateau_evolution_action(action)
        self._finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key=failure_key or self._stage_failure_key(),
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced


__all__ = ["PlateauEvolutionAdvanceMixin"]
