"""Stage-loop progress write path (M5 slim orchestrator).

Scorecard enrichment: ``stage_loop_progress_write_enrich``.
Starship fields: ``stage_loop_progress_write_starship``.
"""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.progress import merge_birth_progress_extra
from lumina_core.birth.stage_scorecard import build_scorecard_payload
from lumina_core.birth.stage_loop_progress_write_enrich import StageLoopProgressWriteEnrichMixin
from lumina_core.birth.stage_loop_progress_write_starship import (
    StageLoopProgressStarshipMixin,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopProgressWriteMixin(
    StageLoopProgressWriteEnrichMixin,
    StageLoopProgressStarshipMixin,
):
    """Writes birth progress scorecard fields."""

    def _write_progress(
        self,
        *,
        phase: str,
        message: str,
        chunk_trades: int = 0,
        rollout_steps: int = 0,
        exploration_active: bool = False,
        hold_ratio: float = 0.0,
    ) -> None:
        current_stage_trades = self.stage_trades + chunk_trades
        elapsed_snapshot = max(0.0, time.time() - self.scorecard_snapshot_at)
        constitution_fields = self.host._constitution_progress_fields()
        rolling_for_scorecard: float | None = None
        rolling_source = "lifetime_fallback"
        rolling_covered = 0
        try:
            rolling_for_scorecard, rolling_source, rolling_covered = self._rolling_winrate_meta()
        except Exception:
            try:
                rolling_for_scorecard = float(self._rolling_winrate_500())
            except Exception:
                rolling_for_scorecard = None
        from lumina_core.birth.starship_birth import (
            gate_rolling_winrate,
            hygiene_wr_telemetry,
            rolling_wr_pass_eligible,
        )

        roll_window = int(getattr(self.cur_cfg, "stage1_rolling_pass_window", 500) or 500)
        rolling_for_blocker = gate_rolling_winrate(
            rolling_wr=rolling_for_scorecard,
            source=rolling_source,
            covered=rolling_covered,
            window=roll_window,
        )
        rolling_eligible = rolling_wr_pass_eligible(
            source=rolling_source,
            covered=rolling_covered,
            window=roll_window,
        )
        entropy_for_blocker = self._resolve_policy_entropy()
        scorecard = build_scorecard_payload(
            stage=self.stage,
            curriculum_index=self.stage_index + 1,
            stages_passed=list(self.host._stages_passed),
            stage_trades=current_stage_trades,
            stage_wins=self.stage_wins,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            constitution_violations=int(constitution_fields["constitution_violations_session"]),
            target_trades=self.target,
            phase=phase,
            patterns_mined=self.patterns_mined,
            learning_attempt=self.attempt + 1,
            prev_stage_trades=self.scorecard_snapshot_trades,
            prev_patterns_mined=self.scorecard_snapshot_patterns,
            snapshot_elapsed_sec=elapsed_snapshot,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_round_trips=self.stage_range_round_trips,
            provisional_pass=self.gen0_provisional,
            cfg=self.cur_cfg,
            rolling_winrate=rolling_for_blocker,
            rolling_winrate_display=rolling_for_scorecard,
            rolling_wr_eligible=rolling_eligible,
            policy_entropy=entropy_for_blocker,
            ppo_steps=int(getattr(self.host, "ppo_steps", 0) or 0),
        )
        self._enrich_progress_scorecard(
            scorecard,
            phase=phase,
            current_stage_trades=current_stage_trades,
            constitution_fields=constitution_fields,
            rollout_steps=rollout_steps,
            rolling_for_scorecard=rolling_for_scorecard,
            rolling_for_blocker=rolling_for_blocker,
            rolling_source=rolling_source,
            rolling_covered=rolling_covered,
            roll_window=roll_window,
            hygiene_wr_telemetry=hygiene_wr_telemetry,
        )
        elapsed_stage_sec = max(0.0, time.time() - self.stage_started_at)
        # P4: honest progress — advance within stage (was frozen at stage base e.g. 27%).
        base_pct = float(self.stage_progress_pct)
        stage_span = 53.0 / 3.0  # curriculum band 27→80 across 3 core stages
        pass_gate = max(
            50,
            int(
                scorecard.get("stage_pass_gate_trades")
                or scorecard.get("stage_target_trades")
                or getattr(self, "target", 0)
                or 200
            ),
        )
        within = min(1.0, float(current_stage_trades) / float(pass_gate))
        honest_pct = round(min(79.5, base_pct + stage_span * within), 2)
        progress_extra = merge_birth_progress_extra(constitution_fields, scorecard)
        self.host._emit_birth_progress(
            stage="training_running",
            phase=phase,
            message=message,
            progress_pct=honest_pct,
            cumulative_trades=self.host.cumulative_trades + chunk_trades,
            target_trades=self.trade_budget_cap,
            ppo_steps=self.host.ppo_steps,
            birth_start_time=self.host.birth_start_time,
            curriculum_stage=self.stage.value,
            stage_trades=current_stage_trades,
            stage_hold_signals=self.stage_hold_signals,
            stage_total_signals=self.stage_total_signals,
            stage_range_hold_signals=self.stage_range_hold_signals,
            stage_range_total_signals=self.stage_range_total_signals,
            stage_range_flat_bars=self.stage_range_flat_bars,
            stage_range_round_trips=self.stage_range_round_trips,
            stage_range_flat_ratio=round(
                float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals)),
                4,
            ),
            rollout_trades=chunk_trades,
            rollout_steps=rollout_steps,
            hold_ratio=round(hold_ratio, 4),
            exploration_active=exploration_active,
            learning_attempt=self.attempt + 1,
            escalation_level=self.escalation_level,
            gen0_provisional=self.gen0_provisional,
            patterns_mined=self.patterns_mined,
            oracle_wins=self.oracle_wins,
            oracle_last_scanned=int(getattr(self, "oracle_last_scanned", 0) or 0),
            oracle_last_patterns=int(getattr(self, "oracle_last_patterns", 0) or 0),
            oracle_last_stop_pct=round(float(getattr(self, "oracle_last_stop_pct", 0.0) or 0.0), 6),
            oracle_last_target_pct=round(
                float(getattr(self, "oracle_last_target_pct", 0.0) or 0.0), 6
            ),
            oracle_last_reason=str(getattr(self, "oracle_last_reason", "") or ""),
            display_winrate_scope="stage_current",
            training_mode=str(self.training_mode),
            allow_provisional=bool(self.allow_provisional),
            data_days_loaded=self.data_days_loaded,
            requested_days=int(self.host._data_manifest.get("requested_days", 0) or 0) or None,
            actual_calendar_days=int(
                self.host._data_manifest.get("actual_calendar_days", 0) or 0
            )
            or None,
            requested_instrument=str(
                self.host._data_manifest.get("requested_instrument", "") or ""
            )
            or None,
            resolved_instrument=str(
                self.host._data_manifest.get("resolved_instrument", "") or ""
            )
            or None,
            rolled=self.host._data_manifest.get("rolled"),
            expansion_step=self.expansion_step,
            stage_wall_remaining_sec=max(
                0, int(self.cur_cfg.max_stage_wall_sec) - int(elapsed_stage_sec)
            ),
            quality_score=float(self.host._data_manifest.get("quality_score", 0.0) or 0.0),
            intra_hard_pct=round(float(self.intra_state.hard_pct), 4) if self.intra_state else None,
            intra_easy_winrate=round(
                float(self.intra_state.easy_wins) / float(max(1, self.intra_state.easy_trades)),
                4,
            )
            if self.intra_state and self.intra_state.easy_trades > 0
            else None,
            needs_attention=bool(
                (
                    getattr(self, "swarm_rejected_no_lift", False)
                    or getattr(self.swarm_state, "rejected_no_lift", False)
                )
                and not bool(
                    getattr(self, "swarm_champion_accepted", False)
                    or getattr(self.swarm_state, "champion_accepted", False)
                )
            ),
            attention_summary=(
                "Swarm tournament produced no tournament lift — champion frozen; accept or wipe."
                if (
                    (
                        getattr(self, "swarm_rejected_no_lift", False)
                        or getattr(self.swarm_state, "rejected_no_lift", False)
                    )
                    and not bool(
                        getattr(self, "swarm_champion_accepted", False)
                        or getattr(self.swarm_state, "champion_accepted", False)
                    )
                )
                else ""
            ),
            attention_reason_code=(
                (
                    str(getattr(self, "swarm_fail_reason_code", "") or "").strip()
                    or "swarm_no_tournament_lift"
                )
                if (
                    (
                        getattr(self, "swarm_rejected_no_lift", False)
                        or getattr(self.swarm_state, "rejected_no_lift", False)
                    )
                    and not bool(
                        getattr(self, "swarm_champion_accepted", False)
                        or getattr(self.swarm_state, "champion_accepted", False)
                    )
                )
                else ""
            ),
            attention_recommended_actions=(
                ["accept_champion", "wipe_and_retry"]
                if (
                    getattr(self, "swarm_rejected_no_lift", False)
                    or getattr(self.swarm_state, "rejected_no_lift", False)
                )
                and not bool(
                    getattr(self, "swarm_champion_accepted", False)
                    or getattr(self.swarm_state, "champion_accepted", False)
                )
                else []
            ),
            user_initiated_stop=False,
            extra_parts=(progress_extra,),
        )
        if (
            current_stage_trades > self.scorecard_snapshot_trades
            or self.patterns_mined > self.scorecard_snapshot_patterns
        ):
            self.scorecard_snapshot_trades = current_stage_trades
            self.scorecard_snapshot_patterns = self.patterns_mined
            self.scorecard_snapshot_at = time.time()
        self.last_progress_write_at = time.time()

