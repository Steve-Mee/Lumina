"""Plateau evolution action application + phoenix reset bodies."""
from __future__ import annotations

from pathlib import Path

from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    is_valid_best_policy_snapshot,
)
from lumina_core.birth.stall_remediation import curate_buffer_top_quartile
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionActionsMixin(StageLoopMixinBase):
    def _apply_plateau_evolution_action(self, action: EvolutionAction) -> tuple[str, bool]:
        if action == EvolutionAction.EXPAND_DATA:
            if not self.cur_cfg.auto_expand_on_adaptation:
                return "expand skipped — auto_expand_on_adaptation disabled", False
            if self._maybe_expand_data():
                return "expanded data window", True
            return "expand skipped — data window at max", False
        if action == EvolutionAction.POLICY_ROLLBACK:
            if not is_valid_best_policy_snapshot(self.plateau_state, cfg=self.cur_cfg):
                return "rollback skipped — no valid best policy snapshot (min trades)", False
            # Raptor v14: prefer rolling-best skill snapshot when available.
            rolling_path = str(
                getattr(self.plateau_state, "best_rolling_policy_path", "") or ""
            ).strip()
            lifetime_path = str(self.plateau_state.best_policy_path or "").strip()
            use_rolling = bool(
                rolling_path
                and Path(rolling_path).is_file()
                and float(getattr(self.plateau_state, "best_rolling_winrate", 0) or 0)
                >= float(self.plateau_state.best_winrate)
            )
            rollback_path = rolling_path if use_rolling else lifetime_path
            if rollback_path and Path(rollback_path).is_file():
                self.host.current_policy = self.host._create_birth_policy(
                    allow_load_existing=True,
                    policy_path=rollback_path,
                )
                if use_rolling:
                    return (
                        f"rollback to rolling-best "
                        f"{float(self.plateau_state.best_rolling_winrate):.1%} winrate",
                        True,
                    )
                return f"rollback to {self.plateau_state.best_winrate:.1%} winrate", True
            return "rollback skipped — no best policy snapshot", False
        if action == EvolutionAction.INTRA_EASY_ONLY:
            # Stage1: easy-only intra curriculum.
            if self.intra_state is not None:
                self.intra_state.hard_pct = 0.0
                self.intra_state.easy_trades = 0
                self.intra_state.easy_wins = 0
                self.intra_state.easy_winrate_history.clear()
                self._rebuild_intra_pools(self.active_stage_ticks)
                return "intra stage1 easy-only pool", True
            # Stage2: easy-only range intra if available.
            if getattr(self, "intra_s2_state", None) is not None:
                self.intra_s2_state.hard_pct = 0.0
                if hasattr(self, "_rebuild_intra_pools"):
                    self._rebuild_intra_pools(self.active_stage_ticks)
                return "intra stage2 easy-only pool", True
            # Raptor v12/v14: stage3 skill temperament (explore vs selectivity).
            from lumina_core.birth.curriculum import CurriculumStage

            if self.stage == CurriculumStage.STAGE3_MIXED:
                hold_ratio = float(self.stage_hold_signals) / float(
                    max(1, self.stage_total_signals)
                )
                self.strong_recovery_mode = True
                self.strong_recovery_attempts = int(
                    getattr(self, "strong_recovery_attempts", 0) or 0
                ) + 1
                base_explore = int(getattr(self.cur_cfg, "exploration_steps", 512) or 512)
                if hold_ratio < 0.40:
                    # Over-trading zone: reduce noise, keep quality mining path.
                    self.cur_cfg.exploration_steps = max(64, int(base_explore * 0.5))
                    logger.info(
                        "birth.plateau.stage3_skill_selectivity trades=%s wr=%.2f%% hold=%.1f%%",
                        self.stage_trades,
                        float(self.stage_wins) / float(max(1, self.stage_trades)) * 100.0,
                        hold_ratio * 100.0,
                    )
                    return "stage3 skill selectivity (reduce explore — overtrade)", True
                self.cur_cfg.exploration_steps = max(base_explore, base_explore * 4)
                logger.info(
                    "birth.plateau.stage3_skill_explore_boost trades=%s wr=%.2f%% hold=%.1f%%",
                    self.stage_trades,
                    float(self.stage_wins) / float(max(1, self.stage_trades)) * 100.0,
                    hold_ratio * 100.0,
                )
                return "stage3 skill explore-boost (ladder WR recovery)", True
            return "intra easy-only skipped — no intra curriculum on this stage", False
        if action == EvolutionAction.FRESH_POLICY:
            if bool(getattr(self.swarm_state, "rejected_no_lift", False)) or bool(
                getattr(self, "swarm_rejected_no_lift", False)
            ):
                if not bool(
                    getattr(self, "swarm_champion_accepted", False)
                    or getattr(self.swarm_state, "champion_accepted", False)
                ):
                    return "fresh policy blocked — champion freeze after swarm no-lift", False
            if bool(getattr(self.cur_cfg, "starship_champion_freeze_enabled", True)) and not bool(
                self.allow_provisional
            ):
                best_edge = float(getattr(self, "best_edgescore", 0.0) or 0.0)
                gap = float(getattr(self.cur_cfg, "starship_champion_edgescore_gap", 0.02))
                if best_edge > 0.0:
                    try:
                        live_edge = float(self._current_edgescore())
                    except Exception:
                        live_edge = 0.0
                    # Allow FRESH only when live is within gap of champion (exploration OK).
                    if live_edge + gap < best_edge:
                        return (
                            "fresh policy blocked — live EdgeScore below champion gap",
                            False,
                        )
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            return "fresh policy (reinitialized weights, buffer/oracle retained)", True
        if action == EvolutionAction.ORACLE_DISTILL:
            return self._apply_oracle_distill(), True
        if action == EvolutionAction.PHOENIX_RESET:
            if bool(getattr(self.swarm_state, "rejected_no_lift", False)) or bool(
                getattr(self, "swarm_rejected_no_lift", False)
            ):
                return "phoenix blocked — champion freeze after swarm no-lift", False
            return self._apply_phoenix_reset()
        return "", False

    def _apply_phoenix_reset(self) -> tuple[str, bool]:
        self.host.current_policy = self.host._create_birth_policy(
            allow_load_existing=False,
            force_reinit=True,
        )
        removed = curate_buffer_top_quartile(
            self.host.buffer,
            keep_pct=float(self.cur_cfg.plateau_oracle_distill_top_pct),
        )
        if self.intra_state is not None:
            self.intra_state.hard_pct = 0.0
            self.intra_state.easy_trades = 0
            self.intra_state.easy_wins = 0
            self.intra_state.easy_winrate_history.clear()
            self._rebuild_intra_pools(self.active_stage_ticks)
        self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 2)
        self.strong_recovery_mode = True
        detail = f"phoenix reset (policy reinit, buffer curated, removed {removed})"
        try:
            from lumina_core.notifications.milestone_events import phoenix_reset_event

            self.host._notify_milestone(
                phoenix_reset_event(
                    cycle=self.plateau_state.full_recovery_cycles,
                    winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
                    detail=detail,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_phoenix_failed: %s", exc)
        return detail, True
