"""stage_loop_data_enrich_core — remaining StageLoopDataEnrichMixin methods."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.birth_control_plane import (
    effective_plateau_max_evolution_steps,
    should_force_swarm_retearnament,
    should_start_swarm_before_recovery,
)
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.starship_birth import (
    evaluate_stage1_edgescore,
    read_last_ppo_entropy,
    should_force_exploration_burst,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_data_enrich")


class StageLoopDataEnrichMixinCore:
    """Policy/signal enrichment for StageLoopSession."""

    def _evolution_max_steps(self) -> int:
        return effective_plateau_max_evolution_steps(
            self.cur_cfg,
            certified=not bool(self.allow_provisional),
        )
    def _resolve_policy_entropy(self) -> float | None:
        cached = getattr(self, "last_policy_entropy", None)
        if cached is not None:
            try:
                return float(cached)
            except (TypeError, ValueError):
                pass
        # Prefer in-process trainer cache (short birth bursts may race JSONL readers).
        trainer = getattr(self.host, "ppo_trainer", None)
        trainer_entropy = getattr(trainer, "last_policy_entropy", None) if trainer is not None else None
        if trainer_entropy is not None:
            try:
                self.last_policy_entropy = float(trainer_entropy)
                return float(self.last_policy_entropy)
            except (TypeError, ValueError):
                pass
        entropy = read_last_ppo_entropy(self.host.workspace_root)
        if entropy is not None:
            self.last_policy_entropy = float(entropy)
        return entropy
    def _capture_trainer_policy_entropy(self) -> None:
        """Primary Starship path: stash entropy immediately after a PPO update."""
        trainer = getattr(self.host, "ppo_trainer", None)
        trainer_entropy = getattr(trainer, "last_policy_entropy", None) if trainer is not None else None
        if trainer_entropy is None:
            return
        try:
            self.last_policy_entropy = float(trainer_entropy)
        except (TypeError, ValueError):
            return
    def _apply_exploration_burst(self, *, reason: str) -> str:
        """Starship entropy life-support — revive a dead policy before ladder steps."""
        mult = float(getattr(self.cur_cfg, "starship_exploration_burst_multiplier", 2.5))
        base = int(getattr(self.cur_cfg, "exploration_steps", 2000) or 2000)
        self.cur_cfg.exploration_steps = max(base, int(base * mult))
        self.strong_recovery_mode = True
        self.starship_exploration_burst_active = True
        if self.cur_cfg.meta_controller_enabled:
            try:
                self.bus.meta_patch_state(self.stage, explore_multiplier=1.0)
            except Exception as exc:
                logger.debug("birth.starship.explore_burst_meta_failed: %s", exc)
        # Fresh head when entropy is known-dead — keep buffer/oracle.
        # Never nuke a frozen / rejected-no-lift champion.
        entropy = self._resolve_policy_entropy()
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
        allow_fresh_head = not rejected and not (freeze_armed and champ_path)
        if (
            allow_fresh_head
            and entropy is not None
            and float(entropy) < float(self.cur_cfg.stage1_entropy_floor)
        ):
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            detail = f"exploration_burst+fresh_head ({reason})"
        else:
            detail = f"exploration_burst ({reason})"
        logger.warning("birth.starship.exploration_burst %s entropy=%s", detail, entropy)
        return detail
    def _maybe_entropy_life_support(self) -> bool:
        """Return True when an exploration burst was forced (caller should skip ladder)."""
        hold_ratio = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
        entropy = self._resolve_policy_entropy()
        ppo_steps = int(getattr(self.host, "ppo_steps", 0) or 0)
        if not should_force_exploration_burst(
            entropy=entropy,
            hold_ratio=hold_ratio,
            cfg=self.cur_cfg,
            ppo_steps=ppo_steps,
        ):
            self.starship_exploration_burst_active = False
            return False
        if bool(getattr(self, "starship_exploration_burst_active", False)):
            # Already bursting this cycle — allow ladder to proceed after one burst.
            return False
        self._apply_exploration_burst(reason="entropy_life_support")
        self._write_progress(
            phase="exploration_burst",
            message="Starship entropy life-support: exploration burst before recovery ladder",
        )
        return True
    def _current_edgescore(self) -> float:
        from lumina_core.birth.starship_birth import (
            evaluate_stage2_edgescore,
            evaluate_stage3_edgescore,
        )

        entropy = self._resolve_policy_entropy()
        total_pnl = (
            float(sum(self.stage_val_pnl)) if getattr(self, "stage_val_pnl", None) else None
        )
        ppo_steps = int(getattr(self.host, "ppo_steps", 0) or 0)
        violations = int(self.host._constitution_guard.violations)
        if self.stage == CurriculumStage.STAGE2_RANGE and bool(
            getattr(self.cur_cfg, "stage2_edgescore_enabled", False)
        ):
            flat = float(self.stage_range_flat_bars) / float(
                max(1, self.stage_range_total_signals)
            )
            if self.stage_range_total_signals < 50:
                flat = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
            roll_wr = None
            try:
                from lumina_core.birth.plateau_rolling import rolling_winrate_last_n_trades
                from lumina_core.birth.starship_edgescore_core import (
                    gate_rolling_winrate,
                )

                window = int(getattr(self.cur_cfg, "stage1_rolling_pass_window", 500) or 500)
                chunks = getattr(self, "rolling_trade_chunks", None)
                wins_at = getattr(self, "wins_at_trade_milestones", None) or {}
                if not isinstance(wins_at, dict):
                    wins_at = {}
                wr_meta = rolling_winrate_last_n_trades(
                    stage_trades=int(self.stage_trades),
                    stage_wins=int(self.stage_wins),
                    wins_at_trade=wins_at,
                    window=window,
                    chunks=chunks if isinstance(chunks, list) else None,
                    return_meta=True,
                )
                if isinstance(wr_meta, tuple) and len(wr_meta) >= 3:
                    wr, src, covered = float(wr_meta[0]), str(wr_meta[1]), int(wr_meta[2])
                    roll_wr = gate_rolling_winrate(
                        rolling_wr=wr, source=src, covered=covered, window=window
                    )
            except Exception:
                roll_wr = None
            edge = evaluate_stage2_edgescore(
                trades=self.stage_trades,
                wins=self.stage_wins,
                range_flat_ratio=flat,
                range_round_trips=self.stage_range_round_trips,
                range_total_signals=self.stage_range_total_signals,
                constitution_violations=violations,
                required=self.required,
                cfg=self.cur_cfg,
                entropy=entropy,
                total_pnl=total_pnl,
                ppo_steps=ppo_steps,
                rolling_winrate=roll_wr,
            )
            return float(edge.score)
        if self.stage == CurriculumStage.STAGE3_MIXED and bool(
            getattr(self.cur_cfg, "stage3_edgescore_enabled", False)
        ):
            edge = evaluate_stage3_edgescore(
                trades=self.stage_trades,
                wins=self.stage_wins,
                hold_signals=self.stage_hold_signals,
                total_signals=self.stage_total_signals,
                constitution_violations=violations,
                required=self.required,
                cfg=self.cur_cfg,
                entropy=entropy,
                total_pnl=total_pnl,
                ppo_steps=ppo_steps,
            )
            return float(edge.score)
        edge = evaluate_stage1_edgescore(
            trades=self.stage_trades,
            wins=self.stage_wins,
            hold_signals=self.stage_hold_signals,
            total_signals=self.stage_total_signals,
            constitution_violations=violations,
            required=self.required,
            cfg=self.cur_cfg,
            entropy=entropy,
            total_pnl=total_pnl,
            ppo_steps=ppo_steps,
        )
        return float(edge.score)
    def _apply_swarm_variant_for_rollout(self) -> tuple[Any | None, float]:
        variant = self.swarm_state.current_variant()
        if variant is None:
            return None, 1.0
        if variant.policy_path:
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=True,
                policy_path=variant.policy_path,
            )
        return variant.reward, float(variant.explore_multiplier)
    def _restore_pre_swarm_policy(self) -> None:
        """Fail-closed revert to pre-swarm / EdgeScore champion / stage-best."""
        candidates = [
            str(getattr(self.swarm_state, "pre_swarm_policy_path", "") or "").strip(),
            str(getattr(self, "best_edgescore_policy_path", "") or "").strip(),
            str(getattr(self.plateau_state, "best_policy_path", "") or "").strip(),
            str(self.host.final_policy_path or "").strip(),
        ]
        for path in candidates:
            if path and Path(path).is_file():
                self.host.current_policy = self.host._create_birth_policy(
                    allow_load_existing=True,
                    policy_path=path,
                )
                logger.info("birth.policy_swarm.reverted path=%s", path)
                return
        logger.warning("birth.policy_swarm.revert_failed no_valid_champion_path")
    def _maybe_swarm_on_wall_skill_fail(self) -> bool:
        """Starship: swarm-first on wall+skill fail even when plateau has not entered.

        Keeps Seal reject→hard-stop intact; only starts a tournament when idle.
        """
        if self.allow_provisional or bool(self.swarm_state.active):
            return False
        if not bool(getattr(self.cur_cfg, "starship_swarm_first_enabled", True)):
            return False
        if not bool(getattr(self, "wall_budget_exhausted", False)):
            return False
        if int(self.stage_trades) < int(self.required):
            return False
        # Reject freeze: no fresh tournament until accept/wipe.
        if bool(getattr(self, "swarm_rejected_no_lift", False)) or bool(
            getattr(self.swarm_state, "rejected_no_lift", False)
        ):
            if not bool(getattr(self, "swarm_champion_accepted", False)):
                return False
        winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        from lumina_core.birth.curriculum import CurriculumStage

        hygiene = float(getattr(self.cur_cfg, "stage1_winrate_pass_floor", 0.35) or 0.35)
        if self.stage == CurriculumStage.STAGE3_MIXED:
            hygiene = float(getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35)
        elif self.stage == CurriculumStage.STAGE2_RANGE:
            # Stage2 skill = flat band; wall path still may start swarm via plateau.
            return False
        if winrate + 1e-9 >= hygiene:
            return False
        started = self._ensure_swarm_first()
        if started:
            logger.info(
                "birth.starship.swarm_on_wall_skill_fail trades=%s wr=%.1f%% hygiene=%.0f%%",
                self.stage_trades,
                winrate * 100.0,
                hygiene * 100.0,
            )
        return started
    def _ensure_swarm_first(self) -> bool:
        """Start swarm tournament when Starship requires it. True if swarm now active."""
        from lumina_core.birth.plateau_escalator import (
            should_block_phoenix_no_lift,
            should_brake_recovery_no_lift,
        )

        no_lift = (
            should_brake_recovery_no_lift(self.plateau_state)
            or should_block_phoenix_no_lift(self.plateau_state)
            or bool(getattr(self, "swarm_rejected_no_lift", False))
        )
        hard_stop = bool(getattr(self, "_hard_stop_terminal_armed", False))
        retearnament_used = bool(getattr(self, "swarm_retearnament_used", False))
        if should_force_swarm_retearnament(
            cfg=self.cur_cfg,
            swarm_state=self.swarm_state,
            allow_provisional=self.allow_provisional,
            hard_stop_armed=hard_stop,
            no_lift_brake=no_lift,
            retearnament_used=retearnament_used,
        ):
            self.swarm_retearnament_used = True
            # Clear reject freeze so the new tournament can run cleanly.
            self.swarm_rejected_no_lift = False
            if self.swarm_state is not None:
                self.swarm_state.rejected_no_lift = False
            self._start_policy_swarm(force=True)
            self._write_progress(
                phase="policy_swarm",
                message="Starship re-swarm after hard-stop/no-lift (max 1)",
            )
            return bool(self.swarm_state.active)
        # Plant must breathe before swarm theater (organism birth rule).
        soft_blocks = int(
            getattr(self.host._constitution_guard, "soft_blocks", 0) or 0
        )
        signals = max(1, int(getattr(self, "stage_total_signals", 0) or 0))
        rate = (1000.0 * float(soft_blocks)) / float(signals)
        plant_max = float(
            getattr(self.cur_cfg, "birth_plant_soft_block_rate_max_per_1k", 100.0) or 100.0
        )
        if rate > plant_max:
            logger.warning(
                "birth.plant_blocked skip_swarm rate=%.1f/1k max=%.0f",
                rate,
                plant_max,
            )
            return False
        if not should_start_swarm_before_recovery(
            cfg=self.cur_cfg,
            swarm_state=self.swarm_state,
            allow_provisional=self.allow_provisional,
        ):
            return bool(self.swarm_state.active)
        # Stage2: remediate flat-band under/over activity before swarm-first.
        try:
            from lumina_core.birth.curriculum import CurriculumStage
            from lumina_core.birth.plateau_escalator import (
                stage2_should_defer_swarm_for_flat_band,
            )

            if self.stage == CurriculumStage.STAGE2_RANGE:
                flat_ratio = float(self.stage_range_flat_bars) / float(
                    max(1, self.stage_range_total_signals)
                )
                if stage2_should_defer_swarm_for_flat_band(
                    range_flat_ratio=flat_ratio,
                    range_total_signals=self.stage_range_total_signals,
                    stage_trades=self.stage_trades,
                    required=self.required,
                    evolution_step=int(
                        getattr(self.plateau_state, "evolution_step", 0) or 0
                    ),
                    cfg=self.cur_cfg,
                ):
                    logger.info(
                        "birth.stage2.skip_swarm_first_flat_band flat=%.1f%% step=%s",
                        flat_ratio * 100.0,
                        int(getattr(self.plateau_state, "evolution_step", 0) or 0),
                    )
                    return bool(self.swarm_state.active)
        except Exception as exc:
            logger.debug("birth.stage2.flat_band_swarm_gate_failed: %s", exc)
        self._start_policy_swarm(force=True)
        self._write_progress(
            phase="policy_swarm",
            message="Starship swarm-first tournament before recovery theater",
        )
        return bool(self.swarm_state.active)
