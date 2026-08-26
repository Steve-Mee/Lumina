"""Starship scorecard enrichment for progress write (Wave H)."""
from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopProgressStarshipMixin:
    """Owns EdgeScore / entropy / champion fields on the progress scorecard."""

    def _progress_enrich_starship_scorecard(
        self,
        scorecard: dict[str, Any],
        *,
        current_stage_trades: int,
        rolling_for_blocker: float | None,
    ) -> None:
        try:
            from lumina_core.birth.starship_birth import (
                compute_expectancy_proxy,
                policy_entropy_alive,
            )

            entropy = self._resolve_policy_entropy()
            scorecard["policy_entropy"] = (
                round(float(entropy), 6) if entropy is not None else None
            )
            scorecard["entropy_alive"] = bool(
                policy_entropy_alive(
                    entropy,
                    cfg=self.cur_cfg,
                    ppo_steps=int(getattr(self.host, "ppo_steps", 0) or 0),
                )
            )
            scorecard["starship_exploration_burst_active"] = bool(
                getattr(self, "starship_exploration_burst_active", False)
            )
            # Stage-2: grade pilot skill expectancy when policy counts exist.
            exp_proxy = compute_expectancy_proxy(
                wins=self.stage_wins,
                trades=current_stage_trades,
                rolling_winrate=rolling_for_blocker,
            )
            try:
                from lumina_core.birth.curriculum import CurriculumStage
                from lumina_core.birth.stage2_skill_metric import (
                    resolve_stage2_skill_counts,
                    skill_expectancy_for_pass,
                )

                if self.stage == CurriculumStage.STAGE2_RANGE and bool(
                    getattr(self.cur_cfg, "stage2_skill_metric_policy_only", True)
                ):
                    sc = resolve_stage2_skill_counts(
                        total_trades=int(current_stage_trades),
                        total_wins=int(self.stage_wins),
                        policy_trades=int(getattr(self, "stage_policy_trades", 0) or 0),
                        policy_wins=int(getattr(self, "stage_policy_wins", 0) or 0),
                        plant_trades=int(getattr(self, "stage_plant_trades", 0) or 0),
                        plant_wins=int(getattr(self, "stage_plant_wins", 0) or 0),
                        skill_only=True,
                        required=int(self.required),
                        skill_min_trades=getattr(
                            self.cur_cfg, "stage2_skill_min_trades", None
                        ),
                    )
                    skill_exp, _, *_rest = skill_expectancy_for_pass(
                        sc, rolling_winrate=rolling_for_blocker
                    )
                    exp_proxy = float(skill_exp)
                    scorecard["expectancy_proxy_total"] = round(
                        float(sc.total_expectancy), 6
                    )
            except Exception:
                pass
            scorecard["expectancy_proxy"] = round(float(exp_proxy), 6)
            edgescore_on = bool(
                getattr(self.cur_cfg, "stage1_edgescore_enabled", False)
                or getattr(self.cur_cfg, "stage2_edgescore_enabled", False)
                or getattr(self.cur_cfg, "stage3_edgescore_enabled", False)
            )
            if edgescore_on:
                from lumina_core.birth.starship_birth import (
                    is_edgescore_champion_eligible,
                    live_stage_winrate,
                    sanitize_edgescore_champion,
                )

                edge_score = float(self._current_edgescore())
                scorecard["edgescore"] = round(edge_score, 4)
                # Live sanitize: drop early/noise champions before freeze can re-arm.
                plateau_wr = float(getattr(self.plateau_state, "best_winrate", 0.0) or 0.0)
                live_wr = live_stage_winrate(
                    wins=int(getattr(self, "stage_wins", 0) or 0),
                    trades=int(current_stage_trades),
                )
                stage_key = str(getattr(self.stage, "value", self.stage) or "")
                best, at_trade, cleared = sanitize_edgescore_champion(
                    best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                    best_edgescore_at_trade=int(
                        getattr(self, "best_edgescore_at_trade", 0) or 0
                    ),
                    best_winrate=plateau_wr,
                    required=int(self.required),
                    cfg=self.cur_cfg,
                    stage=stage_key,
                    live_winrate=live_wr,
                )
                self.best_edgescore = best
                self.best_edgescore_at_trade = at_trade
                if cleared:
                    self.best_edgescore_policy_path = ""
                # Champion freeze tracker — only after pass-gate volume (no early noise).
                eligible = is_edgescore_champion_eligible(
                    stage_trades=int(current_stage_trades),
                    required=int(self.required),
                    cfg=self.cur_cfg,
                )
                if (
                    eligible
                    and edge_score > float(getattr(self, "best_edgescore", 0.0) or 0.0)
                ):
                    skill_exp = getattr(self, "skill_metric_expectancy", None)
                    proxy_exp = getattr(self, "expectancy_proxy", None)
                    try:
                        exp_live = float(
                            skill_exp if skill_exp is not None else proxy_exp
                        )
                    except (TypeError, ValueError):
                        exp_live = -1.0
                    stage_key = str(
                        getattr(self.stage, "value", self.stage) or ""
                    ).lower()
                    is_early_quality = stage_key in {
                        "stage2_range",
                        "stage2",
                        "range",
                        "2",
                        "stage3_mixed",
                        "stage3",
                        "mixed",
                        "3",
                    }
                    exp_floor = float(
                        getattr(self.cur_cfg, "stage2_expectancy_floor", -0.15) or -0.15
                    )
                    # Occupancy-only score must not re-lock after sanitize (PID 33628).
                    if (not is_early_quality) or exp_live + 1e-12 >= exp_floor:
                        self.best_edgescore = edge_score
                        self.best_edgescore_at_trade = int(current_stage_trades)
                        # Snapshot champion weights when EdgeScore improves (not only plateau WR).
                        champion_dir = self.host.workspace_root / "lumina_agents" / "ppo"
                        champion_dir.mkdir(parents=True, exist_ok=True)
                        champ_path = (
                            champion_dir / f"birth_champion_edgescore_{self.stage.value}.zip"
                        )
                        save_fn = getattr(
                            self.host.ppo_trainer, "save_final_birth_policy", None
                        )
                        if callable(save_fn):
                            try:
                                save_fn(str(champ_path))
                                if champ_path.is_file():
                                    self.best_edgescore_policy_path = str(champ_path)
                            except Exception as exc:
                                logger.debug("birth.starship.champion_save_failed: %s", exc)
                        if not str(
                            getattr(self, "best_edgescore_policy_path", "") or ""
                        ).strip():
                            best_path = str(
                                getattr(self.plateau_state, "best_policy_path", "") or ""
                            ).strip()
                            if best_path:
                                self.best_edgescore_policy_path = best_path
            from lumina_core.birth.starship_swarm_gates import dual_write_tournament_lift_keys

            dual_write_tournament_lift_keys(
                scorecard,
                lift_ok=bool(
                    getattr(
                        self,
                        "swarm_tournament_lift_ok",
                        getattr(self, "swarm_edgescore_lift_ok", False),
                    )
                ),
                at_start=float(
                    getattr(
                        self,
                        "swarm_tournament_at_start",
                        getattr(self, "swarm_edgescore_at_start", -1.0),
                    )
                    or -1.0
                ),
            )
            scorecard["swarm_rejected_no_lift"] = bool(
                getattr(self, "swarm_rejected_no_lift", False)
                or getattr(self.swarm_state, "rejected_no_lift", False)
            )
            from lumina_core.birth.starship_birth import publish_edgescore_champion_fields

            scorecard.update(
                publish_edgescore_champion_fields(
                    best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                    best_edgescore_at_trade=int(
                        getattr(self, "best_edgescore_at_trade", 0) or 0
                    ),
                    best_edgescore_policy_path=str(
                        getattr(self, "best_edgescore_policy_path", "") or ""
                    ),
                    stage_trades=int(current_stage_trades),
                    required=int(self.required),
                    cfg=self.cur_cfg,
                )
            )
        except Exception as exc:
            logger.debug("birth.starship.scorecard_fields_failed: %s", exc)
