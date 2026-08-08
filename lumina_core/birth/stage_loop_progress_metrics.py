"""Stage-loop metrics payload builder."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.plateau_escalator import (
    build_plateau_audit,
    plateau_min_stage_trades,
    progress_fields as plateau_progress_fields,
    quarantine_progress_payload,
    remediation_is_exhausted,
)
from lumina_core.birth.progress import merge_birth_progress_extra
from lumina_core.birth.stage_scorecard import (
    build_scorecard_payload,
    enrich_adaptation_payload,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopProgressMetricsMixin:
    """Builds stage_metrics dict for checkpoint/progress."""

    def _stage_metrics_payload(self) -> dict[str, Any]:
        payload = self.host._stage_metrics_snapshot(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            stage_range_hold_signals=self.stage_range_hold_signals,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_round_trips=self.stage_range_round_trips,
            patterns_mined=self.patterns_mined,
        )
        payload["winrate_history"] = list(self.winrate_history)
        payload["reward_history"] = list(self.reward_history)
        payload["velocity_stall_attempts"] = int(self.low_velocity_attempts)
        payload["strong_recovery_mode"] = bool(self.strong_recovery_mode)
        payload["strong_recovery_attempts"] = int(self.strong_recovery_attempts)
        payload["retries_this_stage"] = int(self.retries_this_stage)
        payload["adaptation_tier"] = int(self.adaptation_tier)
        payload["adaptation_history"] = list(self.adaptation_history)
        payload["escalation_level"] = int(self.escalation_level)
        payload["rollouts_since_last_adaptation"] = int(
            getattr(self, "rollouts_since_last_adaptation", 0) or 0
        )
        payload["last_adaptation_stage_trades"] = int(
            getattr(self, "last_adaptation_stage_trades", -1) or -1
        )
        # Raptor v12/v13: persist rolling milestones + chunks.
        wins_at = getattr(self, "wins_at_trade_milestones", None)
        if isinstance(wins_at, dict) and wins_at:
            items = sorted(
                ((int(k), int(v)) for k, v in wins_at.items() if int(k) > 0),
                key=lambda kv: kv[0],
            )
            if len(items) > 64:
                items = items[-64:]
            payload["wins_at_trade_milestones"] = {str(k): v for k, v in items}
        chunks = getattr(self, "rolling_trade_chunks", None)
        if isinstance(chunks, list) and chunks:
            payload["rolling_trade_chunks"] = [
                [int(t), int(w)] for t, w in chunks[-128:] if int(t) > 0
            ]
        payload["curriculum_stage_scope"] = self.stage.value
        if self.intra_state is not None:
            payload["intra_stage1_hard_pct"] = round(float(self.intra_state.hard_pct), 4)
            payload["intra_stage1_easy_trades"] = int(self.intra_state.easy_trades)
            payload["intra_stage1_easy_wins"] = int(self.intra_state.easy_wins)
            payload["intra_stage1_easy_winrate_history"] = list(self.intra_state.easy_winrate_history)
            payload["intra_stage1_meta"] = dict(self.intra_meta)
        if self.intra_s2_state is not None:
            payload["intra_stage2_hard_pct"] = round(float(self.intra_s2_state.hard_pct), 4)
            payload["intra_stage2_easy_flat_bars"] = int(self.intra_s2_state.easy_flat_bars)
            payload["intra_stage2_easy_range_signals"] = int(self.intra_s2_state.easy_range_signals)
            payload["intra_stage2_easy_flat_ratio_history"] = list(
                self.intra_s2_state.easy_flat_ratio_history
            )
            payload["intra_stage2_meta"] = dict(self.intra_s2_meta)
        if self.cur_cfg.meta_controller_enabled:
            payload.update(self.bus.meta_metrics_payload(self.stage))
        payload.update(self.plateau_state.to_metrics())
        payload.update(self.remediation_state.to_metrics())
        payload.update(self.organism_autonomy_state.to_metrics())
        payload.update(self.bus.adaptation_recovery_metrics(self.stage))
        payload.update(self.swarm_state.to_metrics())
        payload.update(
            quarantine_progress_payload(
                self.plateau_quarantine,
                stage_trades=self.stage_trades,
                cfg=self.cur_cfg,
            )
        )
        payload["plateau_min_stage_trades"] = plateau_min_stage_trades(self.stage, self.cur_cfg)
        payload["stage_pass_gate_trades"] = self.required
        payload["stage_budget_trades"] = self.target
        # Starship champion / swarm persistence (resume-safe + poison sanitize).
        try:
            from lumina_core.birth.starship_birth import (
                publish_edgescore_champion_fields,
                sanitize_edgescore_champion,
            )

            best, at_trade, cleared = sanitize_edgescore_champion(
                best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                best_edgescore_at_trade=int(
                    getattr(self, "best_edgescore_at_trade", 0) or 0
                ),
                best_winrate=float(getattr(self.plateau_state, "best_winrate", 0.0) or 0.0),
                required=int(self.required),
                cfg=self.cur_cfg,
            )
            self.best_edgescore = best
            self.best_edgescore_at_trade = at_trade
            if cleared:
                self.best_edgescore_policy_path = ""
            payload.update(
                publish_edgescore_champion_fields(
                    best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                    best_edgescore_at_trade=int(
                        getattr(self, "best_edgescore_at_trade", 0) or 0
                    ),
                    best_edgescore_policy_path=str(
                        getattr(self, "best_edgescore_policy_path", "") or ""
                    ),
                    stage_trades=int(self.stage_trades),
                    required=int(self.required),
                    cfg=self.cur_cfg,
                )
            )
        except Exception as exc:
            logger.debug("birth.starship.champion_sanitize_metrics_failed: %s", exc)
            payload["best_edgescore"] = None
            payload["best_edgescore_at_trade"] = 0
            payload["best_edgescore_policy_path"] = ""
        payload["swarm_retearnament_used"] = bool(getattr(self, "swarm_retearnament_used", False))
        payload["swarm_rejected_no_lift"] = bool(
            getattr(self, "swarm_rejected_no_lift", False)
            or getattr(self.swarm_state, "rejected_no_lift", False)
        )
        tournament_lift_ok = bool(
            getattr(
                self,
                "swarm_tournament_lift_ok",
                getattr(self, "swarm_edgescore_lift_ok", False),
            )
        )
        tournament_at_start = round(
            float(
                getattr(
                    self,
                    "swarm_tournament_at_start",
                    getattr(self, "swarm_edgescore_at_start", -1.0),
                )
            ),
            6,
        )
        from lumina_core.birth.starship_swarm_gates import dual_write_tournament_lift_keys

        dual_write_tournament_lift_keys(
            payload,
            lift_ok=tournament_lift_ok,
            at_start=tournament_at_start,
        )
        payload["swarm_champion_accepted"] = bool(
            getattr(self, "swarm_champion_accepted", False)
            or getattr(self.swarm_state, "champion_accepted", False)
        )
        return payload

    def _maybe_periodic_checkpoint(self, phase: str) -> None:
        interval = max(60, int(self.cur_cfg.checkpoint_interval_sec))
        if self.host._last_checkpoint_at <= 0.0 or time.time() - self.host._last_checkpoint_at >= interval:
            self.host._persist_checkpoint(
                training_mode=self.training_mode,
                curriculum_stage=self.stage.value,
                phase=phase,
                stage_metrics=self._stage_metrics_payload(),
            )

